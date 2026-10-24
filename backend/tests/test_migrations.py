"""Migration CLI proofs against a fresh disposable PostgreSQL database."""

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


@asynccontextmanager
async def migration_process(*arguments, env=None):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.migrate",
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
    assert diagnostic == b"", "FOUNDATION_MIGRATION_UNSAFE_STDERR"
    try:
        result = json.loads(output)
    except ValueError, UnicodeError:
        pytest.fail("FOUNDATION_MIGRATION_INVALID_OUTPUT", pytrace=False)
    return process.returncode, result


async def connect(user, password):
    return await asyncpg.connect(
        host="foundation-db",
        port=5432,
        database="python_foundation_test",
        user=user,
        password=password,
        ssl=False,
        timeout=5,
        command_timeout=5,
    )


@pytest_asyncio.fixture
async def migration_database():
    assert tuple(
        os.environ.get(key)
        for key in (
            "FOUNDATION_DB_HOST",
            "FOUNDATION_DB_PORT",
            "FOUNDATION_DB_NAME",
            "FOUNDATION_DB_USER",
            "FOUNDATION_DB_PASSWORD",
        )
    ) == (
        "foundation-db",
        "5432",
        "python_foundation_test",
        "python_foundation_bootstrap",
        "synthetic-python-foundation-only",
    )
    observer = await connect(
        "python_foundation_bootstrap", "synthetic-python-foundation-only"
    )
    try:
        tables = await observer.fetchval(
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
        )
        assert tables == 0, "FOUNDATION_MIGRATION_FIXTURE_MUST_START_EMPTY"
        assert await migrate("bootstrap") == (
            0,
            {"code": "FOUNDATION_MIGRATION_BOOTSTRAP_OK"},
        )
        yield observer
    finally:
        try:
            await observer.execute("""
                DROP SCHEMA IF EXISTS foundation CASCADE;
                DROP SCHEMA IF EXISTS foundation_migration_probe CASCADE;
                DROP TABLE IF EXISTS public.alembic_version;
                ALTER SCHEMA public OWNER TO python_foundation_bootstrap;
                DROP OWNED BY python_foundation_migrator, python_foundation_runtime, python_foundation_training;
                DROP ROLE python_foundation_migrator, python_foundation_runtime, python_foundation_training;
            """)
        finally:
            await observer.close(timeout=5)


@pytest.mark.asyncio
async def test_up_from_empty_database_records_one_revision(migration_database):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    history = await observer.fetchval("SELECT to_regclass('public.alembic_version')")
    assert history is not None, "FOUNDATION_MIGRATION_HISTORY_REQUIRED"
    revisions = await observer.fetch("SELECT version_num FROM public.alembic_version")
    assert [row["version_num"] for row in revisions] == ["0001_infrastructure"]
    assert await observer.fetchval("SELECT to_regnamespace('foundation')") is not None


@pytest.fixture
def migration_probe(tmp_path):
    # A private graph tests genuine prefixes without changing delivered revisions/CLI.
    package = tmp_path / "opengym_platform"
    shutil.copytree(Path(__file__).parents[1] / "src/opengym_platform", package)
    (package / "migrations/versions/0002_probe.py").write_text(
        "from alembic import op\n"
        'revision = "0002_probe"\n'
        'down_revision = "0001_infrastructure"\n'
        "def upgrade():\n"
        '    op.execute("CREATE SCHEMA foundation_migration_probe")\n'
        '    op.execute("SELECT pg_advisory_xact_lock(728323)")\n',
        encoding="utf-8",
    )
    return {**os.environ, "PYTHONPATH": str(tmp_path)}


