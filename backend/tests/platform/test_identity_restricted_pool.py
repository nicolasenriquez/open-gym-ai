"""Final identity security checkpoint over real HTTP and a one-slot runtime pool."""

import asyncio
import os
from contextlib import suppress
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from _commit_relay import commit_relay
from fastapi.responses import JSONResponse
from test_identity_links import CODE as LINK_CODE
from test_identity_links import DIGEST as LINK_DIGEST
from test_identity_links import redemption, start_link
from test_identity_passkey import fixed_challenge_app
from test_identity_password import PASSWORD
from test_identity_password import accounts as accounts  # noqa: PLC0414
from test_identity_reset import CODE as RESET_CODE
from test_identity_reset import DIGEST as RESET_DIGEST
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server

from opengym_platform.application import create_app as platform_app
from opengym_platform.core.database import Database

CONTEXT = (
    "owner_id",
    "invite_only",
    "first_user_admin",
    "admin_uids",
    "reset_identifier",
    "reset_alias",
    "reset_name",
    "reset_sv",
    "link_sv",
)


@pytest_asyncio.fixture
async def restricted(accounts):
    observer, environment = accounts
    environment["PYTHONPATH"] = (
        str(Path(__file__).parent)
        + ":"
        + str(Path(__file__).parents[1] / "core")
        + ":"
        + environment["PYTHONPATH"]
    )
    await observer.execute("""INSERT INTO identity.passkeys(credential_id,owner_id,public_key,counter,transports)
        VALUES ('Zm9yZWlnbkE','A',decode('aa','hex'),0,'{}'), ('Zm9yZWlnbkI','B',decode('bb','hex'),0,'{}');
        INSERT INTO identity.password_resets VALUES
            ('A',decode(repeat('ab',32),'hex'),now()+interval '24 hours','B'),
            ('B',decode(repeat('cd',32),'hex'),now()+interval '24 hours','B');
        INSERT INTO identity.device_links VALUES
            (decode(repeat('ab',32),'hex'),'A',now(),now()+interval '10 minutes'),
            (decode(repeat('cd',32),'hex'),'B',now(),now()+interval '10 minutes');
    """)
    return observer, environment


class CancelAtSignal:
    """Cancel the actual ASGI request only after the independent observer signals."""

    def __init__(self, app, signal):
        self.app, self.signal = app, Path(signal)

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or (b"x-synthetic-cancel", b"1") not in scope["headers"]
        ):
            return await self.app(scope, receive, send)
        task = asyncio.create_task(self.app(scope, receive, send))
        try:
            async with asyncio.timeout(5):
                while not self.signal.exists():
                    await asyncio.sleep(0.01)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await JSONResponse(
                {"code": "synthetic-request-cancelled"}, status_code=503
            )(scope, receive, send)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def one_slot_app():
    # Only this child-process factory changes pool bounds; product settings stay intact.
    original = Database._open.__func__

    async def open_one(cls, settings, context):
        relay = os.environ.get("PLATFORM_TEST_RELAY_PORT")
        return await original(
            cls,
            settings.model_copy(
                update={
                    "max_size": 1,
                    "statement_timeout": 1.0,
                    "command_timeout": 2.0,
                    "acquire_timeout": 0.25,
                    **({"host": "127.0.0.1", "port": int(relay)} if relay else {}),
                }
            ),
            context,
        )

    Database._open = classmethod(open_one)
    app = platform_app()
    if signal := os.environ.get("PLATFORM_TEST_CANCEL_SIGNAL"):
        app.add_middleware(CancelAtSignal, signal=signal)

    @app.get("/synthetic/pool")
    async def pool_probe():
        database = app.state.database
        rows = await database.fetch(
            """SELECT pg_backend_pid() AS pid,
            current_user AS actor, session_user AS login,
            current_setting('row_security') AS rls,
            ARRAY(SELECT nullif(current_setting('app.' || key, true), '')
                FROM unnest($1::text[]) key) AS context,
            ARRAY(SELECT id FROM identity.users ORDER BY id) AS users,
            ARRAY(SELECT alias_key FROM identity.login_aliases) AS aliases,
            ARRAY(SELECT owner_id FROM identity.password_credentials) AS passwords,
            ARRAY(SELECT owner_id FROM identity.passkeys) AS passkeys,
            ARRAY(SELECT owner_id FROM identity.password_resets) AS resets,
            ARRAY(SELECT owner_id FROM identity.device_links) AS links
        """,
            list(CONTEXT),
        )
        return {**dict(rows[0]), "max_size": database._settings.max_size}

    return app


