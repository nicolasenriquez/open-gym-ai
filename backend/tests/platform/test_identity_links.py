"""Pairing and passkey device links through restricted HTTP and real PostgreSQL."""

import asyncio
import base64
import hashlib
import shutil
from pathlib import Path

import pytest
import pytest_asyncio
from test_identity_passkey import vector
from test_identity_password import PASSWORD
from test_identity_password import accounts as accounts  # noqa: PLC0414
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

CODE = "K7WQ-2MZP-4HXA"
DIGEST = bytes.fromhex(
    "b45069fe4cc0a84a842c5fcc0e2832f86464ccf4cafa582726a6058ecf6125cc"
)
LINK_INVALID = {"error": "that code is wrong, used or expired", "code": "link-invalid"}


@pytest_asyncio.fixture
async def pending(accounts):
    observer, environment = accounts
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await observer.execute(
        "INSERT INTO identity.device_links VALUES ($1,'A',now(),now()+interval '10 min')",
        DIGEST,
    )
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ('Zm9yZWlnbg','B',decode('aa','hex'),0,'{}','foreign',NULL,NULL)"
    )
    return observer, environment


def redemption(start, algorithm="ES256", code=CODE):
    return {
        "code": code,
        "cid": start["cid"],
        "credential": vector(algorithm + "/register")["credential"],
        "name": "Linked device",
    }


async def start_link(client, code=CODE):
    result = await client.post("/api/v1/device-link/options", json={"code": code})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token,other,owner,name,admin",
    [(A, B, "A", "Alice", False), (B, A, "B", "Bob", True)],
)
async def test_pairing_replaces_previous_code_and_redeems_once_as_bearer(
    accounts, token, other, owner, name, admin
):
    observer, environment = accounts
    async with server(environment) as client:
        first = await client.post(
            "/api/v1/pair/create", headers={"Authorization": "Bearer " + token}
        )
        assert first.status_code == 200, first.text
        code = first.json()["code"]
        assert len(code) == 8 and set(code) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
        second = await client.post(
            "/api/v1/pair/create", headers={"Authorization": "Bearer " + token}
        )
        assert (
            await client.post("/api/v1/pair/redeem", json={"code": code})
        ).json() == {"error": "invalid or expired code", "code": "pair-invalid"}
        result = await client.post(
            "/api/v1/pair/redeem",
            headers={"Origin": "capacitor://localhost"},
            json={
                "code": " " + second.json()["code"].lower() + " ",
                "owner": "B" if owner == "A" else "A",
            },
        )
        assert result.status_code == 200, result.text
        assert result.json()["user"] == {"id": owner, "name": name, "admin": admin}
        assert "set-cookie" not in result.headers
        me = await client.get(
            "/api/v1/me", headers={"Authorization": "Bearer " + result.json()["token"]}
        )
        assert me.json()["user"]["id"] == owner
        assert (
            await client.post(
                "/api/v1/pair/redeem", json={"code": second.json()["code"]}
            )
        ).status_code == 400
        assert (
            await client.get("/api/v1/me", headers={"Authorization": "Bearer " + other})
        ).status_code == 200
    assert await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0


