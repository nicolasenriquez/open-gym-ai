"""Settings passkey management through real HTTP and restricted PostgreSQL."""

import asyncio
import base64
import shutil
from pathlib import Path

import pytest
from test_identity_passkey import vector
from test_identity_password import PASSWORD
from test_identity_password import accounts as accounts  # noqa: PLC0414
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server


@pytest.mark.asyncio
async def test_list_is_owner_only_preserves_legacy_nulls_and_hides_key_material(
    accounts,
):
    observer, environment = accounts
    await observer.execute("""
        INSERT INTO identity.passkeys VALUES
            ('own','A',decode('aa','hex'),0,ARRAY['internal'],NULL,NULL,NULL),
            ('foreign','B',decode('bb','hex'),0,'{}','Private',NULL,NULL)
    """)
    async with server(environment) as client:
        assert (await client.get("/api/v1/account/passkeys")).status_code == 401
        result = await client.get(
            "/api/v1/account/passkeys?owner=B",
            headers={
                "Authorization": "Bearer " + A,
                "X-Owner-ID": "B",
            },
        )
        assert result.status_code == 200, result.text
        assert result.json() == {
            "passkeys": [
                {
                    "id": "own",
                    "name": None,
                    "created": None,
                    "lastUsed": None,
                    "transports": ["internal"],
                }
            ],
            "password": True,
            "lastWayIn": False,
        }
        assert result.headers["cache-control"] == "no-store"
        assert "set-cookie" not in result.headers


@pytest.mark.asyncio
async def test_owner_adds_a_verified_passkey_with_fresh_proof_and_no_new_session(
    accounts,
):
    observer, environment = accounts
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        headers = {"Authorization": "Bearer " + A}
        missing = await client.post(
            "/api/v1/account/passkeys/options", headers=headers, json={}
        )
        assert (
            missing.status_code == 403 and missing.json()["code"] == "current-required"
        )
        start = await client.post(
            "/api/v1/account/passkeys/options",
            headers=headers,
            json={"current": PASSWORD, "owner": "B"},
        )
        assert start.status_code == 200, start.text
        options = start.json()["options"]
        assert options["user"] == {"id": "QQ", "name": "Alice", "displayName": "Alice"}
        assert options["extensions"] == {"credProps": True}
        assert options["excludeCredentials"] == []
        body = {
            "cid": start.json()["cid"],
            "credential": vector("ES256/register")["credential"],
            "name": "  Phone\tkey\u202e  ",
        }
        added = await client.post(
            "/api/v1/account/passkeys/verify", headers=headers, json=body
        )
        assert added.status_code == 200, added.text
        assert "set-cookie" not in added.headers
        result = added.json()
        assert result["ok"] and result["password"] and not result["lastWayIn"]
        record = result["passkeys"][0]
        assert record["id"] == vector("ES256/register")["credentialId"]
        assert record["name"] == "Phone key" and record["lastUsed"] is None
        assert record["transports"] == ["internal", "hybrid"] and record[
            "created"
        ].endswith("Z")
        saved = await observer.fetchrow("SELECT * FROM identity.passkeys")
        assert saved["owner_id"] == "A" and saved["counter"] == 0
        assert bytes(saved["public_key"]) == base64.urlsafe_b64decode(
            vector("ES256/register")["publicKey"] + "=="
        )
        assert (
            await client.post(
                "/api/v1/account/passkeys/verify", headers=headers, json=body
            )
        ).json()["code"] == "challenge-expired"
        assert (await client.get("/api/v1/me", headers=headers)).status_code == 200
        assert (
            await client.get(
                "/api/v1/account/passkeys", headers={"Authorization": "Bearer " + B}
            )
        ).json()["passkeys"] == []


