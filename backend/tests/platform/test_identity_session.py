"""Compatible sessions through real HTTP and restricted PostgreSQL."""

import asyncio
import base64
import hashlib
import hmac
import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server

from opengym_platform.core.database import Database
from opengym_platform.identity.service import profile
from opengym_platform.identity.sessions import authorize, verify

VECTORS = json.loads(
    (Path(__file__).parents[2] / "contracts/identity-sessions.v1.json").read_text()
)
SECRET, A, B, LEGACY = (VECTORS[key] for key in ("secret", "a", "b", "legacy"))


@pytest_asyncio.fixture
async def identities(deployment, tmp_path):
    observer, environment = deployment
    secret = tmp_path / "session_secret"
    secret.write_text(SECRET)
    environment["PLATFORM_SESSION_SECRET_FILE"] = str(secret)
    await migration(environment, "up")
    await observer.execute("""
        INSERT INTO identity.users(id, display_name, is_admin, session_version)
        VALUES ('A', 'Alice', false, 0), ('B', 'Bob', true, 3)
    """)
    return observer, environment


@pytest.mark.asyncio
async def test_verified_cookie_actor_reaches_only_own_profile(identities):
    _, environment = identities
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/me?owner_id=B",
            headers={
                "Cookie": f"gymsid={A}",
                "Authorization": f"Bearer {B}",
                "X-Owner-Id": "B",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"user": {"id": "A", "name": "Alice", "admin": False}}


@pytest.mark.asyncio
async def test_forged_owner_in_each_http_location_never_changes_actor(identities):
    observer, environment = identities
    async with server(environment) as client:
        for token, owner, foreign, name, admin in (
            (A, "A", "B", "Alice", False),
            (B, "B", "A", "Bob", True),
        ):
            for query, body, header in (
                (True, False, False),
                (False, True, False),
                (False, False, True),
                (True, True, True),
            ):
                response = await client.request(
                    "GET",
                    "/api/v1/me",
                    params={"owner_id": foreign} if query else {},
                    json={"owner_id": foreign} if body else None,
                    headers={
                        "Authorization": f"Bearer {token}",
                        **({"X-Owner-Id": foreign} if header else {}),
                    },
                )
                assert response.json() == {
                    "user": {"id": owner, "name": name, "admin": admin}
                }
        assert [
            tuple(row)
            for row in await observer.fetch(
                "SELECT id, session_version FROM identity.users ORDER BY id"
            )
        ] == [("A", 0), ("B", 3)]


def signed(payload):
    digest = hmac.digest(SECRET.encode(), payload.encode(), hashlib.sha256)
    return payload + "." + base64.urlsafe_b64encode(digest).decode().rstrip("=")


@pytest.mark.asyncio
@pytest.mark.parametrize("secure", [False, True])
async def test_cookie_bearer_selection_and_invalid_sessions(identities, secure):
    observer, environment = identities
    environment["ORIGIN"] = "https://gym.example" if secure else "http://localhost:8080"
    current = "__Host-gymsid" if secure else "gymsid"
    async with server(environment) as client:
        for own, other, owner, name, admin in (
            (A, B, "A", "Alice", False),
            (B, A, "B", "Bob", True),
        ):
            cases = [
                ("", own, owner),
                (f"{current}={own}", other, owner),
                (f"{current}={own}; {current}={own}", other, owner),
                (f"{current}={own}; {current}={other}", "", None),
                (f"{current}={other}; {current}={own}", "", None),
                (f"{current}={own}; {current}={other}", own, owner),
                (f"{current}={other}; {current}={own}", own, owner),
                (f"{current}=invalid", own, None),
                (f"{current}=", own, owner),
                (f"gymsid={own}", "", owner),
                (f"{current}={own}", "invalid", owner),
                ("", "invalid", None),
                (f"{current}=invalid", "invalid", None),
            ]
            if secure:
                cases += [
                    (f"gymsid={other}; {current}={own}", other, owner),
                    (f"{current}={own}; gymsid={other}", other, owner),
                    (f"{current}=invalid; gymsid={own}", own, None),
                    (f"{current}={own}; {current}={other}; gymsid={own}", "", None),
                ]
            else:
                cases += [(f"__Host-gymsid={other}", own, owner)]
            for cookie, bearer, expected in cases:
                response = await client.get(
                    "/api/v1/me?owner_id=forged",
                    headers={
                        "Cookie": cookie,
                        "Authorization": f"Bearer {bearer}" if bearer else "",
                        "X-Owner-Id": "forged",
                    },
                )
                assert response.status_code == (200 if expected else 401)
                assert response.json() == (
                    {"user": {"id": owner, "name": name, "admin": admin}}
                    if expected
                    else {"error": "not signed in"}
                )
                assert response.headers["cache-control"] == "no-store"
        for token in (LEGACY, signed("A:4102444800000:0")):
            assert (
                await client.get(
                    "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
                )
            ).status_code == 200
        for token in (
            signed("A:1:0"),
            signed("A:4102444800000:1"),
            signed("B:4102444800000"),
            signed("missing:4102444800000:0"),
            signed("A:NaN:0"),
            signed("A:Infinity:0"),
            signed("A:4102444800000:1.5"),
            signed("A:4102444800000:bad"),
            signed("A:4102444800000:-1"),
            A.replace("A:", "B:", 1),
            A[:-1] + "x",
        ):
            response = await client.get(
                "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401
        await observer.execute("UPDATE identity.users SET disabled=true WHERE id='A'")
        assert (
            await client.get("/api/v1/me", headers={"Cookie": f"{current}={A}"})
        ).status_code == 401
        await observer.execute("DELETE FROM identity.users WHERE id='B'")
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {B}"})
        ).status_code == 401


