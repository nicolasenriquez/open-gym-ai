"""Platform role bootstrap, Alembic lock and forward-only history proofs."""

import asyncio
import json
import os
import shutil
import signal
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

BOOTSTRAP_USER = "opengym_platform_bootstrap"
BOOTSTRAP_PASSWORD = "synthetic-opengym-platform-only"
MIGRATOR_USER = "opengym_migrator"
MIGRATOR_PASSWORD = "synthetic-opengym-platform-migrator-only"
RUNTIME_USER = "opengym_api_runtime"
RUNTIME_PASSWORD = "synthetic-opengym-platform-runtime-only"
TARGET = {
    "PLATFORM_DB_HOST": "platform-db",
    "PLATFORM_DB_PORT": "5432",
    "PLATFORM_DB_NAME": "opengym_platform_test",
    "PLATFORM_DB_USER": BOOTSTRAP_USER,
    "PLATFORM_DB_PASSWORD": BOOTSTRAP_PASSWORD,
}


@asynccontextmanager
async def migration_process(*arguments, env=None):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.platform_migrate",
        *arguments,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield process
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def migrate(*arguments, env=None):
    async with migration_process(*arguments, env=env) as process:
        output, diagnostic = await asyncio.wait_for(process.communicate(), timeout=35)
    assert diagnostic == b"", "PLATFORM_MIGRATION_UNSAFE_STDERR"
    try:
        result = json.loads(output)
    except ValueError, UnicodeError:
        pytest.fail("PLATFORM_MIGRATION_INVALID_OUTPUT", pytrace=False)
    return process.returncode, result


async def connect(user, password):
    return await asyncpg.connect(
        host="platform-db",
        port=5432,
        database="opengym_platform_test",
        user=user,
        password=password,
        ssl=False,
        timeout=5,
        command_timeout=5,
    )


def probe_env(tmp_path, blocking):
    """Copy the package and add a private child revision without editing delivery."""
    package = tmp_path / "opengym_platform"
    shutil.copytree(Path(__file__).parents[2] / "src/opengym_platform", package)
    statements = ['    op.execute("CREATE SCHEMA schema_probe")']
    if blocking:
        statements.append('    op.execute("SELECT pg_advisory_xact_lock(728323)")')
    (package / "platform_migrations/versions/p001_probe.py").write_text(
        "from alembic import op\n\n"
        'revision = "p001_probe"\n'
        'down_revision = "p001_identity_session"\n\n\n'
        "def upgrade():\n" + "\n".join(statements) + "\n",
        encoding="utf-8",
    )
    return {**os.environ, "PYTHONPATH": str(tmp_path)}


async def history(observer):
    return [
        row["version_num"]
        for row in await observer.fetch(
            "SELECT version_num FROM public.alembic_version"
        )
    ]


async def wait_for_lock(observer, key):
    async with asyncio.timeout(4):
        while not await observer.fetchval("SELECT pg_try_advisory_lock($1)", key):
            await asyncio.sleep(0.02)
    await observer.fetchval("SELECT pg_advisory_unlock($1)", key)


@pytest_asyncio.fixture
async def migration_database():
    assert tuple(os.environ.get(key) for key in TARGET) == tuple(TARGET.values())
    observer = await connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD)
    try:
        tables = await observer.fetchval(
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
        )
        assert tables == 0, "PLATFORM_MIGRATION_FIXTURE_MUST_START_EMPTY"
        assert await migrate("bootstrap") == (
            0,
            {"code": "PLATFORM_MIGRATION_BOOTSTRAP_OK"},
        )
        yield observer
    finally:
        try:
            await observer.execute("""
                DROP SCHEMA IF EXISTS schema_probe CASCADE;
                DROP SCHEMA IF EXISTS identity CASCADE;
                DROP TABLE IF EXISTS public.alembic_version;
                ALTER SCHEMA public OWNER TO opengym_platform_bootstrap;
                DROP OWNED BY opengym_schema_owner, opengym_migrator, opengym_api_runtime,
                    opengym_identity_executor;
                DROP ROLE opengym_schema_owner, opengym_migrator, opengym_api_runtime,
                    opengym_identity_executor;
            """)
        finally:
            await observer.close(timeout=5)