@pytest.mark.asyncio
async def test_rename_and_removal_are_owner_bound_require_proof_and_keep_last_way(
    accounts,
):
    observer, environment = accounts
    await observer.execute("""
        INSERT INTO identity.passkeys VALUES
            ('own','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL),
            ('foreign','B',decode('bb','hex'),0,'{}',NULL,NULL,NULL);
        INSERT INTO identity.device_links VALUES (decode(repeat('aa',32),'hex'),'A',clock_timestamp(),clock_timestamp()+interval '10 minutes');
    """)
    async with server(environment) as client:
        headers = {"Authorization": "Bearer " + A}
        renamed = await client.post(
            "/api/v1/account/passkeys/rename",
            headers=headers,
            json={"id": "own", "name": "  My\n key\u202e "},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["passkeys"][0]["name"] == "My key"
        for path, body in [
            ("/api/v1/account/passkeys/rename", {"id": "foreign", "name": "stolen"}),
            ("/api/v1/account/passkeys?id=foreign", {}),
        ]:
            result = await client.request(
                "DELETE" if "?id=" in path else "POST", path, headers=headers, json=body
            )
            assert result.status_code == 404 and result.json()["code"] == "not-found"
        no_proof = await client.request(
            "DELETE", "/api/v1/account/passkeys?id=own", headers=headers, json={}
        )
        assert (
            no_proof.status_code == 403
            and no_proof.json()["code"] == "current-required"
        )
        await observer.execute(
            "DELETE FROM identity.password_credentials WHERE owner_id='A'"
        )
        last = await client.request(
            "DELETE", "/api/v1/account/passkeys?id=own", headers=headers, json={}
        )
        assert last.status_code == 409 and last.json()["code"] == "last-way-in"
        await observer.execute(
            "INSERT INTO identity.password_credentials(owner_id,scrypt_hash) SELECT 'A',scrypt_hash FROM identity.password_credentials WHERE owner_id='B'"
        )
        removed = await client.request(
            "DELETE",
            "/api/v1/account/passkeys?id=own&id=foreign",
            headers=headers,
            json={"current": PASSWORD, "id": "foreign"},
        )
        assert removed.status_code == 200 and removed.json() == {
            "ok": True,
            "passkeys": [],
            "password": True,
            "lastWayIn": True,
        }
        assert (await client.get("/api/v1/me", headers=headers)).status_code == 200
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='B'"
            )
            == 1
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("password_on", [True, False])
async def test_password_way_in_counts_only_when_login_enabled(accounts, password_on):
    observer, environment = accounts
    environment["PASSWORD_LOGIN"] = "1" if password_on else "0"
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ('a2V5','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL)"
    )
    async with server(environment) as client:
        headers = {"Authorization": "Bearer " + A}
        state = (await client.get("/api/v1/account/passkeys", headers=headers)).json()
        assert (
            state["password"] is password_on and state["lastWayIn"] is not password_on
        )
        response = await client.post(
            "/api/v1/account/passkeys/options",
            headers=headers,
            json={"current": PASSWORD},
        )
        assert response.status_code == (200 if password_on else 403), response.text
        if not password_on:
            assert response.json()["code"] == "passkey-required"


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_duplicate", [False, True])
async def test_cap_and_duplicate_are_rechecked_after_concurrent_ceremonies(
    accounts, foreign_duplicate
):
    observer, environment = accounts
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    if foreign_duplicate:
        v = vector("Ed25519/register")
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ($1,'B',$2,0,'{}',NULL,NULL,NULL)",
            v["credentialId"],
            base64.urlsafe_b64decode(v["publicKey"] + "=="),
        )
    # Valid credential IDs for exclusion hints, independently seeded near the cap.
    for i in range(19):
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ($1,'A',decode('aa','hex'),0,'{}',NULL,NULL,NULL)",
            base64.urlsafe_b64encode(f"key-{i}".encode()).decode().rstrip("="),
        )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        headers = {"Authorization": "Bearer " + A}
        ceremonies = []
        for _ in range(3):
            response = await client.post(
                "/api/v1/account/passkeys/options",
                headers=headers,
                json={"current": PASSWORD},
            )
            assert response.status_code == 200, response.text
            assert len(response.json()["options"]["excludeCredentials"]) == 19
            ceremonies.append(response.json()["cid"])
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/account/passkeys/verify",
                    headers=headers,
                    json={
                        "cid": cid,
                        "credential": vector(alg + "/register")["credential"],
                    },
                )
                for cid, alg in zip(ceremonies[:2], ["ES256", "RS256"], strict=True)
            ]
        )
        assert sorted(r.status_code for r in responses) == [200, 409]
        assert (
            next(r for r in responses if r.status_code == 409).json()["code"]
            == "passkey-limit"
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            )
            == 20
        )
        limited = await client.post(
            "/api/v1/account/passkeys/options", headers=headers, json={}
        )
        assert limited.status_code == 409 and limited.json()["code"] == "passkey-limit"
        winner = (
            "Ed25519"
            if foreign_duplicate
            else "ES256"
            if responses[0].status_code == 200
            else "RS256"
        )
        duplicate = await client.post(
            "/api/v1/account/passkeys/verify",
            headers=headers,
            json={
                "cid": ceremonies[2],
                "credential": vector(winner + "/register")["credential"],
            },
        )
        assert (
            duplicate.status_code == 409
            and duplicate.json()["code"] == "credential-exists"
        )


