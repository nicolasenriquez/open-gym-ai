"""Own account changes through restricted HTTP and independent PostgreSQL."""

import asyncio
import base64
import shutil
import time
from pathlib import Path

import pytest
from test_identity_passkey import vector
from test_identity_password import HASH, PASSWORD
from test_identity_password import accounts as accounts  # noqa: PLC0414
from test_identity_session import SECRET, A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

from opengym_platform.identity.sessions import sign


@pytest.mark.asyncio
async def test_password_status_preserves_node_shape_and_owner(deployment):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    async with server(environment) as client:
        assert (await client.get("/api/v1/account/password")).status_code == 401
        registered = await client.post(
            "/api/v1/register/password",
            json={"name": "Alice", "password": "violet river stones"},
        )
        assert registered.status_code == 200
        result = await client.get(
            "/api/v1/account/password?owner=other", headers={"X-Owner-ID": "other"}
        )
        assert result.status_code == 200
        assert result.json() == {
            "set": True,
            "setAt": await observer.fetchval(
                "SELECT to_char(set_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"') FROM identity.password_credentials"
            ),
            "passkeys": 0,
            "name": "Alice",
            "nameTaken": False,
            "email": None,
        }
        assert result.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_password_change_requires_current_proof_and_reissues_only_caller(
    deployment,
):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    async with server(environment) as client:
        await client.post(
            "/api/v1/register/password",
            json={"name": "Alice", "password": "violet river stones"},
        )
        old = client.cookies.get("gymsid")
        body = {"next": "amber mountains sunlight"}
        assert (await client.post("/api/v1/account/password", json=body)).json() == {
            "error": "enter your current password",
            "code": "current-required",
        }
        wrong = await client.post(
            "/api/v1/account/password", json={**body, "current": "wrong"}
        )
        assert wrong.status_code == 403 and wrong.json()["code"] == "current-wrong"
        changed = await client.post(
            "/api/v1/account/password", json={**body, "current": "violet river stones"}
        )
        assert changed.status_code == 200 and changed.json() == {"ok": True}
        assert "HttpOnly" in changed.headers["set-cookie"]
        assert (await client.get("/api/v1/me")).status_code == 200
        assert (
            await client.get("/api/v1/me", headers={"Cookie": "gymsid=" + old})
        ).status_code == 401
        assert (
            await observer.fetchval("SELECT session_version FROM identity.users") == 1
        )
        assert (
            await client.post(
                "/api/v1/login/password",
                json={"name": "Alice", "password": "violet river stones"},
            )
        ).status_code == 401
        assert (
            await client.post(
                "/api/v1/login/password",
                json={"name": "Alice", "password": "amber mountains sunlight"},
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_first_password_accepts_fresh_own_passkey_and_preserves_it(deployment):
    observer, environment = deployment
    environment.update(
        PASSWORD_LOGIN="1", RP_ID="localhost", ORIGIN="http://localhost:8080"
    )
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        start = (
            await client.post("/api/v1/register/options", json={"name": "Alice"})
        ).json()
        created = await client.post(
            "/api/v1/register/verify",
            json={
                "cid": start["cid"],
                "credential": vector("ES256/register")["credential"],
            },
        )
        assert created.status_code == 200
        assert (
            await client.post(
                "/api/v1/account/password", json={"next": "violet river stones"}
            )
        ).json()["code"] == "passkey-required"
        proof = (await client.post("/api/v1/login/options")).json()
        response = await client.post(
            "/api/v1/account/password",
            json={
                "next": "violet river stones",
                "cid": proof["cid"],
                "credential": vector("ES256/assertion")["credential"],
            },
        )
        assert response.status_code == 200, response.text
        assert await observer.fetchval("SELECT count(*) FROM identity.passkeys") == 1
        assert await observer.fetchval("SELECT counter FROM identity.passkeys") == 1
        assert (await client.get("/api/v1/account/password")).json()["set"] is True
        replay = await client.post(
            "/api/v1/account/password",
            json={
                "next": "amber mountains sunlight",
                "cid": proof["cid"],
                "credential": vector("ES256/assertion")["credential"],
            },
        )
        assert replay.status_code == 403 and replay.json()["code"] == "passkey"


@pytest.mark.asyncio
async def test_email_claims_require_proof_keep_password_name_and_release_only_expired(
    deployment,
):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    await observer.execute("""
        INSERT INTO identity.users(id,display_name) VALUES ('foreign','Other');
        INSERT INTO identity.login_aliases VALUES
            ('occupied@example.test','foreign',true,false,NULL),
            ('expired@example.test','foreign',false,false,clock_timestamp()-interval '1 day');
    """)
    async with server(environment) as client:
        await client.post(
            "/api/v1/register/password",
            json={"name": "alice@example.test", "password": "violet river stones"},
        )
        old = client.cookies.get("gymsid")
        missing = await client.post(
            "/api/v1/account/email", json={"email": "new@example.test"}
        )
        assert (
            missing.status_code == 403 and missing.json()["code"] == "current-required"
        )
        invalid = await client.post(
            "/api/v1/account/email", json={"email": "not-email"}
        )
        assert invalid.status_code == 400 and invalid.json()["code"] == "email-invalid"
        taken = await client.post(
            "/api/v1/account/email",
            json={"email": "occupied@example.test", "current": "violet river stones"},
        )
        assert taken.status_code == 409 and taken.json()["code"] == "email-taken"
        for email in ("alice@example.test", "expired@example.test"):
            response = await client.post(
                "/api/v1/account/email",
                json={
                    "email": email.upper(),
                    "current": "violet river stones",
                    "owner": "foreign",
                },
            )
            assert response.status_code == 200 and response.json() == {
                "ok": True,
                "email": email,
            }
            assert "set-cookie" not in response.headers
        assert (await client.get("/api/v1/account/password")).json()[
            "email"
        ] == "expired@example.test"
        removed = await client.request(
            "DELETE", "/api/v1/account/email", json={"current": "violet river stones"}
        )
        assert removed.status_code == 200 and removed.json() == {
            "ok": True,
            "email": None,
        }
        assert (
            await client.request("DELETE", "/api/v1/account/email", json={})
        ).status_code == 200
        assert (
            await client.get("/api/v1/me", headers={"Cookie": "gymsid=" + old})
        ).status_code == 200
        aliases = await observer.fetch(
            "SELECT * FROM identity.login_aliases ORDER BY alias_key"
        )
        assert [
            (a["alias_key"], a["email_claim"], a["password_name_claim"])
            for a in aliases
        ] == [
            ("alice@example.test", False, True),
            ("occupied@example.test", True, False),
        ]


@pytest.mark.asyncio
async def test_password_removal_never_removes_last_way_or_revokes_session_and_email(
    deployment,
):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    async with server(environment) as client:
        created = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Alice",
                "password": "violet river stones",
                "email": "alice@example.test",
            },
        )
        owner = created.json()["user"]["id"]
        last = await client.request("DELETE", "/api/v1/account/password", json={})
        assert last.status_code == 409 and last.json()["code"] == "last-way-in"
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ('synthetic-key',$1,$2,0,'{}',NULL,NULL,NULL)",
            owner,
            b"synthetic-unused-key",
        )
        missing = await client.request("DELETE", "/api/v1/account/password", json={})
        assert (
            missing.status_code == 403 and missing.json()["code"] == "current-required"
        )
        removed = await client.request(
            "DELETE",
            "/api/v1/account/password",
            json={"current": "violet river stones"},
        )
        assert removed.status_code == 200 and removed.json() == {"ok": True}
        assert (await client.get("/api/v1/me")).status_code == 200
        assert (
            await client.request("DELETE", "/api/v1/account/password", json={})
        ).status_code == 200
        status = (await client.get("/api/v1/account/password")).json()
        assert (
            status["set"] is False
            and status["setAt"] is None
            and status["email"] == "alice@example.test"
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.password_credentials"
            )
            == 0
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.passkeys") == 1
        aliases = await observer.fetch(
            "SELECT alias_key,email_claim,password_name_claim FROM identity.login_aliases"
        )
        assert [tuple(a.values()) for a in aliases] == [
            ("alice@example.test", True, False)
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("secure", [False, True])
async def test_logout_all_exists_with_password_mode_off_ignores_body_and_revokes_only_actor(
    identities, secure
):
    observer, environment = identities
    environment.update(
        PASSWORD_LOGIN="0",
        ORIGIN="https://gym.test" if secure else "http://localhost:8080",
    )
    await observer.execute("""
        INSERT INTO identity.device_links VALUES (decode(repeat('ab',32),'hex'),'A',now(),now()+interval '10 min'),
            (decode(repeat('cd',32),'hex'),'B',now(),now()+interval '10 min');
        INSERT INTO identity.password_resets VALUES ('A',decode(repeat('ef',32),'hex'),now()+interval '1 day','historical');
        INSERT INTO identity.passkeys VALUES ('key','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL);
    """)
    cookie = ("__Host-gymsid=" if secure else "gymsid=") + A
    async with server(environment) as client:
        assert (await client.post("/api/v1/logout/all")).status_code == 401
        response = await client.post(
            "/api/v1/logout/all?owner=B",
            content="{",
            headers={
                "Cookie": cookie,
                "Authorization": "Bearer " + B,
                "X-Owner-ID": "B",
            },
        )
        assert response.status_code == 200 and response.json() == {"ok": True}
        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == (2 if secure else 1)
        assert all("Max-Age=0" in c and "HttpOnly" in c for c in cookies)
        assert (
            await client.get("/api/v1/me", headers={"Cookie": cookie})
        ).status_code == 401
        client.cookies.clear()
        assert (
            await client.get("/api/v1/me", headers={"Authorization": "Bearer " + B})
        ).status_code == 200
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 1
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.device_links WHERE owner_id='A'"
            )
            == 0
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.device_links WHERE owner_id='B'"
            )
            == 1
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.passkeys") == 1
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.password_resets")
            == 1
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ["valid", "hash", "version", "disabled", "deleted", "last-key", "expire"],
)
async def test_crypto_wait_holds_no_lease_and_revalidates_access_and_last_way(
    accounts, tmp_path, mutation
):
    observer, environment = accounts
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "account_boundary.py").write_text(f"""
import time
from pathlib import Path
from opengym_platform.identity import passwords
from opengym_platform.application import create_app
original = passwords.derive
def derive(password, material):
    if password == {PASSWORD!r}:
        Path({str(entered)!r}).touch()
        deadline = time.monotonic()+8
        while not Path({str(release)!r}).exists():
            if time.monotonic()>deadline:
                raise ValueError("synthetic crypto deadline")
            time.sleep(.01)
    return original(password,material)
passwords.derive = derive
""")
    environment["PYTHONPATH"] = str(tmp_path) + ":/app/src"
    removing = mutation == "last-key"
    if removing:
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ('key','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL)"
        )
    async with server(environment, factory="account_boundary:create_app") as client:
        expires = int(time.time() * 1000) + 3000
        token = sign(f"A:{expires}:0", SECRET) if mutation == "expire" else A
        task = asyncio.create_task(
            client.request(
                "DELETE" if removing else "POST",
                "/api/v1/account/password",
                headers={"Authorization": "Bearer " + token},
                json={"next": "amber mountains sunlight", "current": PASSWORD},
                timeout=10,
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
                "hash": "UPDATE identity.password_credentials SET scrypt_hash='replaced' WHERE owner_id='A'",
                "version": "UPDATE identity.users SET session_version=1 WHERE id='A'",
                "disabled": "UPDATE identity.users SET disabled=true WHERE id='A'",
                "deleted": "DELETE FROM identity.users WHERE id='A'",
                "last-key": "DELETE FROM identity.passkeys",
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
        response = await task
        assert response.status_code == (
            200
            if mutation == "valid"
            else 403
            if mutation == "hash"
            else 409
            if removing
            else 401
        ), response.text
        assert "set-cookie" not in response.headers
        assert (
            await observer.fetchval(
                "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='B'"
            )
            == HASH
        )
        assert (
            await client.get("/api/v1/me", headers={"Authorization": "Bearer " + B})
        ).status_code == 200
        if mutation == "valid":
            assert "token" in response.json()
            assert (
                await client.get(
                    "/api/v1/me",
                    headers={"Authorization": "Bearer " + response.json()["token"]},
                )
            ).status_code == 200
            assert (
                await client.get("/api/v1/me", headers={"Authorization": "Bearer " + A})
            ).status_code == 401
        elif mutation not in {"hash", "deleted"}:
            assert (
                await observer.fetchval(
                    "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='A'"
                )
                == HASH
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("email,expected", [("\ufeff", 200), ("\u0085", 400)])
async def test_email_removal_uses_ecmascript_whitespace(accounts, email, expected):
    _, environment = accounts
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/account/email",
            headers={"Authorization": "Bearer " + A},
            json={"email": email, "current": PASSWORD},
        )
        assert response.status_code == expected, response.text
        assert response.json() == (
            {"ok": True, "email": None}
            if expected == 200
            else {"error": "that is not an e-mail address", "code": "email-invalid"}
        )


@pytest.mark.asyncio
async def test_empty_stored_hash_still_requires_proof_not_a_new_first_password(
    accounts,
):
    observer, environment = accounts
    await observer.execute(
        "UPDATE identity.password_credentials SET scrypt_hash='' WHERE owner_id='A'"
    )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/account/password",
            headers={"Authorization": "Bearer " + A},
            json={"next": "amber mountains sunlight", "current": "wrong"},
        )
        assert (
            response.status_code == 403 and response.json()["code"] == "current-wrong"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("proof", ["foreign", "signature", "bad-object"])
async def test_stepup_never_accepts_foreign_or_invalid_credentials(identities, proof):
    observer, environment = identities
    environment.update(
        PASSWORD_LOGIN="1", RP_ID="localhost", ORIGIN="http://localhost:8080"
    )
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    for algorithm, owner in [("ES256", "A"), ("RS256", "B")]:
        case = vector(algorithm + "/assertion")
        await observer.execute(
            "INSERT INTO identity.passkeys VALUES ($1,$2,$3,0,'{}',NULL,NULL,NULL)",
            case["credentialId"],
            owner,
            base64.urlsafe_b64decode(case["publicKey"] + "=="),
        )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        cid = (await client.post("/api/v1/login/options")).json()["cid"]
        raw = (
            {}
            if proof == "bad-object"
            else vector("RS256/assertion" if proof == "foreign" else "ES256/signature")[
                "credential"
            ]
        )
        response = await client.post(
            "/api/v1/account/password",
            headers={"Authorization": "Bearer " + A},
            json={
                "next": "violet river stones",
                "cid": cid,
                "credential": raw,
                "current": PASSWORD,
            },
        )
        assert response.status_code == 403 and response.json()["code"] == "passkey"
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.password_credentials"
            )
            == 0
        )
        assert (
            await observer.fetchval("SELECT sum(counter) FROM identity.passkeys") == 0
        )
        replay = await client.post(
            "/api/v1/login/verify",
            json={"cid": cid, "credential": vector("ES256/assertion")["credential"]},
        )
        assert (
            replay.status_code == 400 and replay.json()["code"] == "challenge-expired"
        )