@pytest.mark.asyncio
async def test_empty_database_reaches_head_and_runtime_cannot_mutate_history(
    migration_database,
):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    assert await history(observer) == ["p001_identity_session"]
    metadata = await observer.fetchrow("""
        SELECT pg_get_userbyid(n.nspowner) AS owner
        FROM pg_namespace n WHERE n.nspname = 'public'
    """)
    assert metadata["owner"] == "opengym_schema_owner"
    assert (
        await observer.fetchval("""
        SELECT pg_get_userbyid(relowner) FROM pg_class
        WHERE oid = 'public.alembic_version'::regclass
    """)
        == "opengym_schema_owner"
    )
    roles = await observer.fetch("""
        SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole,
               rolreplication, rolinherit, rolcanlogin
        FROM pg_roles WHERE rolname IN (
            'opengym_schema_owner', 'opengym_migrator', 'opengym_api_runtime'
        ) ORDER BY rolname
    """)
    assert [(row["rolname"], tuple(row[1:])) for row in roles] == [
        ("opengym_api_runtime", (False,) * 6 + (True,)),
        ("opengym_migrator", (False,) * 6 + (True,)),
        ("opengym_schema_owner", (False,) * 7),
    ]
    assert (
        await observer.fetchval("""
        SELECT count(*) FROM pg_auth_members m
        JOIN pg_roles member ON member.oid = m.member
        WHERE member.rolname IN (
            'opengym_schema_owner', 'opengym_migrator', 'opengym_api_runtime'
        ) AND NOT (
            member.rolname = 'opengym_migrator' AND m.roleid = (
                SELECT oid FROM pg_roles WHERE rolname = 'opengym_schema_owner'
            )
        ) AND NOT (
            member.rolname = 'opengym_schema_owner' AND m.roleid = (
                SELECT oid FROM pg_roles WHERE rolname = 'opengym_identity_executor'
            )
        )
    """)
        == 0
    )
    runtime = await connect(RUNTIME_USER, RUNTIME_PASSWORD)
    try:
        assert await history(runtime) == ["p001_identity_session"]
        for statement in (
            "CREATE SCHEMA forbidden",
            "CREATE TABLE public.forbidden (id integer)",
            "TRUNCATE public.alembic_version",
            "INSERT INTO public.alembic_version VALUES ('forbidden')",
            "UPDATE public.alembic_version SET version_num = 'forbidden'",
            "DELETE FROM public.alembic_version",
            "SET ROLE opengym_schema_owner",
            "SET ROLE opengym_migrator",
            "CREATE ROLE forbidden",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(statement)
        assert not await runtime.fetchval(
            "SELECT has_database_privilege(current_user, current_database(),"
            " 'CREATE,TEMP')"
        )
        assert not await runtime.fetchval(
            "SELECT has_schema_privilege('opengym_api_runtime', 'public', 'CREATE')"
        )
    finally:
        await runtime.close(timeout=5)


@pytest.mark.asyncio
async def test_owner_default_privileges_do_not_expose_execute(
    migration_database,
):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    migrator = await connect(MIGRATOR_USER, MIGRATOR_PASSWORD)
    try:
        await migrator.execute("SET ROLE opengym_schema_owner")
        await migrator.execute("""
            CREATE FUNCTION public.platform_default_execute_probe()
            RETURNS integer LANGUAGE sql AS 'SELECT 1'
        """)
    finally:
        await migrator.close(timeout=5)
    assert not await observer.fetchval("""
        SELECT has_function_privilege('opengym_api_runtime',
            'public.platform_default_execute_probe()', 'EXECUTE')
    """)


@pytest.mark.asyncio
@pytest.mark.parametrize("from_prefix", [False, True])
async def test_genuine_previous_revision_reaches_head_without_replay(
    migration_database, tmp_path, from_prefix
):
    observer = migration_database
    env = probe_env(tmp_path, blocking=False)
    if from_prefix:
        assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
        original = await observer.fetchrow("""
            SELECT oid, pg_get_userbyid(nspowner) AS owner
            FROM pg_namespace WHERE nspname = 'public'
        """)
    assert await migrate("up", env=env) == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    before_rerun = await observer.fetch("""
        SELECT nspname, oid, pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace WHERE nspname = 'schema_probe'
    """)
    assert [(row["nspname"], row["owner"]) for row in before_rerun] == [
        ("schema_probe", "opengym_schema_owner")
    ]
    if from_prefix:
        assert (
            await observer.fetchrow("""
            SELECT oid, pg_get_userbyid(nspowner) AS owner
            FROM pg_namespace WHERE nspname = 'public'
        """)
            == original
        )
    assert await migrate("up", env=env) == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    assert (
        await observer.fetch("""
        SELECT nspname, oid, pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace WHERE nspname = 'schema_probe'
    """)
        == before_rerun
    )
    assert await history(observer) == ["p001_probe"]


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["sigterm", "disconnect"])
async def test_interrupted_revision_preserves_prefix_and_rerun_recovers(
    migration_database, tmp_path, interruption
):
    observer = migration_database
    env = probe_env(tmp_path, blocking=True)
    assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    await observer.fetchval("SELECT pg_advisory_lock(728323)")
    try:
        async with migration_process("up", env=env) as process:
            async with asyncio.timeout(4):
                while not await observer.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM pg_locks l JOIN pg_stat_activity a USING (pid)
                        WHERE a.application_name = 'opengym-platform-migrate'
                          AND l.locktype = 'advisory' AND l.objid = 728323
                          AND NOT l.granted
                          AND EXISTS (SELECT FROM pg_locks h WHERE h.pid = l.pid
                              AND h.locktype = 'advisory' AND h.objid = 728322
                              AND h.granted)
                    )
                """):
                    await asyncio.sleep(0.02)
            assert await history(observer) == ["p001_identity_session"]
            assert (
                await observer.fetchval("SELECT to_regnamespace('schema_probe')")
                is None
            )
            if interruption == "sigterm":
                process.terminate()
            else:
                backend_pid = await observer.fetchval("""
                    SELECT pid FROM pg_stat_activity
                    WHERE application_name = 'opengym-platform-migrate'
                      AND usename = 'opengym_migrator'
                """)
                assert backend_pid is not None
                assert await observer.fetchval(
                    "SELECT pg_terminate_backend($1)", backend_pid
                )
            output, diagnostic = await asyncio.wait_for(
                process.communicate(), timeout=10
            )
            assert diagnostic == b""
            if interruption == "sigterm":
                assert process.returncode == -signal.SIGTERM
                assert output == b""
            else:
                assert process.returncode == 1
                assert json.loads(output) == {"code": "PLATFORM_MIGRATION_FAILED"}
    finally:
        await observer.fetchval("SELECT pg_advisory_unlock(728323)")
    await wait_for_lock(observer, 728322)
    assert await history(observer) == ["p001_identity_session"]
    assert await observer.fetchval("SELECT to_regnamespace('schema_probe')") is None
    assert await migrate("up", env=env) == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    assert await history(observer) == ["p001_probe"]
    assert await observer.fetchval("SELECT to_regnamespace('schema_probe')") is not None


@pytest.mark.asyncio
async def test_failed_revision_preserves_prefix_and_rerun_recovers(
    migration_database, tmp_path
):
    observer = migration_database
    env = probe_env(tmp_path, blocking=False)
    assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    await observer.execute("CREATE SCHEMA schema_probe")
    assert await migrate("up", env=env) == (
        1,
        {"code": "PLATFORM_MIGRATION_FAILED"},
    )
    assert await history(observer) == ["p001_identity_session"]
    await wait_for_lock(observer, 728322)
    await observer.execute("DROP SCHEMA schema_probe")
    assert await migrate("up", env=env) == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    assert await history(observer) == ["p001_probe"]


@pytest.mark.asyncio
async def test_lock_precedes_unknown_history_and_does_not_fabricate_it(
    migration_database,
):
    observer = migration_database
    await observer.execute("""
        CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY);
        INSERT INTO public.alembic_version VALUES ('unknown_fixture');
        ALTER TABLE public.alembic_version OWNER TO opengym_schema_owner;
    """)
    await observer.fetchval("SELECT pg_advisory_lock(728322)")
    try:
        assert await migrate("up") == (1, {"code": "PLATFORM_MIGRATION_LOCKED"})
    finally:
        await observer.fetchval("SELECT pg_advisory_unlock(728322)")
    assert await migrate("up") == (1, {"code": "PLATFORM_MIGRATION_FAILED"})
    assert await history(observer) == ["unknown_fixture"]
    assert await observer.fetchval("SELECT to_regnamespace('schema_probe')") is None
    await wait_for_lock(observer, 728322)


@pytest.mark.asyncio
async def test_only_lock_owner_applies_pending_revision_after_history_read(
    migration_database, tmp_path
):
    observer = migration_database
    env = probe_env(tmp_path, blocking=False)
    assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    async with AsyncExitStack() as cleanup:
        async with observer.transaction():
            await observer.execute(
                "LOCK TABLE public.alembic_version IN ACCESS EXCLUSIVE MODE"
            )
            owner = await cleanup.enter_async_context(migration_process("up", env=env))
            async with asyncio.timeout(4):
                while not await observer.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM pg_locks l JOIN pg_stat_activity a USING (pid)
                        WHERE a.application_name = 'opengym-platform-migrate'
                          AND l.locktype = 'advisory' AND l.objid = 728322
                          AND l.granted
                          AND EXISTS (SELECT FROM pg_locks w WHERE w.pid = l.pid
                              AND NOT w.granted)
                    )
                """):
                    await asyncio.sleep(0.02)
            assert await migrate("up", env=env) == (
                1,
                {"code": "PLATFORM_MIGRATION_LOCKED"},
            )
            assert await history(observer) == ["p001_identity_session"]
            assert (
                await observer.fetchval("SELECT to_regnamespace('schema_probe')")
                is None
            )
        output, diagnostic = await asyncio.wait_for(owner.communicate(), timeout=10)
    assert owner.returncode == 0
    assert diagnostic == b""
    assert json.loads(output) == {"code": "PLATFORM_MIGRATION_UP_OK"}
    assert await history(observer) == ["p001_probe"]
    assert (
        await observer.fetchval("""
        SELECT pg_get_userbyid(nspowner) FROM pg_namespace
        WHERE nspname = 'schema_probe'
    """)
        == "opengym_schema_owner"
    )
    await wait_for_lock(observer, 728322)