def one_slot_challenge_app():
    fixed_challenge_app()
    return one_slot_app()


async def clean(client, observer, pid=None):
    response = await client.get("/synthetic/pool")
    assert response.status_code == 200
    row = response.json()
    assert row["max_size"] == 1
    assert row["actor"] == row["login"] == "opengym_api_runtime"
    assert row["rls"] == "on" and row["context"] == [None] * len(CONTEXT)
    for key in ("users", "aliases", "passwords", "passkeys", "resets", "links"):
        assert row[key] == [], key
    if pid is not None:
        assert row["pid"] == pid, "proof requires reuse of the same connection"
    sessions = await observer.fetch("""SELECT pid, usename, state, xact_start
        FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()
    """)
    assert len(sessions) == 1
    assert sessions[0]["pid"] == row["pid"]
    assert sessions[0]["usename"] == "opengym_api_runtime"
    assert sessions[0]["state"] == "idle" and sessions[0]["xact_start"] is None
    return row["pid"]


@pytest.mark.asyncio
async def test_one_connection_alternates_preauth_owners_missing_and_committed_write(
    restricted,
):
    observer, environment = restricted
    async with server(
        environment, factory="test_identity_restricted_pool:one_slot_app"
    ) as client:
        pid = await clean(client, observer)
        for token, owner, name, admin in (
            (A, "A", "Alice", False),
            (B, "B", "Bob", True),
        ):
            response = await client.get(
                "/api/v1/me?owner=foreign",
                headers={
                    "Authorization": "Bearer " + token,
                    "X-Owner-ID": "foreign",
                },
            )
            assert response.json() == {
                "user": {"id": owner, "name": name, "admin": admin}
            }
            await clean(client, observer, pid)
            login = await client.post(
                "/api/v1/login/password",
                json={
                    "name": name,
                    "password": PASSWORD,
                    "owner": "foreign",
                },
            )
            assert login.status_code == 200 and login.json()["user"]["id"] == owner
            client.cookies.clear()
            await clean(client, observer, pid)
            assert (await client.get("/api/v1/me")).status_code == 401
            assert (
                await client.post(
                    "/api/v1/login/password",
                    json={
                        "name": name,
                        "password": "wrong",
                    },
                )
            ).status_code == 401
            await clean(client, observer, pid)
        response = await client.post(
            "/api/v1/account/email",
            headers={
                "Authorization": "Bearer " + A,
            },
            json={"email": "new@example.test", "current": PASSWORD, "owner": "B"},
        )
        assert response.status_code == 200
        assert (
            await observer.fetchval(
                "SELECT owner_id FROM identity.login_aliases WHERE alias_key='new@example.test'"
            )
            == "A"
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.login_aliases WHERE owner_id='B'"
            )
            == 1
        )
        await clean(client, observer, pid)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["error", "timeout", "cancel"])