@pytest.mark.asyncio
async def test_concurrent_email_claims_have_one_owner_without_revocation(accounts):
    observer, environment = accounts
    async with server(environment) as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/account/email",
                    headers={"Authorization": "Bearer " + token},
                    json={"email": "ＳＨＡＲＥＤ@example.test", "current": PASSWORD},
                )
                for token in (A, B)
            ]
        )
        assert sorted(r.status_code for r in responses) == [200, 409]
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.login_aliases WHERE alias_key='shared@example.test'"
            )
            == 1
        )
        assert (
            await observer.fetchval("SELECT sum(session_version) FROM identity.users")
            == 3
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.password_credentials"
            )
            == 2
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["email", "password", "future", "expired"])
async def test_only_expired_temporary_foreign_alias_can_be_reclaimed(accounts, purpose):
    observer, environment = accounts
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('C','held@example.test')"
    )
    await observer.execute(
        """INSERT INTO identity.login_aliases VALUES
        ('held@example.test','C',$1,$2,CASE WHEN $3 THEN clock_timestamp()+interval '1 day' WHEN $4 THEN clock_timestamp()-interval '1 day' END)
        """,
        purpose == "email",
        purpose == "password",
        purpose == "future",
        purpose == "expired",
    )
    if purpose == "password":
        await observer.execute(
            "INSERT INTO identity.password_credentials VALUES ('C',$1,NULL)", HASH
        )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/account/email",
            headers={"Authorization": "Bearer " + A},
            json={"email": "held@example.test", "current": PASSWORD},
        )
        assert response.status_code == (200 if purpose == "expired" else 409), (
            response.text
        )
        assert await observer.fetchval(
            "SELECT owner_id FROM identity.login_aliases WHERE alias_key='held@example.test'"
        ) == ("A" if purpose == "expired" else "C")