@pytest.mark.asyncio
async def test_add_challenge_is_owner_bound_one_use_and_rejects_invalid_registration(
    accounts,
):
    _, environment = accounts
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        headers = {"Authorization": "Bearer " + A}
        for bad in [None, {}, [], {"id": "bad", "response": {}}]:
            start = (
                await client.post(
                    "/api/v1/account/passkeys/options",
                    headers=headers,
                    json={"current": PASSWORD},
                )
            ).json()
            body = {"cid": start["cid"], "credential": bad}
            result = await client.post(
                "/api/v1/account/passkeys/verify", headers=headers, json=body
            )
            assert result.status_code == 400, result.text
            assert (
                await client.post(
                    "/api/v1/account/passkeys/verify", headers=headers, json=body
                )
            ).json()["code"] == "challenge-expired"
        start = (
            await client.post(
                "/api/v1/account/passkeys/options",
                headers=headers,
                json={"current": PASSWORD},
            )
        ).json()
        body = {
            "cid": start["cid"],
            "credential": vector("ES256/register")["credential"],
        }
        foreign = await client.post(
            "/api/v1/account/passkeys/verify",
            headers={"Authorization": "Bearer " + B},
            json=body,
        )
        assert (
            foreign.status_code == 400 and foreign.json()["code"] == "challenge-expired"
        )
        assert (
            await client.post(
                "/api/v1/account/passkeys/verify", headers=headers, json=body
            )
        ).json()["code"] == "challenge-expired"
        start = (
            await client.post(
                "/api/v1/account/passkeys/options",
                headers=headers,
                json={"current": PASSWORD},
            )
        ).json()
        assert (
            await client.post("/api/v1/logout/all", headers=headers)
        ).status_code == 200
        assert (
            await client.post(
                "/api/v1/login/password", json={"name": "Alice", "password": PASSWORD}
            )
        ).status_code == 200
        # A fresh session must not revive an older version's unspent ceremony.
        stale = await client.post(
            "/api/v1/account/passkeys/verify",
            json={
                "cid": start["cid"],
                "credential": vector("ES256/register")["credential"],
            },
        )
        assert stale.status_code == 401 and "set-cookie" not in stale.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["options", "verify", "rename", "remove"])
async def test_management_transport_rejects_cross_origin_and_invalid_sessions(
    accounts, operation
):
    _, environment = accounts
    path = "/api/v1/account/passkeys" + (
        "" if operation == "remove" else "/" + operation
    )
    method = "DELETE" if operation == "remove" else "POST"
    async with server(environment) as client:
        denied = await client.request(
            method,
            path,
            headers={"Cookie": "gymsid=" + A, "Origin": "https://foreign.test"},
            json={},
        )
        assert denied.status_code == 403
        expired = await client.request(
            method, path, headers={"Authorization": "Bearer invalid"}, json={}
        )
        assert expired.status_code == 401
        malformed = await client.request(
            method, path, headers={"Authorization": "Bearer " + A}, content="["
        )
        assert malformed.status_code == 400