@pytest.mark.asyncio
async def test_device_link_survives_restart_with_fresh_ceremony_but_old_cid_is_abandoned(
    pending,
):
    observer, environment = pending
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        old = await start_link(client)
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        stale = await client.post("/api/v1/device-link/verify", json=redemption(old))
        assert stale.status_code == 400 and stale.json()["code"] == "challenge-expired"
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        assert (
            await client.post(
                "/api/v1/device-link/verify", json=redemption(await start_link(client))
            )
        ).status_code == 200
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["ES256", "RS256", "Ed25519"])
async def test_device_link_creates_a_passkey_on_code_owner_and_consumes_once(
    accounts, algorithm
):
    observer, environment = accounts
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await observer.execute(
        "INSERT INTO identity.device_links VALUES (decode('b45069fe4cc0a84a842c5fcc0e2832f86464ccf4cafa582726a6058ecf6125cc','hex'),'A',now(),now()+interval '10 min')"
    )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        start = await client.post(
            "/api/v1/device-link/options",
            json={"code": " k7wq 2mzp 4hxa ", "owner": "B"},
        )
        assert start.status_code == 200, start.text
        assert start.json()["id"] == "A" and start.json()["name"] == "Alice"
        assert (
            base64.urlsafe_b64decode(start.json()["options"]["user"]["id"] + "==")
            == b"A"
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        body = {
            "code": "K7WQ-2MZP-4HXA",
            "cid": start.json()["cid"],
            "credential": vector(algorithm + "/register")["credential"],
            "name": "Second device",
            "owner": "B",
        }
        result = await client.post(
            "/api/v1/device-link/verify",
            headers={"Authorization": "Bearer " + B},
            json=body,
        )
        assert result.status_code == 200, result.text
        assert result.json() == {"user": {"id": "A", "name": "Alice", "admin": False}}
        assert "HttpOnly" in result.headers["set-cookie"]
        assert (await client.get("/api/v1/me")).json()["user"]["id"] == "A"
        row = await observer.fetchrow("SELECT * FROM identity.passkeys")
        assert row["owner_id"] == "A" and row["label"] == "Second device"
        assert row["created_at"] == row["last_used_at"]
        assert bytes(row["public_key"]) == base64.urlsafe_b64decode(
            vector(algorithm + "/register")["publicKey"] + "=="
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )
        assert (await client.post("/api/v1/device-link/verify", json=body)).json() == {
            "error": "that code is wrong, used or expired",
            "code": "link-invalid",
        }
    assert await observer.fetchval("SELECT count(*) FROM identity.users") == 2
    assert (
        await observer.fetchval("SELECT sum(session_version) FROM identity.users") == 3
    )


@pytest.mark.asyncio
async def test_create_requires_fresh_proof_stores_only_digest_and_replaces_link(
    accounts,
):
    observer, environment = accounts
    async with server(environment) as client:
        headers = {"Authorization": "Bearer " + A}
        missing = await client.post(
            "/api/v1/account/device-link", headers=headers, json={}
        )
        assert (
            missing.status_code == 403 and missing.json()["code"] == "current-required"
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )
        first = await client.post(
            "/api/v1/account/device-link",
            headers=headers,
            json={"current": PASSWORD, "owner": "B"},
        )
        assert first.status_code == 200, first.text
        code = first.json()["code"]
        assert len(code) == 14 and set(code.replace("-", "")) <= set(
            "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        )
        row = await observer.fetchrow("SELECT * FROM identity.device_links")
        assert (
            row["owner_id"] == "A"
            and bytes(row["code_digest"])
            == hashlib.sha256(
                ("opengym-link:" + code.replace("-", "")).encode()
            ).digest()
        )
        assert (row["expires_at"] - row["created_at"]).total_seconds() == 600
        assert round(row["expires_at"].timestamp() * 1000) == first.json()["expires"]
        second = await client.post(
            "/api/v1/account/device-link", headers=headers, json={"current": PASSWORD}
        )
        assert second.status_code == 200 and second.json()["code"] != code
        assert (
            await client.post("/api/v1/device-link/options", json={"code": code})
        ).json() == LINK_INVALID
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["version", "disabled", "deleted", "valid"])
async def test_pairing_wait_rechecks_owner_and_revocation(accounts, change):
    observer, environment = accounts
    async with server(environment) as client:
        code = (
            await client.post(
                "/api/v1/pair/create", headers={"Authorization": "Bearer " + A}
            )
        ).json()["code"]
        async with observer.transaction():
            await observer.execute("SELECT pg_advisory_xact_lock(728323)")
            task = asyncio.create_task(
                client.post("/api/v1/pair/redeem", json={"code": code})
            )
            async with asyncio.timeout(1.8):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock')"
                    ):
                        break
                    await asyncio.sleep(0.01)
            if change != "valid":
                await observer.execute(
                    {
                        "version": "UPDATE identity.users SET session_version=1 WHERE id='A'",
                        "disabled": "UPDATE identity.users SET disabled=true WHERE id='A'",
                        "deleted": "DELETE FROM identity.users WHERE id='A'",
                    }[change]
                )
        result = await task
        assert result.status_code == (200 if change == "valid" else 400)
        if change != "valid":
            assert result.json() == {
                "error": "invalid or expired code",
                "code": "pair-invalid",
            }
            assert "set-cookie" not in result.headers
        assert (
            await client.post("/api/v1/pair/redeem", json={"code": code})
        ).status_code == 400