@pytest.mark.asyncio
async def test_failed_password_change_rolls_back_claim_reset_link_and_version_then_retries(
    accounts,
):
    observer, environment = accounts
    await observer.execute("""
        INSERT INTO identity.device_links VALUES (decode(repeat('ab',32),'hex'),'A',now(),now()+interval '10 min');
        INSERT INTO identity.password_resets VALUES ('A',decode(repeat('cd',32),'hex'),now()+interval '1 day','historic');
        CREATE FUNCTION public.fail_account() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'private-account-marker'; END $$;
        CREATE TRIGGER fail_account BEFORE UPDATE OF session_version ON identity.users FOR EACH ROW EXECUTE FUNCTION public.fail_account();
    """)
    async with server(environment) as client:
        body = {"current": PASSWORD, "next": "amber mountains sunlight"}
        failed = await client.post(
            "/api/v1/account/password",
            headers={"Authorization": "Bearer " + A},
            json=body,
        )
        assert failed.status_code == 500 and failed.json() == {"error": "server error"}
        assert "set-cookie" not in failed.headers
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 0
        )
        assert (
            await observer.fetchval(
                "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='A'"
            )
            == HASH
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.password_resets")
            == 1
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        await observer.execute("DROP TRIGGER fail_account ON identity.users")
        retry = await client.post(
            "/api/v1/account/password",
            headers={"Authorization": "Bearer " + A},
            json=body,
        )
        assert retry.status_code == 200 and "token" in retry.json()
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.password_resets")
            == 0
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )


@pytest.mark.asyncio
async def test_account_transport_preserves_csrf_bearer_limits_and_json(accounts):
    _, environment = accounts
    routes = [
        ("GET", "/account/password"),
        ("POST", "/account/password"),
        ("DELETE", "/account/password"),
        ("POST", "/account/email"),
        ("DELETE", "/account/email"),
        ("POST", "/logout/all"),
    ]
    async with server(environment) as client:
        for method, path in routes:
            response = await client.request(
                method,
                "/api/v1" + path,
                headers={"Cookie": "gymsid=" + A, "Origin": "https://foreign.test"},
            )
            assert response.status_code == (200 if method == "GET" else 403)
            if method != "GET":
                assert response.json() == {"error": "cross-origin request refused"}
            response = await client.request(method, "/api/v1" + path)
            assert response.status_code == 401
        headers = {"Authorization": "Bearer " + A, "Origin": "https://foreign.test"}
        assert (
            await client.get("/api/v1/account/password", headers=headers)
        ).status_code == 200
        for raw, expected in [
            ("{", 400),
            ('{"bad":NaN}', 400),
            ("x" * (5 * 1024 * 1024 + 1), 413),
        ]:
            assert (
                await client.post(
                    "/api/v1/account/password", headers=headers, content=raw
                )
            ).status_code == expected
        assert (
            await client.request(
                "GET", "/api/v1/account/password", headers=headers, content="{"
            )
        ).status_code == 200
    environment["PASSWORD_LOGIN"] = "0"
    async with server(environment) as client:
        for method, path in routes[:-1]:
            assert (
                await client.request(method, "/api/v1" + path, headers=headers)
            ).status_code == 404


