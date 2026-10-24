"""Restricted-login isolation proof against disposable PostgreSQL."""

import asyncio
from contextlib import AsyncExitStack

import asyncpg
import pytest
import pytest_asyncio
from test_migrations import connect

from opengym_platform.core.database import Database, DatabaseError

pytest_plugins = ["test_migrations"]


@pytest_asyncio.fixture
async def isolation_database(migration_database):
    observer = migration_database
    async with AsyncExitStack() as cleanup:
        cleanup.push_async_callback(
            observer.execute, "DROP SCHEMA IF EXISTS isolation_fixture CASCADE"
        )
        migrator = await connect(
            "python_foundation_migrator", "synthetic-python-foundation-migrator-only"
        )
        cleanup.push_async_callback(migrator.close, timeout=5)
        await migrator.execute("""
            CREATE SCHEMA isolation_fixture;
            REVOKE ALL ON SCHEMA isolation_fixture FROM PUBLIC;
            CREATE TABLE isolation_fixture.owner_probe (
                id integer PRIMARY KEY,
                owner_id text NOT NULL
            );
            GRANT USAGE ON SCHEMA isolation_fixture TO python_foundation_runtime;
            GRANT SELECT, INSERT, UPDATE, DELETE ON isolation_fixture.owner_probe
                TO python_foundation_runtime;
            ALTER TABLE isolation_fixture.owner_probe ENABLE ROW LEVEL SECURITY;
            ALTER TABLE isolation_fixture.owner_probe FORCE ROW LEVEL SECURITY;
            CREATE POLICY owner_isolation ON isolation_fixture.owner_probe
                TO python_foundation_runtime
                USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
                WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''));
        """)
        restricted = await observer.fetchval("""
            SELECT NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolinherit)
                AND NOT EXISTS (SELECT FROM pg_auth_members WHERE member = r.oid)
                AND NOT EXISTS (
                    SELECT FROM pg_class WHERE relnamespace =
                        'isolation_fixture'::regnamespace AND relowner = r.oid
                )
            FROM pg_roles r WHERE rolname = 'python_foundation_runtime'
        """)
        assert restricted is True, "FOUNDATION_ISOLATION_RESTRICTED_LOGIN_REQUIRED"
        database = await Database.open(
            {
                "host": "foundation-db",
                "port": 5432,
                "database": "python_foundation_test",
                "user": "python_foundation_runtime",
                "password": "synthetic-python-foundation-runtime-only",
                "tls": False,
                "min_size": 1,
                "max_size": 1,
            }
        )
        cleanup.push_async_callback(database.close)
        yield database
    assert (
        await observer.fetchval("SELECT to_regnamespace('isolation_fixture')") is None
    )


@pytest.mark.asyncio
async def test_owner_b_cannot_read_owner_a_after_connection_reuse(isolation_database):
    database = isolation_database
    identity_sql = """
        SELECT current_user AS login, pg_backend_pid() AS pid,
            nullif(current_setting('app.owner_id', true), '') AS owner
    """
    async with database.transaction(owner_id="owner-a") as handle:
        first = (await handle.fetch(identity_sql))[0]
        assert first["login"] == "python_foundation_runtime"
        assert first["owner"] == "owner-a"
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
        own = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert [row["id"] for row in own] == [1]

    async with database.transaction(owner_id="owner-b") as handle:
        second = (await handle.fetch(identity_sql))[0]
        assert second["login"] == "python_foundation_runtime"
        assert second["owner"] == "owner-b"
        assert second["pid"] == first["pid"], "FOUNDATION_MAX_ONE_MUST_REUSE_CONNECTION"
        exposed = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert len(exposed) == 0, "FOUNDATION_RLS_CROSS_OWNER_READ_DENIED"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["insert", "update"])