@pytest.mark.asyncio
async def test_pairing_concurrency_restart_and_real_logout_revoke_codes(accounts):
    _, environment = accounts
    async with server(environment) as client:
        headers = {"Authorization": "Bearer " + A}
        code = (await client.post("/api/v1/pair/create", headers=headers)).json()[
            "code"
        ]
        results = await asyncio.gather(
            *[client.post("/api/v1/pair/redeem", json={"code": code}) for _ in range(2)]
        )
        assert sorted(r.status_code for r in results) == [200, 400]
        code = (await client.post("/api/v1/pair/create", headers=headers)).json()[
            "code"
        ]
        assert (
            await client.post("/api/v1/logout/all", headers=headers)
        ).status_code == 200
        assert (
            await client.post("/api/v1/pair/redeem", json={"code": code})
        ).status_code == 400
        code_b = (
            await client.post(
                "/api/v1/pair/create", headers={"Authorization": "Bearer " + B}
            )
        ).json()["code"]
    async with server(environment) as client:
        assert (
            await client.post("/api/v1/pair/redeem", json={"code": code_b})
        ).status_code == 400


@pytest.mark.asyncio
async def test_link_challenges_are_bound_to_code_kind_and_owner_and_burn_on_failure(
    pending,
):
    observer, environment = pending
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        start = await start_link(client)
        login = (await client.post("/api/v1/login/options")).json()
        result = await client.post("/api/v1/device-link/verify", json=redemption(login))
        assert (
            result.status_code == 400 and result.json()["code"] == "challenge-expired"
        )
        assert (
            await client.post(
                "/api/v1/login/verify",
                json={
                    "cid": login["cid"],
                    "credential": vector("ES256/assertion")["credential"],
                },
            )
        ).json()["code"] == "challenge-expired"
        invalid = await client.post(
            "/api/v1/device-link/verify", json={**redemption(start), "credential": {}}
        )
        assert invalid.status_code == 400 and "set-cookie" not in invalid.headers
        assert (
            await client.post("/api/v1/device-link/verify", json=redemption(start))
        ).json()["code"] == "challenge-expired"
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        first = await start_link(client)
        other = (
            await client.post(
                "/api/v1/account/device-link",
                headers={"Authorization": "Bearer " + B},
                json={"current": PASSWORD},
            )
        ).json()["code"]
        cross = await client.post(
            "/api/v1/device-link/verify", json=redemption(first, code=other)
        )
        assert cross.status_code == 400 and cross.json()["code"] == "challenge-expired"
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            )
            == 0
        )
        assert (
            await client.post(
                "/api/v1/device-link/verify", json=redemption(await start_link(client))
            )
        ).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    ["valid", "expiry", "replacement", "version", "disabled", "deleted", "logout"],
)
async def test_link_verification_rechecks_access_after_crypto_without_holding_a_lease(
    pending, tmp_path, change
):
    observer, environment = pending
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "link_boundary.py").write_text(f"""
import time
from pathlib import Path
from test_identity_passkey import fixed_challenge_app
from opengym_platform.identity import links
original = links.verify_registration_response
def verify(**args):
    Path({str(entered)!r}).touch()
    deadline = time.monotonic()+8
    while not Path({str(release)!r}).exists():
        if time.monotonic()>deadline:
            raise ValueError("synthetic crypto deadline")
        time.sleep(.01)
    return original(**args)
links.verify_registration_response = verify
create_app = fixed_challenge_app
""")
    environment["PYTHONPATH"] = str(tmp_path) + ":" + environment["PYTHONPATH"]
    async with server(environment, factory="link_boundary:create_app") as client:
        start = await start_link(client)
        task = asyncio.create_task(
            client.post("/api/v1/device-link/verify", json=redemption(start))
        )
        try:
            async with asyncio.timeout(4):
                while not entered.exists():
                    await asyncio.sleep(0.01)
            assert not await observer.fetchval(
                "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND xact_start IS NOT NULL)"
            )
            changes = {
                "expiry": "UPDATE identity.device_links SET expires_at=clock_timestamp() WHERE owner_id='A'",
                "replacement": "UPDATE identity.device_links SET code_digest=decode(repeat('cd',32),'hex') WHERE owner_id='A'",
                "version": "UPDATE identity.users SET session_version=1 WHERE id='A'",
                "disabled": "UPDATE identity.users SET disabled=true WHERE id='A'",
                "deleted": "DELETE FROM identity.users WHERE id='A'",
            }
            if change == "logout":
                assert (
                    await client.post(
                        "/api/v1/logout/all", headers={"Authorization": "Bearer " + A}
                    )
                ).status_code == 200
            elif change in changes:
                await observer.execute(changes[change])
        finally:
            release.touch()
        result = await task
        assert result.status_code == (200 if change == "valid" else 400), result.text
        if change != "valid":
            assert result.json() == LINK_INVALID and "set-cookie" not in result.headers
        assert await observer.fetchval(
            "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
        ) == (1 if change == "valid" else 0)
        assert (
            await observer.fetchval(
                "SELECT label FROM identity.passkeys WHERE owner_id='B'"
            )
            == "foreign"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["limit", "duplicate", "both"])