@pytest.mark.asyncio
async def test_bootstrap_rerun_removes_excess_runtime_grants(migration_database):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "PLATFORM_MIGRATION_UP_OK"})
    await observer.execute("""
        GRANT CREATE, TEMP ON DATABASE opengym_platform_test TO opengym_api_runtime;
        GRANT CREATE ON SCHEMA public TO opengym_api_runtime;
        GRANT INSERT, UPDATE, DELETE, TRUNCATE ON TABLE public.alembic_version
            TO opengym_api_runtime;
    """)
    assert await migrate("bootstrap") == (
        0,
        {"code": "PLATFORM_MIGRATION_BOOTSTRAP_OK"},
    )
    excessive = await observer.fetchval("""
        SELECT has_database_privilege('opengym_api_runtime', current_database(),
                'CREATE,TEMP')
            OR has_schema_privilege('opengym_api_runtime', 'public', 'CREATE')
            OR has_table_privilege('opengym_api_runtime', 'public.alembic_version',
                'INSERT,UPDATE,DELETE,TRUNCATE')
    """)
    assert not excessive, "PLATFORM_RUNTIME_EXCESS_GRANTS"
    assert await observer.fetchval("""
        SELECT has_table_privilege('opengym_api_runtime', 'public.alembic_version',
            'SELECT')
    """)