async def test_runtime_cannot_forge_a_different_row_owner(
    isolation_database, operation
):
    database = isolation_database
    async with database.transaction(owner_id="owner-a") as handle:
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
    with pytest.raises(DatabaseError, match="^DATABASE_QUERY_FAILED$"):
        async with database.transaction(owner_id="owner-a") as handle:
            if operation == "insert":
                await handle.execute(
                    "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)",
                    2,
                    "owner-b",
                )
            else:
                await handle.execute(
                    "UPDATE isolation_fixture.owner_probe SET owner_id = $1 WHERE id = $2",
                    "owner-b",
                    1,
                )
    async with database.transaction(owner_id="owner-a") as handle:
        own = await handle.fetch(
            "SELECT id, owner_id FROM isolation_fixture.owner_probe"
        )
        assert [(row["id"], row["owner_id"]) for row in own] == [(1, "owner-a")]
    async with database.transaction(owner_id="owner-b") as handle:
        assert (
            len(await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")) == 0
        )


@pytest.mark.asyncio
async def test_runtime_can_mutate_only_its_own_rows(isolation_database):
    database = isolation_database
    async with database.transaction(owner_id="owner-a") as handle:
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
    async with database.transaction(owner_id="owner-b") as handle:
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 2, "owner-b"
        )
        assert (
            await handle.execute(
                "UPDATE isolation_fixture.owner_probe SET id = $1 WHERE id = $2", 3, 1
            )
            == "UPDATE 0"
        )
        assert (
            await handle.execute(
                "DELETE FROM isolation_fixture.owner_probe WHERE id = $1", 1
            )
            == "DELETE 0"
        )
        assert (
            await handle.execute(
                "UPDATE isolation_fixture.owner_probe SET id = $1 WHERE id = $2", 3, 2
            )
            == "UPDATE 1"
        )
        own = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert [row["id"] for row in own] == [3]
        assert (
            await handle.execute(
                "DELETE FROM isolation_fixture.owner_probe WHERE id = $1", 3
            )
            == "DELETE 1"
        )
    async with database.transaction(owner_id="owner-a") as handle:
        own = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert [row["id"] for row in own] == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", [None, ""])
