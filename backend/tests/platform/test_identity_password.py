"""Password compatibility at the approved real HTTP/PostgreSQL seam."""

import asyncio
import json
import shutil
import threading
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server

from opengym_platform.core.database import Database, DatabaseError
from opengym_platform.identity.passwords import (
    BusyError,
    Passwords,
    identifier_text,
    name_key,
)

VECTORS = json.loads(
    (Path(__file__).parents[2] / "contracts/identity-passwords.v1.json").read_text()
)
HASH = VECTORS["vectors"][0]["hash"]
PASSWORD = VECTORS["vectors"][0]["password"]


@pytest_asyncio.fixture
async def accounts(identities):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute(
        "INSERT INTO identity.password_credentials(owner_id,scrypt_hash) VALUES ('A',$1),('B',$1)",
        HASH,
    )
    await observer.execute("""INSERT INTO identity.login_aliases VALUES
        ('alice','A',false,true,NULL), ('a@example.test','A',true,false,NULL),
        ('bob','B',false,true,NULL)""")
    return identities


@pytest.mark.asyncio
async def test_identity_routes_keep_factory_configuration_and_collaborators_local(
    monkeypatch,
):
    from opengym_platform.application import create_app
    from opengym_platform.identity.sessions import sign

    calls = []

    async def login(database, passwords, throttle, address, body, secret, days):
        calls.append((database, passwords, throttle, secret, days))
        return 200, {"user": {"id": "A"}}, "synthetic-token"

    async def read_profile(database, session, secret, days):
        return {"user": {"id": session.owner}}

    monkeypatch.setattr("opengym_platform.identity.router.login_password", login)
    monkeypatch.setattr("opengym_platform.identity.router.profile", read_profile)
    monkeypatch.setattr(
        "opengym_platform.application.load_public_config",
        lambda: {"password_login": True},
    )
    monkeypatch.setattr(
        "opengym_platform.application.load_session_secret", lambda: "a" * 32
    )
    monkeypatch.setenv("ORIGIN", "http://localhost:8080")
    monkeypatch.setenv("SESSION_DAYS", "2")
    first = create_app()
    first.state.database = object()

    monkeypatch.setattr(
        "opengym_platform.application.load_session_secret", lambda: "b" * 32
    )
    monkeypatch.setenv("ORIGIN", "https://gym.example")
    monkeypatch.setenv("SESSION_DAYS", "4")
    second = create_app()
    second.state.database = object()

    monkeypatch.setattr("opengym_platform.application.load_public_config", dict)
    disabled = create_app()
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=first), base_url="http://test"
        ) as a,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second), base_url="http://test"
        ) as b,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=disabled), base_url="http://test"
        ) as off,
    ):
        for client in (a, b, a):
            response = await client.post("/api/v1/login/password", json={})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            cookies = response.headers.get_list("set-cookie")
            if client is a:
                assert len(cookies) == 1
                assert cookies[0].startswith("gymsid=synthetic-token;")
                assert "Max-Age=172800;" in cookies[0]
                assert "; Secure;" not in cookies[0]
            else:
                assert len(cookies) == 2
                assert cookies[0].startswith("__Host-gymsid=synthetic-token;")
                assert "Max-Age=345600;" in cookies[0]
                assert "; Secure;" in cookies[0]
        assert calls[0] == calls[2]
        assert calls[0][0] is first.state.database
        assert calls[1][0] is second.state.database
        assert calls[0][1] is not calls[1][1]
        assert calls[0][2] is not calls[1][2]
        assert calls[0][3:] == ("a" * 32, 2)
        assert calls[1][3:] == ("b" * 32, 4)
        a.cookies.clear()
        b.cookies.clear()
        token = sign("A:4102444800000:0", "a" * 32)
        assert (
            await a.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        ).json() == {"user": {"id": "A"}}
        assert (
            await b.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        ).status_code == 401
        for path in ("/api/v1/me/", "/api/v1/login/password/"):
            response = await a.request("GET" if path == "/api/v1/me/" else "POST", path)
            assert response.status_code == 404
            assert "location" not in response.headers
        response = await off.post("/api/v1/login/password", json={})
        assert response.status_code == 404
        assert response.json() == {"error": "not found"}