@pytest.mark.asyncio
@pytest.mark.parametrize("from_prefix", [False, True])
async def test_empty_and_genuine_prefix_reach_same_head_without_replay(
    migration_database, migration_probe, from_prefix
):
    observer = migration_database
    if from_prefix:
        assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
        assert (
            await observer.fetchval("SELECT version_num FROM public.alembic_version")
            == "0001_infrastructure"
        )
        original_oid = await observer.fetchval(
            "SELECT oid FROM pg_namespace WHERE nspname = 'foundation'"
        )
    assert await migrate("up", env=migration_probe) == (
        0,
        {"code": "FOUNDATION_MIGRATION_UP_OK"},
    )
    before_rerun = await observer.fetch("""
        SELECT nspname, oid, pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace WHERE nspname IN ('foundation', 'foundation_migration_probe')
        ORDER BY nspname
    """)
    assert [(row["nspname"], row["owner"]) for row in before_rerun] == [
        ("foundation", "python_foundation_migrator"),
        ("foundation_migration_probe", "python_foundation_migrator"),
    ]
    if from_prefix:
        assert before_rerun[0]["oid"] == original_oid
    assert await migrate("up", env=migration_probe) == (
        0,
        {"code": "FOUNDATION_MIGRATION_UP_OK"},
    )
    assert (
        await observer.fetch("""
        SELECT nspname, oid, pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace WHERE nspname IN ('foundation', 'foundation_migration_probe')
        ORDER BY nspname
    """)
        == before_rerun
    )
    assert [
        row["version_num"]
        for row in await observer.fetch(
            "SELECT version_num FROM public.alembic_version"
        )
    ] == ["0002_probe"]


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["sigterm", "disconnect"])
async def test_interrupted_revision_preserves_prefix_and_rerun_recovers(
    migration_database, migration_probe, interruption
):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    await observer.fetchval("SELECT pg_advisory_lock(728323)")
    try:
        async with migration_process("up", env=migration_probe) as process:
            async with asyncio.timeout(4):
                while not await observer.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM pg_locks l JOIN pg_stat_activity a USING (pid)
                        WHERE a.application_name = 'opengym-foundation-migrate'
                          AND l.locktype = 'advisory' AND l.objid = 728323 AND NOT l.granted
                          AND EXISTS (SELECT FROM pg_locks h WHERE h.pid = l.pid
                              AND h.locktype = 'advisory' AND h.objid = 728322 AND h.granted)
                    )
                """):
                    await asyncio.sleep(0.02)
            assert (
                await observer.fetchval(
                    "SELECT version_num FROM public.alembic_version"
                )
                == "0001_infrastructure"
            )
            assert (
                await observer.fetchval(
                    "SELECT to_regnamespace('foundation_migration_probe')"
                )
                is None
            )
            if interruption == "sigterm":
                process.terminate()
            else:
                backend_pid = await observer.fetchval("""
                    SELECT pid FROM pg_stat_activity
                    WHERE application_name = 'opengym-foundation-migrate'
                      AND usename = 'python_foundation_migrator'
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
                assert json.loads(output) == {"code": "FOUNDATION_MIGRATION_FAILED"}
    finally:
        await observer.fetchval("SELECT pg_advisory_unlock(728323)")
    async with asyncio.timeout(4):
        while not await observer.fetchval("SELECT pg_try_advisory_lock(728322)"):
            await asyncio.sleep(0.02)
    await observer.fetchval("SELECT pg_advisory_unlock(728322)")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "0001_infrastructure"
    )
    assert (
        await observer.fetchval("SELECT to_regnamespace('foundation_migration_probe')")
        is None
    )
    assert await migrate("up", env=migration_probe) == (
        0,
        {"code": "FOUNDATION_MIGRATION_UP_OK"},
    )
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "0002_probe"
    )
    assert (
        await observer.fetchval("SELECT to_regnamespace('foundation_migration_probe')")
        is not None
    )