async def test_missing_context_has_no_access_after_owner_commit(
    isolation_database, owner
):
    database = isolation_database
    async with database.transaction(owner_id="owner-a") as handle:
        pid = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
    assert (
        len(await database.fetch("SELECT id FROM isolation_fixture.owner_probe")) == 0
    )
    async with database.transaction(owner_id=owner) as handle:
        identity = (
            await handle.fetch("""
            SELECT pg_backend_pid() AS pid,
                nullif(current_setting('app.owner_id', true), '') AS owner
        """)
        )[0]
        assert identity["pid"] == pid
        assert identity["owner"] is None
        assert (
            len(await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")) == 0
        )
        assert (
            await handle.execute(
                "UPDATE isolation_fixture.owner_probe SET id = $1 WHERE id = $2", 2, 1
            )
            == "UPDATE 0"
        )
        assert (
            await handle.execute(
                "DELETE FROM isolation_fixture.owner_probe WHERE id = $1", 1
            )
            == "DELETE 0"
        )
    with pytest.raises(DatabaseError, match="^DATABASE_QUERY_FAILED$"):
        async with database.transaction(owner_id=owner) as handle:
            await handle.execute(
                "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)",
                2,
                "owner-a",
            )
    async with database.transaction(owner_id="owner-a") as handle:
        own = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert [row["id"] for row in own] == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM isolation_fixture.owner_probe",
        "INSERT INTO isolation_fixture.owner_probe VALUES (2, 'owner-a')",
        "UPDATE isolation_fixture.owner_probe SET id = 2 WHERE id = 1",
        "DELETE FROM isolation_fixture.owner_probe WHERE id = 1",
    ],
    ids=["read", "insert", "update", "delete"],
)
async def test_training_login_cannot_access_protected_fixture(isolation_database, sql):
    database = isolation_database
    async with database.transaction(owner_id="owner-a") as handle:
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
    training = await connect(
        "python_foundation_training", "synthetic-python-foundation-training-only"
    )
    try:
        assert (
            await training.fetchval("SELECT current_user")
            == "python_foundation_training"
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with training.transaction():
                await training.execute(
                    "SELECT set_config('app.owner_id', $1, true)", "owner-a"
                )
                await training.execute(sql)
    finally:
        await training.close(timeout=5)
    async with database.transaction(owner_id="owner-a") as handle:
        own = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert [row["id"] for row in own] == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome", ["commit", "rollback", "sql-error", "timeout", "cancel"]
)
async def test_owner_access_is_local_after_every_transaction_outcome(
    isolation_database, migration_database, outcome
):
    database = isolation_database
    observer = migration_database
    async with database.transaction(owner_id="owner-a") as handle:
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
    entered = asyncio.Event()
    pid = None

    async def work():
        nonlocal pid
        async with database.transaction(owner_id="owner-a") as handle:
            pid = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
            await handle.execute(
                "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)",
                2,
                "owner-a",
            )
            if outcome == "timeout":
                await handle.execute(
                    "SELECT set_config('statement_timeout', $1, true)", "50ms"
                )
            entered.set()
            if outcome == "commit":
                return
            if outcome == "rollback":
                raise RuntimeError("FOUNDATION_EXPECTED_ROLLBACK")
            if outcome == "sql-error":
                with pytest.raises(DatabaseError, match="^DATABASE_QUERY_FAILED$"):
                    await handle.execute(
                        "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)",
                        2,
                        "owner-a",
                    )
                return
            await handle.fetch("SELECT pg_sleep(10)")

    task = asyncio.create_task(work())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if outcome == "cancel":
            async with asyncio.timeout(3):
                while not await observer.fetchval(
                    "SELECT EXISTS (SELECT FROM pg_stat_activity WHERE pid = $1 AND wait_event = 'PgSleep')",
                    pid,
                ):
                    pass
            task.cancel()
        if outcome == "commit":
            await asyncio.wait_for(task, 5)
        else:
            expected = {
                "rollback": RuntimeError,
                "sql-error": DatabaseError,
                "timeout": DatabaseError,
                "cancel": asyncio.CancelledError,
            }[outcome]
            with pytest.raises(expected) as failure:
                await asyncio.wait_for(task, 5)
            codes = {
                "rollback": "FOUNDATION_EXPECTED_ROLLBACK",
                "sql-error": "DATABASE_TRANSACTION_ABORTED",
                "timeout": "DATABASE_QUERY_FAILED",
                "cancel": "",
            }
            assert str(failure.value) == codes[outcome]
            assert getattr(failure.value, "commit_outcome", None) is None
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    for owner in ("owner-b", None):
        async with database.transaction(owner_id=owner) as handle:
            identity = (
                await handle.fetch("""
                SELECT pg_backend_pid() AS pid,
                    nullif(current_setting('app.owner_id', true), '') AS owner
            """)
            )[0]
            assert identity["pid"] == pid, "FOUNDATION_MAX_ONE_MUST_REUSE_CONNECTION"
            assert identity["owner"] == owner
            assert (
                len(await handle.fetch("SELECT id FROM isolation_fixture.owner_probe"))
                == 0
            )
    async with database.transaction(owner_id="owner-a") as handle:
        own = await handle.fetch(
            "SELECT id FROM isolation_fixture.owner_probe ORDER BY id"
        )
        assert [row["id"] for row in own] == ([1, 2] if outcome == "commit" else [1])