async def test_cap_and_foreign_duplicate_leave_code_available_for_a_new_ceremony(
    pending, reason
):
    observer, environment = pending
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        start = await start_link(client)
        if reason in ("limit", "both"):
            await observer.execute("""INSERT INTO identity.passkeys SELECT
                rtrim(encode(convert_to('cap-'||g,'UTF8'),'base64'),'='),'A',decode('aa','hex'),0,'{}',NULL,NULL,NULL FROM generate_series(1,20) g""")
        if reason in ("duplicate", "both"):
            await observer.execute(
                "INSERT INTO identity.passkeys VALUES ($1,'B',$2,0,'{}',NULL,NULL,NULL)",
                vector("ES256/register")["credentialId"],
                base64.urlsafe_b64decode(vector("ES256/register")["publicKey"] + "=="),
            )
        result = await client.post("/api/v1/device-link/verify", json=redemption(start))
        assert result.status_code == 409 and result.json()["code"] == (
            "passkey-limit" if reason == "limit" else "credential-exists"
        )
        assert "set-cookie" not in result.headers
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        if reason in ("limit", "both"):
            for path, body, headers in [
                ("/api/v1/device-link/options", {"code": CODE}, {}),
                (
                    "/api/v1/account/device-link",
                    {"current": PASSWORD},
                    {"Authorization": "Bearer " + A},
                ),
            ]:
                response = await client.post(path, json=body, headers=headers)
                assert (
                    response.status_code == 409
                    and response.json()["code"] == "passkey-limit"
                )
            await observer.execute("DELETE FROM identity.passkeys WHERE owner_id='A'")
        assert (
            await client.post(
                "/api/v1/device-link/verify",
                json=redemption(await start_link(client), "RS256"),
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_pairing_expiry_during_lock_wait_uses_five_minute_code_deadline(
    accounts, tmp_path
):
    observer, environment = accounts
    (tmp_path / "pair_clock.py").write_text("""
import time
from types import SimpleNamespace
from opengym_platform.application import create_app
from opengym_platform.identity import links
links.time = SimpleNamespace(time=lambda: time.time()-299)
""")
    environment["PYTHONPATH"] = str(tmp_path) + ":/app/src"
    async with server(environment, factory="pair_clock:create_app") as client:
        code = (
            await client.post(
                "/api/v1/pair/create", headers={"Authorization": "Bearer " + A}
            )
        ).json()["code"]
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            task = asyncio.create_task(
                client.post("/api/v1/pair/redeem", json={"code": code})
            )
            async with asyncio.timeout(0.6):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%identity.lock_actor%')"
                    ):
                        break
                    await asyncio.sleep(0.01)
            await observer.execute("SELECT pg_sleep(1.1)")
        result = await task
        assert result.status_code == 400 and result.json()["code"] == "pair-invalid"
        assert "token" not in result.json()


@pytest.mark.asyncio
async def test_device_link_creation_accepts_fresh_own_passkey_when_passwords_are_off(
    pending,
):
    observer, environment = pending
    environment["PASSWORD_LOGIN"] = "0"
    case = vector("ES256/assertion")
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ($1,'A',$2,0,'{}',NULL,NULL,NULL)",
        case["credentialId"],
        base64.urlsafe_b64decode(case["publicKey"] + "=="),
    )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        headers = {"Authorization": "Bearer " + A}
        denied = await client.post(
            "/api/v1/account/device-link", headers=headers, json={"current": PASSWORD}
        )
        assert denied.status_code == 403 and denied.json()["code"] == "passkey-required"
        proof = (await client.post("/api/v1/login/options")).json()
        created = await client.post(
            "/api/v1/account/device-link",
            headers=headers,
            json={"cid": proof["cid"], "credential": case["credential"]},
        )
        assert created.status_code == 200, created.text
        assert (
            await observer.fetchval(
                "SELECT counter FROM identity.passkeys WHERE owner_id='A'"
            )
            == 1
        )
        assert (
            await client.post(
                "/api/v1/account/device-link",
                headers=headers,
                json={"cid": proof["cid"], "credential": case["credential"]},
            )
        ).status_code == 403
        code = created.json()["code"]
        start = await start_link(client, code)
        assert start["options"]["excludeCredentials"][0]["id"] == case["credentialId"]
        assert (
            await client.post(
                "/api/v1/device-link/verify", json=redemption(start, "Ed25519", code)
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_transport_and_separate_link_failure_budget_keep_other_signins_usable(
    accounts,
):
    _, environment = accounts
    environment["TRUST_PROXY"] = "1"
    headers = {"Authorization": "Bearer " + A}
    async with server(environment) as client:
        assert (
            await client.post("/api/v1/pair/create", content="{")
        ).status_code == 401
        assert (
            await client.post(
                "/api/v1/pair/create",
                headers={"Cookie": "gymsid=" + A, "Origin": "https://foreign.test"},
            )
        ).status_code == 403
        assert (
            await client.post("/api/v1/pair/create", headers=headers, content="{")
        ).status_code == 200
        for path in [
            "/api/v1/device-link/options",
            "/api/v1/device-link/verify",
            "/api/v1/account/device-link",
        ]:
            assert (
                await client.post(
                    path, headers={"Origin": "https://foreign.test"}, json={}
                )
            ).status_code == 403
            for raw, status in [
                ("{", 400),
                ("[]", 400),
                ("1", 400),
                ("x" * (5 * 1024 * 1024 + 1), 413),
            ]:
                assert (
                    await client.post(
                        path,
                        headers={**headers, "X-Forwarded-For": "192.0.2.9"},
                        content=raw,
                    )
                ).status_code == status
        for _ in range(21):
            assert (
                await client.post(
                    "/api/v1/device-link/options",
                    headers={"X-Forwarded-For": "192.0.2.1"},
                    json={"code": "wrong"},
                )
            ).status_code == 400
        blocked = await client.post(
            "/api/v1/device-link/verify",
            headers={"X-Forwarded-For": "192.0.2.1"},
            json={},
        )
        assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
        login = await client.post(
            "/api/v1/login/password",
            headers={"X-Forwarded-For": "192.0.2.1"},
            json={"name": "Alice", "password": PASSWORD},
        )
        assert login.status_code == 200
        for path in [
            "/api/pair/create",
            "/api/pair/redeem",
            "/api/account/device-link",
            "/api/device-link/options",
            "/api/device-link/verify",
        ]:
            assert (await client.post(path, json={})).status_code == 404


@pytest.mark.asyncio
async def test_forward_migration_preserves_links_and_keeps_functions_and_runtime_bounded(
    deployment, tmp_path, monkeypatch
):
    from opengym_platform.core.database import Database, DatabaseError

    observer, environment = deployment
    previous = tmp_path / "previous"
    shutil.copytree(
        Path("/app/src/opengym_platform"),
        previous / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p003_coach.py", "p003_coach_jobs.py", "p002_media_gc.py", "p001_links.py"
        ),
    )
    await migration({**environment, "PYTHONPATH": str(previous)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_reset"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'),('B','Bob')"
    )
    await observer.execute(
        "INSERT INTO identity.device_links VALUES ($1,'A',now(),now()+interval '10 min')",
        DIGEST,
    )
    before = await observer.fetch("SELECT * FROM identity.device_links")
    await migration(environment, "up")
    await migration(environment, "up")
    assert await observer.fetch("SELECT * FROM identity.device_links") == before
    rows = await observer.fetch("""SELECT p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner,
        EXISTS(SELECT FROM aclexplode(p.proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='identity'
            AND p.proname IN ('lookup_device_link','finish_device_link')""")
    assert len(rows) == 2
    for row in rows:
        assert row["prosecdef"] and not row["public"]
        assert row["owner"] == "opengym_identity_executor" and row["proconfig"] == [
            "search_path=pg_catalog, pg_temp"
        ]
    assert await observer.fetchval(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='identity.device_links'::regclass"
    )
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    database = await Database.open_platform()
    try:
        assert await database.fetch("SELECT * FROM identity.device_links") == []
        assert (
            await database.fetch(
                "SELECT * FROM identity.lookup_device_link($1)", b"short"
            )
            == []
        )
        for sql in [
            "SET ROLE opengym_identity_executor",
            "UPDATE identity.device_links SET owner_id='B'",
            "CREATE TABLE identity.forbidden(id text)",
        ]:
            with pytest.raises(DatabaseError):
                await database.execute(sql)
        assert (
            await database.fetch(
                "SELECT * FROM identity.finish_device_link('A',$1,'forged',$2,0,'{}',NULL)",
                DIGEST,
                b"forged",
            )
            == []
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.passkeys") == 0
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_two_link_ceremonies_race_for_one_code_without_partial_passkeys(pending):
    observer, environment = pending
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        starts = [await start_link(client) for _ in range(2)]
        results = await asyncio.gather(
            *[
                client.post("/api/v1/device-link/verify", json=redemption(start, alg))
                for start, alg in zip(starts, ["ES256", "RS256"], strict=True)
            ]
        )
        assert sorted(r.status_code for r in results) == [200, 400]
        assert next(r for r in results if r.status_code == 400).json() == LINK_INVALID
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
        )
        == 1
    )
    assert await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
    assert (
        await observer.fetchval(
            "SELECT label FROM identity.passkeys WHERE owner_id='B'"
        )
        == "foreign"
    )


@pytest.mark.asyncio
async def test_sql_failure_rolls_back_new_passkey_and_code_then_fresh_ceremony_can_retry(
    pending,
):
    observer, environment = pending
    await observer.execute("""CREATE FUNCTION public.fail_link() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'private-link-marker'; END $$;
        CREATE TRIGGER fail_link BEFORE DELETE ON identity.device_links FOR EACH ROW EXECUTE FUNCTION public.fail_link();""")
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        start = await start_link(client)
        result = await client.post("/api/v1/device-link/verify", json=redemption(start))
        assert result.status_code == 500 and result.json() == {"error": "server error"}
        assert "set-cookie" not in result.headers
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            )
            == 0
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        await observer.execute("DROP TRIGGER fail_link ON identity.device_links")
        assert (
            await client.post("/api/v1/device-link/verify", json=redemption(start))
        ).json()["code"] == "challenge-expired"
        assert (
            await client.post(
                "/api/v1/device-link/verify", json=redemption(await start_link(client))
            )
        ).status_code == 200