@pytest.mark.asyncio
async def test_bootstrap_rerun_removes_excess_runtime_grants(migration_database):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    await observer.execute("""
        GRANT CREATE, TEMP ON DATABASE python_foundation_test TO python_foundation_runtime;
        GRANT CREATE ON SCHEMA public, foundation TO python_foundation_runtime;
    """)
    assert await migrate("bootstrap") == (
        0,
        {"code": "FOUNDATION_MIGRATION_BOOTSTRAP_OK"},
    )
    excessive = await observer.fetchval("""
        SELECT has_database_privilege('python_foundation_runtime', current_database(), 'CREATE,TEMP')
            OR has_schema_privilege('python_foundation_runtime', 'public', 'CREATE')
            OR has_schema_privilege('python_foundation_runtime', 'foundation', 'CREATE')
    """)
    assert not excessive, "FOUNDATION_RUNTIME_EXCESS_GRANTS"


@pytest.mark.asyncio
async def test_runtime_roles_have_no_ddl_ownership_or_elevation(migration_database):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    roles = await observer.fetch("""
        SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole,
               rolreplication, rolinherit
        FROM pg_roles WHERE rolname IN (
            'python_foundation_runtime', 'python_foundation_training'
        ) ORDER BY rolname
    """)
    assert len(roles) == 2
    for role in roles:
        assert not any(role[1:])
    assert (
        await observer.fetchval("""
        SELECT count(*) FROM pg_auth_members WHERE member IN (
            SELECT oid FROM pg_roles WHERE rolname IN (
                'python_foundation_runtime', 'python_foundation_training'
            )
        )
    """)
        == 0
    )
    for suffix in ("runtime", "training"):
        connection = await connect(
            f"python_foundation_{suffix}",
            f"synthetic-python-foundation-{suffix}-only",
        )
        try:
            assert (
                await connection.fetchval("SELECT current_user")
                == f"python_foundation_{suffix}"
            )
            for statement in (
                "CREATE SCHEMA forbidden",
                "CREATE TABLE public.forbidden (id integer)",
                "CREATE TABLE foundation.forbidden (id integer)",
                "CREATE TEMP TABLE forbidden (id integer)",
                "SET ROLE python_foundation_migrator",
                "SET ROLE python_foundation_bootstrap",
                "CREATE ROLE forbidden",
                "TRUNCATE public.alembic_version",
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(statement)
            assert not await connection.fetchval(
                "SELECT has_database_privilege(current_user, current_database(), 'CREATE,TEMP')"
            )
            assert not await connection.fetchval(
                "SELECT has_schema_privilege(current_user, 'foundation', 'CREATE')"
            )
        finally:
            await connection.close(timeout=5)
    owners = await observer.fetch("""
        SELECT nspname, pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace WHERE nspname IN ('foundation', 'public') ORDER BY nspname
    """)
    assert [(row["nspname"], row["owner"]) for row in owners] == [
        ("foundation", "python_foundation_migrator"),
        ("public", "python_foundation_migrator"),
    ]


@pytest.mark.asyncio
async def test_bootstrap_refuses_elevating_memberships(migration_database):
    observer = migration_database
    await observer.execute(
        "GRANT python_foundation_migrator TO python_foundation_runtime"
    )
    assert await migrate("bootstrap") == (
        1,
        {"code": "FOUNDATION_MIGRATION_ROLES_REJECTED"},
    )
    await observer.execute(
        "REVOKE python_foundation_migrator FROM python_foundation_runtime"
    )
    assert await migrate("bootstrap") == (
        0,
        {"code": "FOUNDATION_MIGRATION_BOOTSTRAP_OK"},
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
            {"code": "FOUNDATION_MIGRATION_ARGUMENTS_REJECTED"},
        )
    for key, value in (
        ("FOUNDATION_DB_HOST", "external.invalid"),
        ("FOUNDATION_DB_PORT", "5433"),
        ("FOUNDATION_DB_NAME", "other"),
        ("FOUNDATION_DB_USER", "other"),
        ("FOUNDATION_DB_PASSWORD", "synthetic-secret-dsn"),
    ):
        assert await migrate("up", env={**os.environ, key: value}) == (
            1,
            {"code": "FOUNDATION_MIGRATION_TARGET_REJECTED"},
        )


@pytest.mark.asyncio
async def test_lock_precedes_unknown_history_and_does_not_fabricate_it(
    migration_database,
):
    observer = migration_database
    await observer.execute("""
        CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY);
        INSERT INTO public.alembic_version VALUES ('unknown_fixture');
        ALTER TABLE public.alembic_version OWNER TO python_foundation_migrator;
    """)
    await observer.fetchval("SELECT pg_advisory_lock(728322)")
    try:
        assert await migrate("up") == (1, {"code": "FOUNDATION_MIGRATION_LOCKED"})
    finally:
        await observer.fetchval("SELECT pg_advisory_unlock(728322)")
    assert await migrate("up") == (1, {"code": "FOUNDATION_MIGRATION_FAILED"})
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "unknown_fixture"
    )
    assert await observer.fetchval("SELECT to_regnamespace('foundation')") is None
    assert await observer.fetchval("SELECT pg_try_advisory_lock(728322)")
    await observer.fetchval("SELECT pg_advisory_unlock(728322)")