@pytest.mark.asyncio
async def test_new_revision_preserves_previous_history_and_uses_restricted_owner_access(
    deployment, tmp_path, monkeypatch
):
    from opengym_platform.core.database import Database, DatabaseError
    from opengym_platform.identity.sessions import authorize, verify

    observer, environment = deployment
    original = Path("/app/src/opengym_platform")
    previous = tmp_path / "previous"
    shutil.copytree(
        original,
        previous / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p003_coach.py",
            "p003_coach_jobs.py",
            "p002_media_gc.py",
            "p001_links.py",
            "p001_reset.py",
            "p001_passkey_manage.py",
            "p001_account.py",
        ),
    )
    await migration({**environment, "PYTHONPATH": str(previous)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_passkey"
    )
    await observer.execute("""
        INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'),('B','Bob');
        INSERT INTO identity.login_aliases VALUES ('protected','B',true,false,NULL),
            ('expired','B',false,false,clock_timestamp()-interval '1 day');
    """)
    before = [
        dict(row)
        for row in await observer.fetch("SELECT * FROM identity.users ORDER BY id")
    ]
    await migration(environment, "up")
    await migration(environment, "up")
    assert [
        dict(row)
        for row in await observer.fetch("SELECT * FROM identity.users ORDER BY id")
    ] == before
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p003_coach_jobs"
    )
    functions = await observer.fetch("""
        SELECT p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner,
            has_function_privilege('opengym_api_runtime',p.oid,'EXECUTE') AS runtime,
            EXISTS(SELECT FROM aclexplode(p.proacl) a WHERE a.grantee=0) AS public
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='identity' AND p.proname IN ('alias_available','release_expired_alias')
    """)
    assert len(functions) == 2
    for row in functions:
        assert row["prosecdef"] and row["runtime"] and not row["public"]
        assert row["owner"] == "opengym_identity_executor" and row["proconfig"] == [
            "search_path=pg_catalog, pg_temp"
        ]
    for table in ("password_resets", "device_links", "login_aliases", "passkeys"):
        assert await observer.fetchval(
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=$1::regclass",
            "identity." + table,
        )
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()
    try:
        assert not (
            await database.fetch(
                "SELECT identity.alias_available('protected') AS available"
            )
        )[0]["available"]
        await database.execute("SELECT identity.release_expired_alias('expired')")
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.login_aliases") == 2
        )
        for sql in (
            "SET ROLE opengym_identity_executor",
            "SELECT * FROM identity.password_resets",
            "INSERT INTO identity.device_links(owner_id) VALUES ('A')",
            "UPDATE identity.users SET is_admin=true",
        ):
            with pytest.raises(DatabaseError):
                await database.execute(sql)
        session = verify("gymsid=" + A, "", False, SECRET)
        async with database.transaction() as handle:
            await handle.execute("SELECT pg_advisory_xact_lock(728323)")
            assert await authorize(handle, session)
            assert await handle.fetch("SELECT * FROM identity.login_aliases") == []
            assert not (
                await handle.fetch(
                    "SELECT identity.alias_available('protected') AS available"
                )
            )[0]["available"]
            await handle.execute("SELECT identity.release_expired_alias('protected')")
            await handle.execute("SELECT identity.release_expired_alias('expired')")
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.login_aliases") == 1
        )
        assert await database.fetch("SELECT id FROM identity.users") == []
        assert not (
            await database.fetch(
                "SELECT nullif(current_setting('app.owner_id',true),'') AS owner"
            )
        )[0]["owner"]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_proof_and_email_collision_budgets_do_not_block_noops_or_password_login(
    accounts,
):
    _, environment = accounts
    environment["TRUST_PROXY"] = "1"
    async with server(environment) as client:
        for i in range(6):
            response = await client.post(
                "/api/v1/account/password",
                headers={
                    "Authorization": "Bearer " + A,
                    "X-Forwarded-For": f"198.51.100.{i + 1}",
                },
                json={"current": "wrong", "next": "amber mountains sunlight"},
            )
            assert response.status_code == 403
        paused = await client.post(
            "/api/v1/login/password", json={"name": "alice", "password": PASSWORD}
        )
        assert paused.status_code == 429 and paused.json()["retryAfter"] > 0
        assert (
            await client.request(
                "DELETE",
                "/api/v1/account/password",
                headers={"Authorization": "Bearer " + A},
                json={},
            )
        ).json()["code"] == "last-way-in"
        # B's independent password still works; its email-collision budget is separate.
        for i in range(21):
            response = await client.post(
                "/api/v1/account/email",
                headers={
                    "Authorization": "Bearer " + B,
                    "X-Forwarded-For": f"203.0.113.{i + 1}",
                },
                json={"email": "a@example.test", "current": PASSWORD},
            )
            assert response.status_code == 409
        headers = {"Authorization": "Bearer " + B, "X-Forwarded-For": "192.0.2.1"}
        paused = await client.post(
            "/api/v1/account/email",
            headers=headers,
            json={"email": "free@example.test", "current": PASSWORD},
        )
        assert paused.status_code == 429
        assert (
            await client.request(
                "DELETE", "/api/v1/account/email", headers=headers, json={}
            )
        ).status_code == 200
        assert (
            await client.post(
                "/api/v1/login/password",
                headers={"X-Forwarded-For": "192.0.2.2"},
                json={"name": "bob", "password": PASSWORD},
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_status_detects_foreign_email_without_password_and_keeps_null_dates(
    identities,
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute("""
        UPDATE identity.users SET display_name='shared@example.test' WHERE id='A';
        INSERT INTO identity.login_aliases VALUES ('shared@example.test','B',true,false,NULL);
    """)
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/account/password", headers={"Authorization": "Bearer " + A}
        )
        assert response.status_code == 200 and response.json() == {
            "set": False,
            "setAt": None,
            "name": "shared@example.test",
            "nameTaken": True,
            "passkeys": 0,
            "email": None,
        }
        refusal = await client.post(
            "/api/v1/account/password",
            headers={"Authorization": "Bearer " + A},
            json={"next": "violet river stones"},
        )
        assert refusal.status_code == 409 and refusal.json()["code"] == "name-taken"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["owner", "counter"])
async def test_passkey_proof_changed_during_crypto_rolls_back_counter_and_creates_no_password(
    identities, tmp_path, mutation
):
    observer, environment = identities
    environment.update(
        PASSWORD_LOGIN="1", RP_ID="localhost", ORIGIN="http://localhost:8080"
    )
    await observer.execute("UPDATE identity.users SET session_version=0 WHERE id='B'")
    case = vector("ES256/assertion")
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ($1,'A',$2,0,'{}',NULL,NULL,NULL)",
        case["credentialId"],
        base64.urlsafe_b64decode(case["publicKey"] + "=="),
    )
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "passkey_boundary.py").write_text(f"""
import time
from pathlib import Path
from opengym_platform.identity import account
from test_identity_passkey import fixed_challenge_app
original=account.verify_authentication_response
def verify(**kwargs):
    Path({str(entered)!r}).touch()
    deadline=time.monotonic()+8
    while not Path({str(release)!r}).exists():
        if time.monotonic()>deadline:
            raise ValueError("synthetic crypto deadline")
        time.sleep(.01)
    return original(**kwargs)
account.verify_authentication_response=verify
def create_app():
    return fixed_challenge_app()
""")
    environment["PYTHONPATH"] = (
        str(tmp_path) + ":" + str(Path(__file__).parent) + ":/app/src"
    )
    async with server(environment, factory="passkey_boundary:create_app") as client:
        cid = (await client.post("/api/v1/login/options")).json()["cid"]
        task = asyncio.create_task(
            client.post(
                "/api/v1/account/password",
                headers={"Authorization": "Bearer " + A},
                json={
                    "next": "violet river stones",
                    "cid": cid,
                    "credential": case["credential"],
                },
                timeout=10,
            )
        )
        try:
            async with asyncio.timeout(4):
                while not entered.exists():
                    await asyncio.sleep(0.01)
            assert not await observer.fetchval(
                "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND xact_start IS NOT NULL)"
            )
            await observer.execute(
                "UPDATE identity.passkeys SET "
                + ("owner_id='B'" if mutation == "owner" else "counter=2")
            )
        finally:
            release.touch()
        response = await task
        assert response.status_code == 403 and response.json()["code"] == "passkey"
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.password_credentials"
            )
            == 0
        )
        assert await observer.fetchval("SELECT counter FROM identity.passkeys") == (
            0 if mutation == "owner" else 2
        )