async def wait_for_actor_locks(observer, count):
    async with asyncio.timeout(2):
        while True:
            await observer.execute("SELECT pg_stat_clear_snapshot()")
            waiting = await observer.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE usename = 'opengym_api_runtime' AND wait_event_type = 'Lock'
                  AND query LIKE '%identity.lock_actor%'
            """)
            if waiting == count:
                return
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["version", "disabled", "deleted", "expiry", "valid"]
)
@pytest.mark.parametrize("bearer", [False, True])
async def test_actor_wait_revalidates_access_before_rls(identities, change, bearer):
    observer, environment = identities
    async with server(environment) as client:
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            expiry = await observer.fetchval(
                "SELECT clock_timestamp() + interval '1200 milliseconds'"
            )
            token = (
                signed(f"A:{int(expiry.timestamp() * 1000)}:0")
                if change == "expiry"
                else A
            )
            headers = (
                {"Authorization": f"Bearer {token}"}
                if bearer
                else {"Cookie": f"gymsid={token}"}
            )
            task = asyncio.create_task(client.get("/api/v1/me", headers=headers))
            await wait_for_actor_locks(observer, 1)
            if change == "version":
                await observer.execute(
                    "UPDATE identity.users SET session_version=1 WHERE id='A'"
                )
            elif change == "disabled":
                await observer.execute(
                    "UPDATE identity.users SET disabled=true WHERE id='A'"
                )
            elif change == "deleted":
                await observer.execute("DELETE FROM identity.users WHERE id='A'")
            elif change == "expiry":
                await observer.execute(
                    "SELECT pg_sleep(greatest(0, extract(epoch FROM ($1::timestamptz - clock_timestamp()))))",
                    expiry + timedelta(milliseconds=10),
                )
        response = await task
        assert response.status_code == (200 if change == "valid" else 401)
        if change != "valid":
            assert response.json() == {"error": "not signed in"}
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {B}"})
        ).json() == {"user": {"id": "B", "name": "Bob", "admin": True}}
        assert (await client.get("/api/v1/me")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("bearer", [False, True])
async def test_session_expires_while_waiting_for_pool(identities, bearer):
    observer, environment = identities
    async with server(environment) as client:
        blockers = []
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            blockers = [
                asyncio.create_task(
                    client.get("/api/v1/me", headers={"Cookie": f"gymsid={A}"})
                )
                for _ in range(4)
            ]
            await wait_for_actor_locks(observer, 4)
            expiry = await observer.fetchval(
                "SELECT clock_timestamp() + interval '700 milliseconds'"
            )
            token = signed(f"B:{int(expiry.timestamp() * 1000)}:3")
            sent = asyncio.Event()

            async def trace(event, info):
                if event == "http11.send_request_headers.complete":
                    sent.set()

            headers = (
                {"Authorization": f"Bearer {token}"}
                if bearer
                else {"Cookie": f"gymsid={token}"}
            )
            waiting = asyncio.create_task(
                client.get("/api/v1/me", headers=headers, extensions={"trace": trace})
            )
            await asyncio.wait_for(sent.wait(), 1)
            assert not waiting.done()
            await observer.execute(
                "SELECT pg_sleep(greatest(0, extract(epoch FROM ($1::timestamptz - clock_timestamp()))))",
                expiry + timedelta(milliseconds=10),
            )
        assert all(
            response.status_code == 200 for response in await asyncio.gather(*blockers)
        )
        assert (await waiting).status_code == 401
        assert (
            await client.get("/api/v1/me", headers={"Cookie": f"gymsid={B}"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_bearer_renewal_preserves_version_and_cookie_is_not_renewed(identities):
    observer, environment = identities
    expiry = await observer.fetchval("SELECT clock_timestamp() + interval '1 day'")
    token = signed(f"B:{int(expiry.timestamp() * 1000)}:3")
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
        result = response.json()
        renewed = result.pop("token")
        assert result == {"user": {"id": "B", "name": "Bob", "admin": True}}
        payload = renewed.rpartition(".")[0]
        assert signed(payload) == renewed
        owner, new_expiry, version = payload.split(":")
        assert (owner, version) == ("B", "3")
        assert int(new_expiry) > int(expiry.timestamp() * 1000)
        cookie = await client.get("/api/v1/me", headers={"Cookie": f"gymsid={token}"})
        assert cookie.json() == result and "set-cookie" not in cookie.headers
        await observer.execute(
            "UPDATE identity.users SET session_version=4 WHERE id='B'"
        )
        assert (
            await client.get(
                "/api/v1/me", headers={"Authorization": f"Bearer {renewed}"}
            )
        ).status_code == 401


@pytest.mark.asyncio
async def test_actor_lock_is_held_until_initiator_finishes_and_context_is_local(
    identities, monkeypatch
):
    observer, environment = identities
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()
    session = verify("", f"Bearer {A}", False, SECRET)
    try:
        async with database.transaction() as handle:
            assert await authorize(handle, session)
            assert [
                row["id"] for row in await handle.fetch("SELECT id FROM identity.users")
            ] == ["A"]
            assert (
                await handle.fetch("SELECT current_setting('app.owner_id') AS owner")
            )[0]["owner"] == "A"
            revoke = asyncio.create_task(
                observer.execute(
                    "UPDATE identity.users SET session_version=1 WHERE id='A'"
                )
            )
            async with asyncio.timeout(1):
                while not (
                    await handle.fetch(
                        "SELECT EXISTS (SELECT FROM pg_locks WHERE locktype='transactionid' AND NOT granted AND transactionid=pg_current_xact_id()::text::xid) AS waiting"
                    )
                )[0]["waiting"]:
                    await asyncio.sleep(0.01)
            assert not revoke.done()
        await revoke
        assert await profile(database, session, SECRET, 90) is None
        assert not (
            await database.fetch(
                "SELECT nullif(current_setting('app.owner_id', true), '') AS owner"
            )
        )[0]["owner"]
        assert await database.fetch("SELECT id FROM identity.users") == []
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_identity_acl_rls_and_public_count_are_bounded(identities):
    observer, environment = identities
    tables = await observer.fetch(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid IN ('identity.users'::regclass, 'identity.invitations'::regclass)"
    )
    assert len(tables) == 2 and all(
        row["relrowsecurity"] and row["relforcerowsecurity"] for row in tables
    )
    functions = await observer.fetch("""
        SELECT p.proname, p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner) AS owner,
            has_function_privilege('opengym_api_runtime', p.oid, 'EXECUTE') AS runtime,
            EXISTS (SELECT FROM aclexplode(p.proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='identity'
    """)
    assert {row["proname"] for row in functions} == {
        "lock_actor",
        "public_user_count",
        "lookup_password",
        "finish_password_login",
    }
    for row in functions:
        assert row["prosecdef"] and row["owner"] == "opengym_identity_executor"
        assert row["runtime"] and not row["public"]
        assert row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
    assert not await observer.fetchval(
        "SELECT pg_has_role('opengym_api_runtime','opengym_identity_executor','MEMBER')"
    )
    async with server(environment) as client:
        assert (await client.get("/api/v1/health")).json() == {
            "ok": True,
            "users": 2,
            "writable": True,
        }


@pytest.mark.asyncio
async def test_genuine_p000_upgrades_to_identity_without_changing_p000(
    deployment, tmp_path
):
    observer, environment = deployment
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        tmp_path / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p001_identity_session.py",
            "p001_password_login.py",
            "p002_training.py",
            "p002_training_write.py",
        ),
    )
    await migration({**environment, "PYTHONPATH": str(tmp_path)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p000_bootstrap"
    )
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p002_training_write"
    )


@pytest.mark.parametrize("fault", ["missing", "short", "symlink", "whitespace"])
def test_session_key_configuration_fails_closed_without_echoing_secrets(
    tmp_path, monkeypatch, fault
):
    from opengym_platform.core.platform_settings import load_session_secret

    secret = tmp_path / "key"
    secret.write_text(
        " " * 40 if fault == "whitespace" else SECRET if fault != "short" else "short"
    )
    if fault == "symlink":
        link = tmp_path / "link"
        link.symlink_to(secret)
        secret = link
    monkeypatch.setenv(
        "PLATFORM_SESSION_SECRET_FILE",
        str(secret) + ("-missing" if fault == "missing" else ""),
    )
    with pytest.raises(ValueError, match="^PLATFORM_SESSION_CONFIG_INVALID$"):
        load_session_secret()


@pytest.mark.asyncio
async def test_identity_migration_supplies_bounded_actor_lock(deployment):
    observer, environment = deployment
    await migration(environment, "up")
    assert (
        await observer.fetchval(
            "SELECT to_regprocedure('identity.lock_actor(text,bigint,timestamp with time zone)')"
        )
        is not None
    )


@pytest.mark.asyncio
async def test_missing_session_never_establishes_an_actor(deployment):
    _, environment = deployment
    async with server(environment) as client:
        response = await client.get("/api/v1/me", headers={"X-Owner-Id": "B"})
        assert response.status_code == 401
        assert response.json() == {"error": "not signed in"}
        assert response.headers["cache-control"] == "no-store"