@pytest.mark.asyncio
async def test_only_lock_owner_applies_pending_revision_after_history_read(
    migration_database, migration_probe
):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    async with AsyncExitStack() as cleanup:
        async with observer.transaction():
            await observer.execute(
                "LOCK TABLE public.alembic_version IN ACCESS EXCLUSIVE MODE"
            )
            owner = await cleanup.enter_async_context(
                migration_process("up", env=migration_probe)
            )
            async with asyncio.timeout(4):
                while not await observer.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM pg_locks l JOIN pg_stat_activity a USING (pid)
                        WHERE a.application_name = 'opengym-foundation-migrate'
                          AND l.locktype = 'advisory' AND l.objid = 728322 AND l.granted
                          AND EXISTS (SELECT FROM pg_locks w WHERE w.pid = l.pid AND NOT w.granted)
                    )
                """):
                    await asyncio.sleep(0.02)
            assert await migrate("up", env=migration_probe) == (
                1,
                {"code": "FOUNDATION_MIGRATION_LOCKED"},
            )
            assert (
                await observer.fetchval(
                    "SELECT version_num FROM public.alembic_version"
                )
                == "0001_infrastructure"
            )
            assert (
                await observer.fetchval(
                    "SELECT to_regnamespace('foundation_migration_probe')"
                )
                is None
            )
        output, diagnostic = await asyncio.wait_for(owner.communicate(), timeout=10)
        assert owner.returncode == 0
        assert diagnostic == b""
        assert json.loads(output) == {"code": "FOUNDATION_MIGRATION_UP_OK"}
    assert [
        row["version_num"]
        for row in await observer.fetch(
            "SELECT version_num FROM public.alembic_version"
        )
    ] == ["0002_probe"]
    assert (
        await observer.fetchval("""
            SELECT pg_get_userbyid(nspowner) FROM pg_namespace
            WHERE nspname = 'foundation_migration_probe'
        """)
        == "python_foundation_migrator"
    )
    assert await observer.fetchval("SELECT pg_try_advisory_lock(728322)")
    await observer.fetchval("SELECT pg_advisory_unlock(728322)")


@pytest.mark.asyncio
async def test_failed_revision_rolls_back_history_and_rerun_recovers(
    migration_database,
):
    observer = migration_database
    await observer.execute("CREATE SCHEMA foundation")
    assert await migrate("up") == (1, {"code": "FOUNDATION_MIGRATION_FAILED"})
    assert (
        await observer.fetchval("SELECT to_regclass('public.alembic_version')") is None
    )
    assert await observer.fetchval("SELECT pg_try_advisory_lock(728322)")
    await observer.fetchval("SELECT pg_advisory_unlock(728322)")
    await observer.execute("DROP SCHEMA foundation")
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "0001_infrastructure"
    )