@pytest.mark.asyncio
async def test_bootstrap_refuses_elevating_memberships(migration_database):
    observer = migration_database
    await observer.execute("GRANT opengym_schema_owner TO opengym_api_runtime")
    assert await migrate("bootstrap") == (
        1,
        {"code": "PLATFORM_MIGRATION_ROLES_REJECTED"},
    )
    await observer.execute("REVOKE opengym_schema_owner FROM opengym_api_runtime")
    assert await migrate("bootstrap") == (
        0,
        {"code": "PLATFORM_MIGRATION_BOOTSTRAP_OK"},
    )


@pytest.mark.asyncio
async def test_cli_rejects_unsafe_targets_and_uncontrolled_actions():
    for arguments in (
        (),
        ("stamp",),
        ("down",),
        ("up", "--no-lock"),
        ("up", "/tmp/other"),
    ):
        assert await migrate(*arguments) == (
            1,
            {"code": "PLATFORM_MIGRATION_ARGUMENTS_REJECTED"},
        )
    for key, value in (
        ("PLATFORM_DB_HOST", "external.invalid"),
        ("PLATFORM_DB_PORT", "5433"),
        ("PLATFORM_DB_NAME", "other"),
        ("PLATFORM_DB_USER", "other"),
        ("PLATFORM_DB_PASSWORD", "synthetic-secret-dsn"),
    ):
        assert await migrate("up", env={**os.environ, key: value}) == (
            1,
            {"code": "PLATFORM_MIGRATION_TARGET_REJECTED"},
        )