@pytest.mark.asyncio
async def test_node_scrypt_and_unicode_vectors():
    passwords = Passwords()
    await passwords.warm_up()
    for vector in VECTORS["vectors"]:
        assert (
            await passwords.verify(vector["password"], vector["hash"])
            is vector["matches"]
        )
    for vector in VECTORS["aliases"]:
        assert name_key(vector["input"]) == vector["key"]
    for vector in VECTORS["identifiers"]:
        assert identifier_text(vector["input"]) == vector["text"]
    for malformed in (
        None,
        "",
        "not-scrypt",
        HASH.replace("ln=15", "ln=99"),
        HASH.replace("r=8", "r=99"),
    ):
        assert not await passwords.verify(PASSWORD, malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize("secure", [False, True])
async def test_login_cookie_and_bearer_reach_same_account(accounts, secure):
    _, environment = accounts
    environment["ORIGIN"] = "https://gym.example" if secure else "http://localhost:8080"
    async with server(environment) as client:
        for field, value in (
            ("identifier", " ＡＬＩＣＥ "),
            ("name", "Alice"),
            ("email", " A@EXAMPLE.TEST "),
        ):
            response = await client.post(
                "/api/v1/login/password",
                json={field: value, "password": PASSWORD, "owner_id": "B"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "user": {"id": "A", "name": "Alice", "admin": False}
            }
            assert response.headers["cache-control"] == "no-store"
            cookies = response.headers.get_list("set-cookie")
            assert len(cookies) == (2 if secure else 1)
            cookie = cookies[0]
            assert cookie.startswith("__Host-gymsid=" if secure else "gymsid=")
            assert cookie.endswith(
                "; Path=/; Max-Age=7776000; HttpOnly;"
                + (" Secure;" if secure else "")
                + " SameSite=Lax"
            )
            token = cookie.split(";", 1)[0].split("=", 1)[1]
            assert (
                await client.get(
                    "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
                )
            ).json() == response.json()
            assert (
                await client.get(
                    "/api/v1/me", headers={"Cookie": cookie.split(";", 1)[0]}
                )
            ).json() == response.json()
            if secure:
                assert (
                    cookies[1]
                    == "gymsid=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
                )


@pytest.mark.asyncio
async def test_login_rejects_sibling_origin(accounts):
    _, environment = accounts
    environment["ORIGIN"] = "https://gym.example"
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/login/password",
            json={"name": "alice", "password": PASSWORD},
            headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "same-site"},
        )
        assert response.status_code == 403
        assert response.json() == {"error": "cross-origin request refused"}
        assert "set-cookie" not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["hash", "version", "disabled", "deleted", "alias", "valid"]
)
async def test_credentials_rechecked_after_crypto_and_owner_lock(accounts, change):
    observer, environment = accounts
    async with server(environment) as client:
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            task = asyncio.create_task(
                client.post(
                    "/api/v1/login/password",
                    json={"name": "alice", "password": PASSWORD},
                )
            )
            async with asyncio.timeout(2):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%finish_password_login%'"
                    ):
                        break
                    await asyncio.sleep(0.01)
            if change == "hash":
                await observer.execute(
                    "UPDATE identity.password_credentials SET scrypt_hash='replaced' WHERE owner_id='A'"
                )
            elif change == "version":
                await observer.execute(
                    "UPDATE identity.users SET session_version=1 WHERE id='A'"
                )
            elif change == "disabled":
                await observer.execute(
                    "UPDATE identity.users SET disabled=true WHERE id='A'"
                )
            elif change == "deleted":
                await observer.execute("DELETE FROM identity.users WHERE id='A'")
            elif change == "alias":
                await observer.execute(
                    "UPDATE identity.login_aliases SET owner_id='B', email_claim=true, password_name_claim=false WHERE alias_key='alice'"
                )
        response = await task
        assert response.status_code == (
            200 if change == "valid" else 403 if change == "disabled" else 401
        )
        if change != "valid":
            assert "set-cookie" not in response.headers
        assert (
            await client.post(
                "/api/v1/login/password", json={"name": "bob", "password": PASSWORD}
            )
        ).status_code == 200
        client.cookies.clear()
        assert (await client.get("/api/v1/me")).status_code == 401