@pytest.mark.asyncio
async def test_stale_password_proof_cannot_clear_new_password_failure_budget(
    accounts, tmp_path
):
    observer, environment = accounts
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    case = vector("ES256/assertion")
    await observer.execute(
        "INSERT INTO identity.passkeys VALUES ($1,'A',$2,0,'{}',NULL,NULL,NULL)",
        case["credentialId"],
        base64.urlsafe_b64decode(case["publicKey"] + "=="),
    )
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "budget_boundary.py").write_text(f"""
import time
from pathlib import Path
from opengym_platform.identity import passwords
from test_identity_passkey import fixed_challenge_app
original=passwords.derive
def derive(password,material):
    if password=={PASSWORD!r}:
        Path({str(entered)!r}).touch()
        deadline=time.monotonic()+12
        while not Path({str(release)!r}).exists():
            if time.monotonic()>deadline:
                raise ValueError("synthetic crypto deadline")
            time.sleep(.01)
    return original(password,material)
passwords.derive=derive
def create_app():
    return fixed_challenge_app()
""")
    environment["PYTHONPATH"] = (
        str(tmp_path) + ":" + str(Path(__file__).parent) + ":/app/src"
    )
    async with server(environment, factory="budget_boundary:create_app") as client:
        old = asyncio.create_task(
            client.post(
                "/api/v1/account/email",
                headers={"Authorization": "Bearer " + A},
                json={"email": "new@example.test", "current": PASSWORD},
                timeout=15,
            )
        )
        try:
            async with asyncio.timeout(4):
                while not entered.exists():
                    await asyncio.sleep(0.01)
            cid = (await client.post("/api/v1/login/options")).json()["cid"]
            changed = await client.post(
                "/api/v1/account/password",
                headers={"Authorization": "Bearer " + A},
                json={
                    "next": "amber mountains sunlight",
                    "cid": cid,
                    "credential": case["credential"],
                },
                timeout=5,
            )
            assert changed.status_code == 200, changed.text
            token = changed.json()["token"]
            for _ in range(6):
                failed = await client.post(
                    "/api/v1/account/password",
                    headers={"Authorization": "Bearer " + token},
                    json={"next": "another violet sunrise", "current": "wrong"},
                )
                assert failed.status_code == 403
        finally:
            release.touch()
        assert (await old).status_code == 401
        paused = await client.post(
            "/api/v1/login/password",
            json={"name": "alice", "password": "amber mountains sunlight"},
        )
        assert paused.status_code == 429, paused.text


@pytest.mark.asyncio
async def test_mixed_password_signup_and_email_routes_share_node_burst_budget(accounts):
    _, environment = accounts
    async with server(environment) as client:
        routes = [
            ("/api/v1/account/password", {"next": "short"}),
            ("/api/v1/account/email", {"email": "bad"}),
            ("/api/v1/register/password", {}),
        ]
        headers = {"Authorization": "Bearer " + A}
        for i in range(60):
            path, body = routes[i % 3]
            response = await client.post(path, headers=headers, json=body)
            assert response.status_code == 400
        response = await client.post(
            "/api/v1/account/password", headers=headers, json={"next": "short"}
        )
        assert response.status_code == 429, response.text
        assert int(response.headers["retry-after"]) > 0