@pytest.mark.asyncio
async def test_two_removals_may_remove_all_passkeys_when_password_remains(accounts):
    observer, environment = accounts
    await observer.execute("""INSERT INTO identity.passkeys VALUES
        ('one','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL),
        ('two','A',decode('bb','hex'),0,'{}',NULL,NULL,NULL)""")
    async with server(environment) as client:
        responses = await asyncio.gather(
            *[
                client.request(
                    "DELETE",
                    "/api/v1/account/passkeys?id=" + key,
                    headers={"Authorization": "Bearer " + A},
                    json={"current": PASSWORD},
                )
                for key in ["one", "two"]
            ]
        )
        assert [r.status_code for r in responses] == [200, 200]
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            )
            == 0
        )
        assert (
            await client.post(
                "/api/v1/login/password", json={"name": "Alice", "password": PASSWORD}
            )
        ).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase,mutation,expected",
    [
        ("options", "version", 401),
        ("options", "hash", 403),
        ("verify", "valid", 200),
        ("verify", "version", 401),
        ("verify", "disabled", 401),
        ("verify", "deleted", 401),
        ("verify", "expire", 401),
        ("remove", "last-key", 403),
    ],
)
async def test_crypto_outside_transaction_revalidates_before_commit(
    accounts, tmp_path, phase, mutation, expected
):
    import time

    from test_identity_session import SECRET

    from opengym_platform.identity.sessions import sign

    observer, environment = accounts
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "management_boundary.py").write_text(f"""
import time
from pathlib import Path
from opengym_platform.identity import account, passwords
from test_identity_passkey import fixed_challenge_app
original = account.verify_registration_response if {phase!r} == 'verify' else passwords.derive
def pause(*args, **kwargs):
    if {phase!r} != 'verify' and args[0] != {PASSWORD!r}:
        return original(*args, **kwargs)
    Path({str(entered)!r}).touch()
    deadline = time.monotonic()+8
    while not Path({str(release)!r}).exists():
        if time.monotonic()>deadline:
            raise ValueError('synthetic crypto deadline')
        time.sleep(.01)
    return original(*args, **kwargs)
if {phase!r} == 'verify':
    account.verify_registration_response = pause
else:
    passwords.derive = pause
create_app = fixed_challenge_app
""")
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    environment["PYTHONPATH"] = (
        str(tmp_path) + ":" + str(Path(__file__).parent) + ":/app/src"
    )
    if phase == "remove":
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ('key','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL)"
        )
    async with server(environment, factory="management_boundary:create_app") as client:
        expires = int(time.time() * 1000) + 3000
        token = sign(f"A:{expires}:0", SECRET) if mutation == "expire" else A
        headers = {"Authorization": "Bearer " + token}
        body = {"current": PASSWORD}
        if phase == "verify":
            started = await client.post(
                "/api/v1/account/passkeys/options", headers=headers, json=body
            )
            assert started.status_code == 200, started.text
            body = {
                "cid": started.json()["cid"],
                "credential": vector("ES256/register")["credential"],
            }
        task = asyncio.create_task(
            client.request(
                "DELETE" if phase == "remove" else "POST",
                "/api/v1/account/passkeys?id=key"
                if phase == "remove"
                else "/api/v1/account/passkeys/" + phase,
                headers=headers,
                json=body,
                timeout=12,
            )
        )
        try:
            async with asyncio.timeout(4):
                while not entered.exists():
                    await asyncio.sleep(0.01)
            assert not await observer.fetchval(
                "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND xact_start IS NOT NULL)"
            )
            changes = {
                "version": "UPDATE identity.users SET session_version=1 WHERE id='A'",
                "hash": "UPDATE identity.password_credentials SET scrypt_hash='replaced' WHERE owner_id='A'",
                "disabled": "UPDATE identity.users SET disabled=true WHERE id='A'",
                "deleted": "DELETE FROM identity.users WHERE id='A'",
                "last-key": "DELETE FROM identity.password_credentials WHERE owner_id='A'",
            }
            if mutation in changes:
                await observer.execute(changes[mutation])
            if mutation == "expire":
                await observer.execute(
                    "SELECT pg_sleep(greatest(0,$1/1000.0-extract(epoch from clock_timestamp()))+0.03)",
                    expires,
                )
        finally:
            release.touch()
        result = await task
        assert result.status_code == expected, result.text
        assert "set-cookie" not in result.headers
        if phase == "verify":
            assert await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            ) == (1 if mutation == "valid" else 0)
        if mutation == "last-key":
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
                )
                == 1
            )
        assert (
            await client.get("/api/v1/me", headers={"Authorization": "Bearer " + B})
        ).status_code == 200