@pytest.mark.asyncio
async def test_name_and_email_share_concurrent_failure_budget(accounts):
    _, environment = accounts
    async with server(environment) as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/login/password",
                    json={
                        "identifier": "alice" if i % 2 else "a@example.test",
                        "password": "wrong",
                    },
                )
                for i in range(12)
            ]
        )
        assert sorted(r.status_code for r in responses) == [401] * 6 + [429] * 6
        locked = next(r for r in responses if r.status_code == 429)
        assert locked.json()["code"] == "locked"
        assert 58 <= locked.json()["retryAfter"] <= 60
        assert locked.headers["retry-after"] == str(locked.json()["retryAfter"])
        assert (
            await client.post(
                "/api/v1/login/password", json={"name": "alice", "password": PASSWORD}
            )
        ).status_code == 429
        assert (
            await client.post(
                "/api/v1/login/password", json={"name": "bob", "password": PASSWORD}
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_password_login_requires_identifier_and_password(identities):
    _, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    async with server(environment) as client:
        response = await client.post("/api/v1/login/password", json={})
        assert response.status_code == 400
        assert response.json() == {
            "error": "name and password required",
            "code": "missing",
        }


@pytest.mark.asyncio
async def test_unknown_password_login_is_generic_denial(identities):
    _, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/login/password",
            json={"identifier": "unknown", "password": "synthetic-wrong-password"},
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "wrong name or password",
            "code": "bad-credentials",
        }
        assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_off_malformed_missing_and_oversized_bodies(accounts):
    _, environment = accounts
    environment["PASSWORD_LOGIN"] = "0"
    async with server(environment) as client:
        assert (await client.post("/api/v1/login/password", json={})).status_code == 404
    environment["PASSWORD_LOGIN"] = "1"
    async with server(environment) as client:
        for content in ("{", "null", "[]", '"hello"', '{"name":NaN,"password":"x"}'):
            response = await client.post("/api/v1/login/password", content=content)
            assert response.status_code == 400
            assert response.json() == {"error": "invalid json"}
        response = await client.post(
            "/api/v1/login/password", content="x" * (5 * 1024 * 1024 + 1)
        )
        assert response.status_code == 413
        for body in (
            {},
            {"name": "alice"},
            {"name": {}, "password": PASSWORD},
            {"name": "alice", "password": 123},
        ):
            response = await client.post("/api/v1/login/password", json=body)
            assert response.status_code == 400
        for body in (
            {"email": "alice", "password": PASSWORD},
            {"name": "alice", "password": "x" * 257},
        ):
            assert (
                await client.post("/api/v1/login/password", json=body)
            ).status_code == 401
        assert (
            await client.post(
                "/api/v1/login/password", json={"name": "alice", "password": PASSWORD}
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_disabled_wrong_and_malformed_hash_do_not_issue_sessions(accounts):
    observer, environment = accounts
    await observer.execute("UPDATE identity.users SET disabled=true WHERE id='A'")
    async with server(environment) as client:
        for password, status in (("wrong", 401), (PASSWORD, 403)):
            response = await client.post(
                "/api/v1/login/password", json={"name": "alice", "password": password}
            )
            assert response.status_code == status
            assert "set-cookie" not in response.headers
        await observer.execute(
            "UPDATE identity.password_credentials SET scrypt_hash='bad' WHERE owner_id='A'"
        )
        response = await client.post(
            "/api/v1/login/password", json={"name": "alice", "password": PASSWORD}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_old_parameters_rehash_without_changing_version_or_historical_date(
    accounts,
):
    observer, environment = accounts
    vector = VECTORS["vectors"][5]
    await observer.execute(
        "UPDATE identity.password_credentials SET scrypt_hash=$1 WHERE owner_id='A'",
        vector["hash"],
    )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/login/password",
            json={"name": "alice", "password": vector["password"]},
        )
        assert response.status_code == 200
        rows = await observer.fetch(
            "SELECT scrypt_hash,set_at FROM identity.password_credentials WHERE owner_id='A'"
        )
        assert rows[0]["scrypt_hash"].startswith("$scrypt$v=1$ln=15,r=8,p=1$")
        assert rows[0]["set_at"] is None
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 0
        )
        assert (await client.get("/api/v1/me")).status_code == 200


@pytest.mark.asyncio
async def test_address_failure_and_burst_budgets(accounts):
    _, environment = accounts
    async with server(environment) as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/login/password",
                    json={"name": f"unknown-{i}", "password": "wrong"},
                )
                for i in range(30)
            ]
        )
        assert sorted(r.status_code for r in responses) == [401] * 21 + [429] * 9
    async with server(environment) as client:
        for _ in range(60):
            assert (
                await client.post("/api/v1/login/password", json={})
            ).status_code == 400
        response = await client.post("/api/v1/login/password", json={})
        assert response.status_code == 429


@pytest.mark.asyncio
@pytest.mark.parametrize("trust", ["0", "true", "on", "1"])
async def test_proxy_address_is_trusted_only_when_enabled(accounts, trust):
    _, environment = accounts
    environment["TRUST_PROXY"] = trust
    async with server(environment) as client:
        for i in range(21):
            response = await client.post(
                "/api/v1/login/password",
                json={"name": f"unknown-{i}", "password": "wrong"},
                headers={"X-Forwarded-For": "198.51.100.1"},
            )
            assert response.status_code == 401
        response = await client.post(
            "/api/v1/login/password",
            json={"name": "bob", "password": PASSWORD},
            headers={"X-Forwarded-For": "198.51.100.1, 198.51.100.2"},
        )
        assert response.status_code == (429 if trust == "0" else 200)


@pytest.mark.asyncio
async def test_login_database_failure_is_safe(accounts):
    observer, environment = accounts
    async with server(environment) as client:
        await observer.execute(
            "REVOKE EXECUTE ON FUNCTION identity.lookup_password(text) FROM opengym_api_runtime"
        )
        response = await client.post(
            "/api/v1/login/password", json={"name": "alice", "password": PASSWORD}
        )
        assert response.status_code == 500
        assert response.json() == {"error": "server error"}
        assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_invalid_unicode_identifier_is_generic_denial(accounts):
    _, environment = accounts
    async with server(environment) as client:
        for value in ("a\u0000b", "\ud800"):
            response = await client.post(
                "/api/v1/login/password",
                content=json.dumps({"name": value, "password": PASSWORD}),
            )
            assert response.status_code == 401
            assert response.json() == {
                "error": "wrong name or password",
                "code": "bad-credentials",
            }


@pytest.mark.asyncio
async def test_crypto_dummy_work_bounds_cancellation_and_failure(monkeypatch):
    passwords = Passwords()
    await passwords.warm_up()
    loop = asyncio.get_running_loop()
    entered = asyncio.Queue()
    release = threading.Event()

    def crypto(password, **kwargs):
        loop.call_soon_threadsafe(entered.put_nowait, kwargs["n"])
        assert release.wait(3)
        return bytes(kwargs["dklen"])

    monkeypatch.setattr("hashlib.scrypt", crypto)
    tasks = [
        asyncio.create_task(passwords.verify(PASSWORD, None if i % 2 else "bad"))
        for i in range(34)
    ]
    try:
        assert await asyncio.wait_for(entered.get(), 1) == 32768
        assert await asyncio.wait_for(entered.get(), 1) == 32768
        with pytest.raises(BusyError):
            await passwords.verify(PASSWORD, HASH)
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[0]
        with pytest.raises(BusyError):
            await passwords.verify(PASSWORD, HASH)
        assert entered.empty()
    finally:
        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
    assert results[1:] == [False] * 33

    def failed_crypto(*args, **kwargs):
        raise ValueError("synthetic-crypto-failure")

    monkeypatch.setattr("hashlib.scrypt", failed_crypto)
    with pytest.raises(ValueError):
        await passwords.verify(PASSWORD, HASH)


@pytest.mark.asyncio
async def test_password_sql_rls_and_grants_are_bounded(accounts, monkeypatch):
    observer, environment = accounts
    for key, value in {
        **environment,
        "PLATFORM_DB_PASSWORD_FILE": environment["PLATFORM_RUNTIME_PASSWORD_FILE"],
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    database = await Database.open_platform()
    try:
        assert await database.fetch("SELECT * FROM identity.password_credentials") == []
        with pytest.raises(DatabaseError):
            await database.fetch("SELECT * FROM identity.login_aliases")
        async with database.transaction(owner_id="A") as handle:
            assert [
                r["owner_id"]
                for r in await handle.fetch(
                    "SELECT * FROM identity.password_credentials"
                )
            ] == ["A"]
            assert (
                await handle.execute(
                    "UPDATE identity.password_credentials SET scrypt_hash='forged' WHERE owner_id='B'"
                )
                == "UPDATE 0"
            )
        assert await database.fetch("SELECT * FROM identity.password_credentials") == []
        assert (
            await observer.fetchval(
                "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='B'"
            )
            == HASH
        )
        rows = await observer.fetch(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid IN ('identity.password_credentials'::regclass,'identity.login_aliases'::regclass)"
        )
        assert len(rows) == 2 and all(
            r["relrowsecurity"] and r["relforcerowsecurity"] for r in rows
        )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_password_migration_extends_genuine_session_revision(
    deployment, tmp_path
):
    from test_lifecycle import migration

    observer, environment = deployment
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        tmp_path / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p001_password_register.py",
            "p001_password_login.py",
            "p002_training.py",
            "p002_training_write.py",
        ),
    )
    await migration({**environment, "PYTHONPATH": str(tmp_path)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_identity_session"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('existing','Historical')"
    )
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_password_register"
    )
    assert dict(
        await observer.fetchrow("SELECT id,created_at FROM identity.users")
    ) == {
        "id": "existing",
        "created_at": None,
    }