async def test_partial_owner_write_rolls_back_and_next_borrower_is_clean(
    restricted, tmp_path, outcome
):
    observer, environment = restricted
    signal = tmp_path / "cancel"
    environment["PLATFORM_TEST_CANCEL_SIGNAL"] = str(signal)
    # The real owner write deletes the old email before this insert faults.
    fault = (
        "RAISE EXCEPTION 'private-pool-marker'"
        if outcome == "error"
        else "PERFORM pg_sleep(20)"
    )
    await observer.execute(f"""CREATE FUNCTION public.fail_email() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            IF NEW.alias_key='new@example.test' THEN {fault}; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER fail_email BEFORE INSERT ON identity.login_aliases
        FOR EACH ROW EXECUTE FUNCTION public.fail_email();
    """)
    async with server(
        environment, factory="test_identity_restricted_pool:one_slot_app"
    ) as client:
        pid = await clean(client, observer)
        before = await observer.fetch(
            "SELECT * FROM identity.login_aliases ORDER BY alias_key"
        )
        task = asyncio.create_task(
            client.post(
                "/api/v1/account/email",
                headers={
                    "Authorization": "Bearer " + A,
                    **({"X-Synthetic-Cancel": "1"} if outcome == "cancel" else {}),
                },
                json={"email": "new@example.test", "current": PASSWORD},
            )
        )
        try:
            if outcome == "cancel":
                async with asyncio.timeout(2):
                    while not await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE pid=$1 AND wait_event='PgSleep')",
                        pid,
                    ):
                        await asyncio.sleep(0.01)
                signal.touch()
            response = await task
            assert response.status_code == (503 if outcome == "cancel" else 500)
            assert response.json() == (
                {"code": "synthetic-request-cancelled"}
                if outcome == "cancel"
                else {"error": "server error"}
            )
            assert "set-cookie" not in response.headers
            if outcome == "cancel":
                # Cancellation discards the lease; PostgreSQL observes disconnect asynchronously.
                async with asyncio.timeout(2):
                    while await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE pid=$1)", pid
                    ):
                        await asyncio.sleep(0.01)
            assert (
                await observer.fetch(
                    "SELECT * FROM identity.login_aliases ORDER BY alias_key"
                )
                == before
            )
            next_pid = await clean(
                client, observer, None if outcome == "cancel" else pid
            )
            if next_pid != pid:
                assert not await observer.fetchval(
                    "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE pid=$1)", pid
                )
            pid = next_pid
            for token, owner in ((B, "B"), (A, "A")):
                result = await client.get(
                    "/api/v1/me", headers={"Authorization": "Bearer " + token}
                )
                assert (
                    result.status_code == 200 and result.json()["user"]["id"] == owner
                )
                await clean(client, observer, pid)
            assert (await client.get("/api/v1/me")).status_code == 401
            await clean(client, observer, pid)
        finally:
            signal.touch()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_pool_acquire_and_actor_wait_timeouts_do_not_leak_actor(restricted):
    observer, environment = restricted
    async with server(
        environment, factory="test_identity_restricted_pool:one_slot_app"
    ) as client:
        pid = await clean(client, observer)
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            first = asyncio.create_task(
                client.get("/api/v1/me", headers={"Authorization": "Bearer " + A})
            )
            async with asyncio.timeout(0.8):
                while not await observer.fetchval(
                    "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE pid=$1 AND wait_event_type='Lock')",
                    pid,
                ):
                    await asyncio.sleep(0.01)
            queued = await client.get(
                "/api/v1/me", headers={"Authorization": "Bearer " + B}
            )
            assert queued.status_code == 500 and queued.json() == {
                "error": "server error"
            }
            assert not first.done()
            assert (await first).status_code == 500
        await clean(client, observer, pid)
        for token, owner in ((B, "B"), (A, "A")):
            result = await client.get(
                "/api/v1/me", headers={"Authorization": "Bearer " + token}
            )
            assert result.json()["user"]["id"] == owner
            await clean(client, observer, pid)


@pytest.mark.asyncio
async def test_registration_reset_and_link_context_cannot_survive_commit_or_rollback(
    restricted,
):
    observer, environment = restricted
    environment.update(
        RP_ID="localhost", ORIGIN="http://localhost:8080", FIRST_USER_ADMIN="1"
    )
    await observer.execute(
        "UPDATE identity.password_resets SET code_digest=$1 WHERE owner_id='A'",
        RESET_DIGEST,
    )
    await observer.execute(
        "UPDATE identity.device_links SET code_digest=$1 WHERE owner_id='B'",
        LINK_DIGEST,
    )
    async with server(
        environment, factory="test_identity_restricted_pool:one_slot_challenge_app"
    ) as client:
        pid = await clean(client, observer)
        signup = {
            "name": "Carol",
            "password": "violet river stones",
            "admin": True,
            "owner": "B",
        }
        result = await client.post("/api/v1/register/password", json=signup)
        assert result.status_code == 200 and result.json()["user"]["admin"] is False
        carol = result.json()["user"]["id"]
        client.cookies.clear()
        await clean(client, observer, pid)
        assert (
            await client.post("/api/v1/register/password", json=signup)
        ).status_code == 409
        await clean(client, observer, pid)
        reset = {
            "name": "Alice",
            "code": RESET_CODE,
            "next": "violet river stones",
            "owner": "B",
        }
        result = await client.post("/api/v1/login/password-reset", json=reset)
        assert result.status_code == 200 and result.json()["user"]["id"] == "A"
        client.cookies.clear()
        await clean(client, observer, pid)
        assert (
            await client.post("/api/v1/login/password-reset", json=reset)
        ).status_code == 400
        await clean(client, observer, pid)
        start = await start_link(client, LINK_CODE)
        await clean(client, observer, pid)
        result = await client.post("/api/v1/device-link/verify", json=redemption(start))
        assert result.status_code == 200 and result.json()["user"]["id"] == "B"
        client.cookies.clear()
        await clean(client, observer, pid)
        assert (
            await client.post("/api/v1/device-link/verify", json=redemption(start))
        ).status_code == 400
        await clean(client, observer, pid)
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 1
        )
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='B'"
            )
            == 3
        )
        assert (
            await observer.fetchval(
                "SELECT is_admin FROM identity.users WHERE id=$1", carol
            )
            is False
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.password_resets")
            == 1
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )


@pytest.mark.asyncio
async def test_final_catalog_has_exact_signatures_acl_force_rls_and_no_role_escape(
    restricted,
):
    observer, environment = restricted
    functions = await observer.fetch("""SELECT p.oid::regprocedure::text AS signature,
        p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner) AS owner,
        has_function_privilege('opengym_api_runtime',p.oid,'EXECUTE') AS runtime,
        EXISTS(SELECT FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE a.grantee=0) AS public,
        EXISTS(SELECT FROM aclexplode(p.proacl) a WHERE a.is_grantable AND a.grantee<>'opengym_identity_executor'::regrole) AS delegated
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='identity'
    """)
    assert {row["signature"] for row in functions} == {
        "identity.lock_actor(text,bigint,timestamp with time zone)",
        "identity.public_user_count()",
        "identity.lookup_password(text)",
        "identity.finish_password_login(text,text,bigint)",
        "identity.register_password(text,text,text,text,text,text,timestamp with time zone)",
        "identity.register_passkey(text,text,text,text,bytea,bigint,text[],timestamp with time zone)",
        "identity.lookup_passkey(text)",
        "identity.finish_passkey_login(text,bytea,bigint,bigint,bigint)",
        "identity.alias_available(text)",
        "identity.release_expired_alias(text)",
        "identity.lookup_reset(bytea)",
        "identity.finish_reset(text,bytea,text)",
        "identity.lookup_device_link(bytea)",
        "identity.finish_device_link(text,bytea,text,bytea,bigint,text[],text)",
    }
    assert all(
        row["prosecdef"]
        and row["runtime"]
        and not row["public"]
        and not row["delegated"]
        and row["owner"] == "opengym_identity_executor"
        and row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
        for row in functions
    )
    tables = await observer.fetch("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
        pg_get_userbyid(c.relowner) AS owner,
        EXISTS(SELECT FROM aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a WHERE a.grantee=0) AS public
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='identity' AND c.relkind='r'
    """)
    assert {row["relname"] for row in tables} == {
        "users",
        "invitations",
        "login_aliases",
        "password_credentials",
        "passkeys",
        "password_resets",
        "device_links",
    }
    assert all(
        row["relrowsecurity"]
        and row["relforcerowsecurity"]
        and not row["public"]
        and row["owner"] == "opengym_schema_owner"
        for row in tables
    )
    # Column grants are intentional: table-level checks alone miss accidental escalation.
    grants = {
        "users": {
            "SELECT": {"id", "display_name", "is_admin", "session_version"},
            "UPDATE": {"session_version"},
        },
        "invitations": {},
        "login_aliases": {
            "SELECT": "*",
            "INSERT": "*",
            "DELETE": "*",
            "UPDATE": {"email_claim", "password_name_claim", "reset_name_until"},
        },
        "password_credentials": {
            "SELECT": "*",
            "INSERT": "*",
            "DELETE": "*",
            "UPDATE": {"scrypt_hash", "set_at"},
        },
        "passkeys": {"SELECT": "*", "INSERT": "*", "DELETE": "*", "UPDATE": {"label"}},
        "password_resets": {"SELECT": {"owner_id"}, "DELETE": "*"},
        "device_links": {
            "SELECT": "*",
            "INSERT": "*",
            "DELETE": "*",
            "UPDATE": {"code_digest", "created_at", "expires_at"},
        },
    }
    columns = await observer.fetch("""SELECT c.oid, c.relname, a.attname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE n.nspname='identity' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped""")
    for column in columns:
        for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
            allowed = grants[column["relname"]].get(privilege, set())
            actual = await observer.fetchval(
                "SELECT has_column_privilege('opengym_api_runtime',$1::oid,$2::text,$3::text)",
                column["oid"],
                column["attname"],
                privilege,
            )
            assert actual == (allowed == "*" or column["attname"] in allowed), (
                dict(column),
                privilege,
            )
    for table in tables:
        for privilege in ("DELETE", "TRUNCATE", "TRIGGER"):
            actual = await observer.fetchval(
                "SELECT has_table_privilege('opengym_api_runtime',$1::text,$2::text)",
                "identity." + table["relname"],
                privilege,
            )
            assert actual == (privilege in grants[table["relname"]]), (
                table["relname"],
                privilege,
            )
    roles = await observer.fetch("""SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolinherit
        FROM pg_roles WHERE rolname IN ('opengym_api_runtime','opengym_identity_executor')""")
    assert len(roles) == 2
    for role in roles:
        assert role["rolcanlogin"] == (role["rolname"] == "opengym_api_runtime")
        assert not any(
            role[key]
            for key in (
                "rolsuper",
                "rolbypassrls",
                "rolcreatedb",
                "rolcreaterole",
                "rolreplication",
                "rolinherit",
            )
        )
    assert not await observer.fetchval(
        "SELECT EXISTS(SELECT FROM pg_auth_members WHERE member='opengym_api_runtime'::regrole)"
    )
    connection = await asyncpg.connect(
        host="platform-db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
        timeout=5,
    )
    try:
        for sql in (
            "SET ROLE opengym_identity_executor",
            "SET ROLE opengym_schema_owner",
            "SET ROLE opengym_migrator",
            "SET ROLE opengym_platform_bootstrap",
            "CREATE SCHEMA escaped",
            "CREATE TABLE public.escaped(id int)",
            "CREATE TEMP TABLE escaped(id int)",
            "ALTER TABLE identity.users DISABLE ROW LEVEL SECURITY",
            "GRANT opengym_identity_executor TO opengym_api_runtime",
            "SELECT code FROM identity.invitations",
            "SELECT code_digest FROM identity.password_resets",
            "UPDATE identity.users SET is_admin=true",
            "UPDATE identity.passkeys SET public_key=decode('aa','hex')",
            "TRUNCATE identity.users CASCADE",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(sql)
        async with connection.transaction():
            await connection.execute("SET LOCAL row_security=off")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.fetch("SELECT id FROM identity.users")
        assert await connection.fetch("SELECT id FROM identity.users") == []
        assert (
            await connection.execute("UPDATE identity.users SET session_version=99")
            == "UPDATE 0"
        )
        assert (
            await connection.execute("DELETE FROM identity.device_links") == "DELETE 0"
        )
        assert (
            await connection.fetchval("SELECT identity.alias_available('alice')")
            is False
        )
        assert (
            await connection.fetch("SELECT * FROM identity.lookup_password('missing')")
            == []
        )
        assert (
            await connection.fetch("SELECT * FROM identity.lookup_passkey('missing')")
            == []
        )
        assert (
            await connection.fetch(
                "SELECT * FROM identity.lookup_reset(decode('ab','hex'))"
            )
            == []
        )
        assert (
            await connection.fetch(
                "SELECT * FROM identity.lookup_device_link(decode('ab','hex'))"
            )
            == []
        )
        for owner, foreign in (("A", "B"), ("B", "A")):
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.owner_id',$1,true)", owner
                )
                assert [
                    row["id"]
                    for row in await connection.fetch("SELECT id FROM identity.users")
                ] == [owner]
                for table in (
                    "login_aliases",
                    "password_credentials",
                    "passkeys",
                    "password_resets",
                    "device_links",
                ):
                    rows = await connection.fetch(
                        f"SELECT owner_id FROM identity.{table}"
                    )
                    assert rows and {row["owner_id"] for row in rows} == {owner}
                assert (
                    await connection.execute(
                        "UPDATE identity.users SET session_version=99 WHERE id=$1",
                        foreign,
                    )
                    == "UPDATE 0"
                )
                assert (
                    await connection.execute(
                        "DELETE FROM identity.device_links WHERE owner_id=$1", foreign
                    )
                    == "DELETE 0"
                )
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.owner_id',$1,true)", owner
                )
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(
                        "INSERT INTO identity.passkeys(credential_id,owner_id,public_key,counter,transports) VALUES ('forged',$1,decode('aa','hex'),0,'{}')",
                        foreign,
                    )
    finally:
        await connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["register", "reset", "link"])
async def test_privileged_context_is_clean_after_failed_final_write(
    restricted, operation
):
    observer, environment = restricted
    environment.update(RP_ID="localhost", ORIGIN="http://localhost:8080")
    await observer.execute(
        "UPDATE identity.password_resets SET code_digest=$1 WHERE owner_id='A'",
        RESET_DIGEST,
    )
    await observer.execute(
        "UPDATE identity.device_links SET code_digest=$1 WHERE owner_id='B'",
        LINK_DIGEST,
    )
    event, table = {
        "register": ("INSERT", "password_credentials"),
        "reset": ("UPDATE", "password_credentials"),
        "link": ("INSERT", "passkeys"),
    }[operation]
    await observer.execute(f"""CREATE FUNCTION public.fail_final() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'private-final-marker'; END $$;
        CREATE TRIGGER fail_final BEFORE {event} ON identity.{table}
        FOR EACH ROW EXECUTE FUNCTION public.fail_final();""")
    async with server(
        environment, factory="test_identity_restricted_pool:one_slot_challenge_app"
    ) as client:
        pid = await clean(client, observer)
        if operation == "register":
            path, body = (
                "/api/v1/register/password",
                {"name": "Carol", "password": "violet river stones"},
            )
        elif operation == "reset":
            path, body = (
                "/api/v1/login/password-reset",
                {"name": "Alice", "code": RESET_CODE, "next": "violet river stones"},
            )
        else:
            path, body = (
                "/api/v1/device-link/verify",
                redemption(await start_link(client)),
            )
        response = await client.post(path, json=body)
        assert response.status_code == 500 and response.json() == {
            "error": "server error"
        }
        assert "set-cookie" not in response.headers
        await clean(client, observer, pid)
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 2
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.password_resets")
            == 2
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 2
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.passkeys") == 2
        assert [
            tuple(row)
            for row in await observer.fetch(
                "SELECT id,session_version FROM identity.users ORDER BY id"
            )
        ] == [("A", 0), ("B", 3)]


@pytest.mark.asyncio
async def test_http_unknown_commit_does_not_retry_or_reuse_discarded_context(
    restricted,
):
    observer, environment = restricted
    async with commit_relay() as relay:
        environment["PLATFORM_TEST_RELAY_PORT"] = str(relay.port)
        async with server(
            environment, factory="test_identity_restricted_pool:one_slot_app"
        ) as client:
            pid = await clean(client, observer)
            task = asyncio.create_task(
                client.post(
                    "/api/v1/logout/all", headers={"Authorization": "Bearer " + A}
                )
            )
            try:
                await asyncio.wait_for(relay.held.wait(), 1.5)
                assert (
                    await observer.fetchval(
                        "SELECT session_version FROM identity.users WHERE id='A'"
                    )
                    == 1
                )
                relay.release.set()
                response = await task
                assert response.status_code == 500 and response.json() == {
                    "error": "server error"
                }
                assert "set-cookie" not in response.headers and relay.commits == 1
                replacement = await clean(client, observer)
                assert replacement != pid
                assert (
                    await client.get(
                        "/api/v1/me", headers={"Authorization": "Bearer " + A}
                    )
                ).status_code == 401
                result = await client.get(
                    "/api/v1/me", headers={"Authorization": "Bearer " + B}
                )
                assert result.status_code == 200 and result.json()["user"]["id"] == "B"
                await clean(client, observer, replacement)
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
            finally:
                relay.release.set()
                await asyncio.gather(task, return_exceptions=True)