@pytest.mark.asyncio
async def test_fixture_has_forced_policy_and_minimal_role_grants(
    isolation_database, migration_database
):
    observer = migration_database
    table = await observer.fetchrow("""
        SELECT relrowsecurity AS enabled, relforcerowsecurity AS forced,
            pg_get_userbyid(relowner) AS owner,
            NOT EXISTS (SELECT FROM aclexplode(relacl) WHERE grantee = 0) AS private
        FROM pg_class WHERE oid = 'isolation_fixture.owner_probe'::regclass
    """)
    assert dict(table) == {
        "enabled": True,
        "forced": True,
        "owner": "python_foundation_migrator",
        "private": True,
    }
    policies = await observer.fetch("""
        SELECT policyname, roles::text[], cmd, qual IS NOT NULL AS using_present,
            with_check IS NOT NULL AS check_present
        FROM pg_policies WHERE schemaname = 'isolation_fixture'
            AND tablename = 'owner_probe'
    """)
    assert [dict(row) for row in policies] == [
        {
            "policyname": "owner_isolation",
            "roles": ["python_foundation_runtime"],
            "cmd": "ALL",
            "using_present": True,
            "check_present": True,
        }
    ]
    roles = await observer.fetch("""
        SELECT rolname, (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolinherit
                OR EXISTS (SELECT FROM pg_auth_members WHERE member = r.oid)
                OR EXISTS (SELECT FROM pg_namespace WHERE nspowner = r.oid)
                OR EXISTS (SELECT FROM pg_class WHERE relowner = r.oid)) AS elevated
        FROM pg_roles r WHERE rolname IN (
            'python_foundation_runtime', 'python_foundation_training'
        ) ORDER BY rolname
    """)
    assert [tuple(row) for row in roles] == [
        ("python_foundation_runtime", False),
        ("python_foundation_training", False),
    ]
    for role in ("python_foundation_runtime", "python_foundation_training"):
        runtime = role == "python_foundation_runtime"
        assert (
            await observer.fetchval(
                "SELECT has_schema_privilege($1, 'isolation_fixture', 'USAGE')", role
            )
            is runtime
        )
        assert (
            await observer.fetchval(
                "SELECT has_schema_privilege($1, 'isolation_fixture', 'CREATE')", role
            )
            is False
        )
        privileges = await observer.fetch(
            """
            SELECT privilege FROM unnest(ARRAY[
                'DELETE', 'INSERT', 'REFERENCES', 'SELECT', 'TRIGGER', 'TRUNCATE', 'UPDATE'
            ]) AS privilege
            WHERE has_table_privilege($1, 'isolation_fixture.owner_probe', privilege)
            ORDER BY privilege
        """,
            role,
        )
        assert [row["privilege"] for row in privileges] == (
            ["DELETE", "INSERT", "SELECT", "UPDATE"] if runtime else []
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["runtime", "training"])
@pytest.mark.parametrize(
    "sql",
    [
        "TRUNCATE isolation_fixture.owner_probe",
        "CREATE TABLE isolation_fixture.ddl_probe (id integer)",
        "CREATE SCHEMA isolation_unauthorized",
        "CREATE TEMP TABLE isolation_temp_probe (id integer)",
        "ALTER TABLE isolation_fixture.owner_probe DISABLE ROW LEVEL SECURITY",
        "DROP TABLE isolation_fixture.owner_probe",
        "SET ROLE python_foundation_migrator",
        "SET ROLE python_foundation_bootstrap",
        "ALTER ROLE python_foundation_runtime SUPERUSER",
    ],
    ids=[
        "truncate",
        "create-table",
        "create-schema",
        "create-temp",
        "disable-rls",
        "drop-table",
        "assume-migrator",
        "assume-bootstrap",
        "superuser",
    ],
)
async def test_restricted_logins_cannot_truncate_change_schema_or_elevate(
    isolation_database, role, sql
):
    database = isolation_database
    async with database.transaction(owner_id="owner-a") as handle:
        await handle.execute(
            "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)", 1, "owner-a"
        )
    login = await connect(
        f"python_foundation_{role}", f"synthetic-python-foundation-{role}-only"
    )
    try:
        assert (
            await login.fetchval("SELECT current_user") == f"python_foundation_{role}"
        )
        async with login.transaction():
            await login.execute(
                "SELECT set_config('app.owner_id', $1, true)", "owner-a"
            )
            # An unexpected success raises inside this transaction and rolls it back.
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await login.execute(sql)
        assert (
            await login.fetchval("SELECT current_user") == f"python_foundation_{role}"
        )
    finally:
        await login.close(timeout=5)
    async with database.transaction(owner_id="owner-a") as handle:
        own = await handle.fetch("SELECT id FROM isolation_fixture.owner_probe")
        assert [row["id"] for row in own] == [1]