@pytest.mark.asyncio
async def test_two_passkey_confirmed_removals_cannot_delete_last_access(accounts):
    observer, environment = accounts
    environment.update(
        PASSWORD_LOGIN="0", RP_ID="localhost", ORIGIN="http://localhost:8080"
    )
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    for alg in ["ES256", "RS256"]:
        v = vector(alg + "/assertion")
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ($1,'A',$2,0,'{}',NULL,NULL,NULL)",
            v["credentialId"],
            base64.urlsafe_b64decode(v["publicKey"] + "=="),
        )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        headers = {"Authorization": "Bearer " + A}
        cids = [
            (await client.post("/api/v1/login/options")).json()["cid"] for _ in range(2)
        ]
        responses = await asyncio.gather(
            *[
                client.request(
                    "DELETE",
                    "/api/v1/account/passkeys?id="
                    + vector(alg + "/assertion")["credentialId"],
                    headers=headers,
                    json={
                        "cid": cid,
                        "credential": vector(alg + "/assertion")["credential"],
                    },
                )
                for alg, cid in zip(["ES256", "RS256"], cids, strict=True)
            ]
        )
        assert sorted(r.status_code for r in responses) == [200, 409], [
            r.text for r in responses
        ]
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            )
            == 1
        )
        assert (await client.get("/api/v1/me", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_rename_does_not_spend_node_auth_burst(accounts):
    observer, environment = accounts
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ('key','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL)"
    )
    async with server(environment) as client:
        for i in range(62):
            response = await client.post(
                "/api/v1/account/passkeys/rename",
                headers={"Authorization": "Bearer " + A},
                json={"id": "key", "name": str(i)},
            )
            assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_management_upgrade_preserves_rows_and_forced_rls_grants(
    deployment, tmp_path, monkeypatch
):
    from test_identity_session import SECRET

    from opengym_platform.core.database import Database, DatabaseError
    from opengym_platform.identity.sessions import authorize, verify

    observer, environment = deployment
    previous = tmp_path / "previous"
    shutil.copytree(
        Path("/app/src/opengym_platform"),
        previous / "opengym_platform",
        ignore=shutil.ignore_patterns("p001_passkey_manage.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_account"
    )
    await observer.execute("""INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'),('B','Bob');
        INSERT INTO identity.passkeys VALUES ('own','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL),
            ('foreign','B',decode('bb','hex'),0,'{}',NULL,NULL,NULL)""")
    before = await observer.fetch(
        "SELECT * FROM identity.passkeys ORDER BY credential_id"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetch("SELECT * FROM identity.passkeys ORDER BY credential_id")
        == before
    )
    assert await observer.fetchval(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='identity.passkeys'::regclass"
    )
    assert not await observer.fetchval(
        "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname='opengym_api_runtime'"
    )
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()
    try:
        assert await database.fetch("SELECT * FROM identity.passkeys") == []
        for sql in [
            "SET ROLE opengym_identity_executor",
            "UPDATE identity.passkeys SET counter=5",
            "UPDATE identity.passkeys SET owner_id='B'",
            "UPDATE identity.passkeys SET public_key=decode('cc','hex')",
        ]:
            with pytest.raises(DatabaseError):
                await database.execute(sql)
        async with database.transaction() as handle:
            await handle.execute("SELECT pg_advisory_xact_lock(728323)")
            assert await authorize(handle, verify("", "Bearer " + A, False, SECRET))
            assert [
                r["credential_id"]
                for r in await handle.fetch("SELECT * FROM identity.passkeys")
            ] == ["own"]
            assert (
                await handle.fetch(
                    "UPDATE identity.passkeys SET label='stolen' WHERE credential_id='foreign' RETURNING credential_id"
                )
                == []
            )
            assert (
                await handle.fetch(
                    "DELETE FROM identity.passkeys WHERE credential_id='foreign' RETURNING credential_id"
                )
                == []
            )
        assert await database.fetch("SELECT * FROM identity.passkeys") == []
        with pytest.raises(DatabaseError):
            await database.execute(
                "INSERT INTO identity.passkeys VALUES ('intruder','B',decode('aa','hex'),0,'{}',NULL,NULL,NULL)"
            )
    finally:
        await database.close()
    assert (
        await observer.fetch("SELECT * FROM identity.passkeys ORDER BY credential_id")
        == before
    )


@pytest.mark.asyncio
async def test_failed_removal_rolls_back_passkey_proof_and_link_deletion(accounts):
    observer, environment = accounts
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    v = vector("ES256/assertion")
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ($1,'A',$2,0,'{}',NULL,NULL,NULL)",
        v["credentialId"],
        base64.urlsafe_b64decode(v["publicKey"] + "=="),
    )
    await observer.execute("""
        INSERT INTO identity.device_links VALUES (decode(repeat('aa',32),'hex'),'A',clock_timestamp(),clock_timestamp()+interval '10 minutes');
        CREATE FUNCTION public.fail_management() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$;
        CREATE TRIGGER fail_management BEFORE DELETE ON identity.device_links FOR EACH ROW EXECUTE FUNCTION public.fail_management();
    """)
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        headers = {"Authorization": "Bearer " + A}

        async def remove():
            cid = (await client.post("/api/v1/login/options")).json()["cid"]
            return await client.request(
                "DELETE",
                "/api/v1/account/passkeys?id=" + v["credentialId"],
                headers=headers,
                json={"cid": cid, "credential": v["credential"]},
            )

        failed = await remove()
        assert failed.status_code == 500 and failed.json() == {"error": "server error"}
        assert "set-cookie" not in failed.headers
        assert await observer.fetchval("SELECT counter FROM identity.passkeys") == 0
        assert (
            await observer.fetchval("SELECT last_used_at FROM identity.passkeys")
            is None
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        await observer.execute("DROP TRIGGER fail_management ON identity.device_links")
        assert (await remove()).status_code == 200
        assert await observer.fetchval("SELECT count(*) FROM identity.passkeys") == 0
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )
