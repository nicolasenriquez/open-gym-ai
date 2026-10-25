"""Recovery CLI checkpoint with real restricted roles and SQL metadata."""

import asyncio
import hashlib
import json
import os
import secrets
import struct
import sys
from time import perf_counter

import asyncpg
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from test_migrations import migrate

pytest_plugins = ["test_isolation"]


@pytest.mark.asyncio
async def test_backup_creates_bundle_for_two_restricted_owners(
    isolation_database, recovery_target, migration_database, tmp_path, capsys
):
    started = perf_counter()
    database = isolation_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    expected = {"owner-a": 1, "owner-b": 2}
    for owner, identifier in expected.items():
        async with database.transaction(owner_id=owner) as handle:
            await handle.execute(
                "INSERT INTO isolation_fixture.owner_probe VALUES ($1, $2)",
                identifier,
                owner,
            )
    for owner, identifier in expected.items():
        async with database.transaction(owner_id=owner) as handle:
            assert (await handle.fetch("SELECT current_user AS login"))[0][
                "login"
            ] == "python_foundation_runtime"
            rows = await handle.fetch(
                "SELECT id, owner_id FROM isolation_fixture.owner_probe ORDER BY id"
            )
            assert [(row["id"], row["owner_id"]) for row in rows] == [
                (identifier, owner)
            ]
            assert [
                row["version_num"]
                for row in await handle.fetch(
                    "SELECT version_num FROM public.alembic_version"
                )
            ] == ["0002_health_readiness"]

    before = await recovery_metadata(migration_database)
    probe = next(row for row in before["tables"] if row["relname"] == "owner_probe")
    assert probe["owner"] == "python_foundation_migrator"
    assert probe["relrowsecurity"] and probe["relforcerowsecurity"]
    assert len(before["roles"]) == 3
    for role in before["roles"]:
        assert role["rolcanlogin"] is True
        assert not any(
            role[field]
            for field in (
                "rolsuper",
                "rolbypassrls",
                "rolcreatedb",
                "rolcreaterole",
                "rolreplication",
                "rolinherit",
                "membership",
            )
        )
    for grant in before["grants"]:
        assert grant["allowed"] == (
            grant["rolname"] == "python_foundation_runtime"
            and grant["privilege"] in ("SELECT", "INSERT", "UPDATE", "DELETE")
        )
        runtime = grant["rolname"] == "python_foundation_runtime"
        assert grant["schema_usage"] is runtime
        assert grant["schema_create"] is False
        assert grant["history_read"] is runtime
    assert before["public_grants"] == []
    for grant in before["database"]:
        assert grant["owner"] == "python_foundation_bootstrap"
        assert grant["connect"] is True
        assert grant["create"] == (grant["rolname"] == "python_foundation_migrator")
        assert grant["temp"] is False
    assert len(before["policies"]) == 1
    assert before["policies"][0]["roles"] == ["python_foundation_runtime"]
    assert before["policies"][0]["qual"] == before["policies"][0]["with_check"]

    tmp_path.chmod(0o700)
    key = tmp_path / "separate.key"
    key.write_bytes(os.urandom(32))
    key.chmod(0o600)
    bundle = tmp_path / "backup.bundle"
    assert not bundle.exists()
    phase = perf_counter()
    assert await recovery(
        "backup", str(bundle), str(key), "synthetic-revision-8-1"
    ) == (0, {"code": "FOUNDATION_RECOVERY_BACKUP_OK"})
    backup_seconds = perf_counter() - phase
    assert bundle.is_file(), "FOUNDATION_RECOVERY_BUNDLE_REQUIRED"
    data = bundle.read_bytes()
    size = struct.unpack("!I", data[:4])[0]
    metadata = data[4 : 4 + size]
    manifest = json.loads(metadata)
    assert manifest == {
        "format": 1,
        "revision": "synthetic-revision-8-1",
        "history": ["0002_health_readiness"],
        "database_version": "18.6",
        "tools": {"pg_dump": "18.6", "pg_restore": "18.6"},
        "roles": [
            "python_foundation_migrator",
            "python_foundation_runtime",
            "python_foundation_training",
        ],
        "source": "python_foundation_test",
        "scope": "synthetic-same-cluster-database-only",
        "cipher": "AES-256-GCM",
        "sha256": manifest["sha256"],
    }
    dump = AESGCM(key.read_bytes()).decrypt(
        data[4 + size : 16 + size], data[16 + size :], metadata
    )
    assert dump.startswith(b"PGDMP")
    assert hashlib.sha256(dump).hexdigest() == manifest["sha256"]
    transfer = tmp_path / "transfer"
    transfer.mkdir(mode=0o700)
    copied = transfer / "backup.bundle"
    phase = perf_counter()
    assert await recovery("copy", str(bundle), str(copied)) == (
        0,
        {"code": "FOUNDATION_RECOVERY_COPY_OK"},
    )
    copy_seconds = perf_counter() - phase
    assert copied.read_bytes() == bundle.read_bytes()
    assert list(transfer.iterdir()) == [copied]
    excludes_key = key.read_bytes() not in copied.read_bytes()
    assert excludes_key, "FOUNDATION_RECOVERY_TRANSFER_EXCLUDES_KEY"
    assert b"PGDMP" not in copied.read_bytes()
    phase = perf_counter()
    assert await recovery("restore", str(copied), str(key), recovery_target) == (
        0,
        {"code": "FOUNDATION_RECOVERY_RESTORE_OK"},
    )
    restore_seconds = perf_counter() - phase
    restored = await asyncpg.connect(
        host="foundation-db",
        database=recovery_target,
        user="python_foundation_runtime",
        password="synthetic-python-foundation-runtime-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        assert (
            await restored.fetchval("SELECT current_user")
            == "python_foundation_runtime"
        )
        after = await recovery_metadata(restored)
        assert after == before, "FOUNDATION_RECOVERY_METADATA_EQUIVALENCE_REQUIRED"
        for owner, identifier in expected.items():
            async with restored.transaction():
                await restored.execute(
                    "SELECT set_config('app.owner_id', $1, true)", owner
                )
                rows = await restored.fetch(
                    "SELECT id, owner_id FROM isolation_fixture.owner_probe ORDER BY id"
                )
                assert [(row["id"], row["owner_id"]) for row in rows] == [
                    (identifier, owner)
                ]
                assert (
                    await restored.fetchval(
                        "SELECT version_num FROM public.alembic_version"
                    )
                    == "0002_health_readiness"
                )
        assert (
            await restored.fetch("SELECT id FROM isolation_fixture.owner_probe") == []
        )
        # Roll every probe back, including an unexpected success, to preserve fixtures.
        for sql in (
            "INSERT INTO isolation_fixture.owner_probe VALUES (3, 'owner-b')",
            "TRUNCATE isolation_fixture.owner_probe",
            "CREATE TABLE isolation_fixture.forbidden (id integer)",
            "SET ROLE python_foundation_migrator",
        ):
            transaction = restored.transaction()
            await transaction.start()
            try:
                await restored.execute(
                    "SELECT set_config('app.owner_id', $1, true)", "owner-a"
                )
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await restored.execute(sql)
            finally:
                await transaction.rollback()
        async with restored.transaction():
            await restored.execute(
                "SELECT set_config('app.owner_id', $1, true)", "owner-a"
            )
            assert (
                await restored.execute(
                    "UPDATE isolation_fixture.owner_probe SET id = 4 WHERE id = 2"
                )
                == "UPDATE 0"
            )
            assert (
                await restored.execute(
                    "DELETE FROM isolation_fixture.owner_probe WHERE id = 2"
                )
                == "DELETE 0"
            )
    finally:
        await restored.close(timeout=5)
    training = await asyncpg.connect(
        host="foundation-db",
        database=recovery_target,
        user="python_foundation_training",
        password="synthetic-python-foundation-training-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        assert (
            await training.fetchval("SELECT current_user")
            == "python_foundation_training"
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await training.fetch("SELECT id FROM isolation_fixture.owner_probe")
    finally:
        await training.close(timeout=5)
    source_after = await recovery_metadata(migration_database)
    assert source_after == before, "FOUNDATION_RECOVERY_SOURCE_METADATA_UNCHANGED"
    for owner, identifier in expected.items():
        async with database.transaction(owner_id=owner) as handle:
            assert [
                row["id"]
                for row in await handle.fetch(
                    "SELECT id FROM isolation_fixture.owner_probe"
                )
            ] == [identifier]
    with capsys.disabled():
        print(
            json.dumps(
                {
                    "code": "FOUNDATION_RECOVERY_TIMING",
                    "backup_seconds": round(backup_seconds, 3),
                    "copy_seconds": round(copy_seconds, 3),
                    "restore_seconds": round(restore_seconds, 3),
                    "case_seconds": round(perf_counter() - started, 3),
                }
            )
        )


async def recovery_metadata(connection):
    # Stable catalog values only: no cross-database OIDs or privileged row reads.
    queries = {
        "history": "SELECT version_num FROM public.alembic_version ORDER BY version_num",
        "schemas": """
            SELECT nspname, pg_get_userbyid(nspowner) AS owner
            FROM pg_namespace WHERE nspname IN ('foundation', 'public', 'isolation_fixture')
            ORDER BY nspname
        """,
        "tables": """
            SELECT n.nspname, c.relname, pg_get_userbyid(c.relowner) AS owner,
                c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname IN ('public', 'isolation_fixture') AND c.relkind = 'r'
            ORDER BY n.nspname, c.relname
        """,
        "policies": """
            SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
            FROM pg_policies WHERE schemaname = 'isolation_fixture' ORDER BY policyname
        """,
        "public_grants": """
            SELECT 'schema' AS kind, nspname AS name, a.privilege_type
            FROM pg_namespace CROSS JOIN LATERAL aclexplode(nspacl) a
            WHERE nspname IN ('public', 'foundation', 'isolation_fixture') AND a.grantee = 0
            UNION ALL
            SELECT 'table', c.relname, a.privilege_type FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL aclexplode(c.relacl) a
            WHERE n.nspname IN ('public', 'isolation_fixture') AND a.grantee = 0
            UNION ALL
            SELECT 'database', 'current', a.privilege_type FROM pg_database d
            CROSS JOIN LATERAL aclexplode(d.datacl) a
            WHERE d.datname = current_database() AND a.grantee = 0
            ORDER BY 1, 2, 3
        """,
        "roles": """
            SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                rolcreaterole, rolreplication, rolinherit,
                EXISTS (SELECT FROM pg_auth_members WHERE member = r.oid) AS membership
            FROM pg_roles r WHERE rolname IN ('python_foundation_migrator',
                'python_foundation_runtime', 'python_foundation_training') ORDER BY rolname
        """,
        "grants": """
            SELECT r.rolname, privilege, has_table_privilege(r.oid,
                'isolation_fixture.owner_probe', privilege) AS allowed,
                has_schema_privilege(r.oid, 'isolation_fixture', 'USAGE') AS schema_usage,
                has_schema_privilege(r.oid, 'isolation_fixture', 'CREATE') AS schema_create,
                has_table_privilege(r.oid, 'public.alembic_version', 'SELECT') AS history_read
            FROM pg_roles r CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) privilege
            WHERE r.rolname IN ('python_foundation_runtime', 'python_foundation_training')
            ORDER BY r.rolname, privilege
        """,
        "database": """
            SELECT r.rolname, pg_get_userbyid(d.datdba) AS owner,
                has_database_privilege(r.oid, d.oid, 'CONNECT') AS connect,
                has_database_privilege(r.oid, d.oid, 'CREATE') AS create,
                has_database_privilege(r.oid, d.oid, 'TEMP') AS temp
            FROM pg_database d CROSS JOIN pg_roles r
            WHERE d.datname = current_database() AND r.rolname IN (
                'python_foundation_migrator', 'python_foundation_runtime', 'python_foundation_training')
            ORDER BY r.rolname
        """,
    }
    return {name: await connection.fetch(sql) for name, sql in queries.items()}


@pytest_asyncio.fixture
async def recovery_target(migration_database):
    observer = migration_database
    name = "python_foundation_restore_" + secrets.token_hex(8)
    await observer.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
    try:
        await observer.execute(
            f"COMMENT ON DATABASE \"{name}\" IS 'opengym-python-foundation-recovery-v1'"
        )
        yield name
    finally:
        await observer.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        remaining = await observer.fetchval(
            "SELECT EXISTS (SELECT FROM pg_database WHERE datname = $1)", name
        )
        assert remaining is False, "FOUNDATION_RECOVERY_TARGET_CLEANUP_REQUIRED"


@pytest_asyncio.fixture
async def recovery_bundle(migration_database, tmp_path):
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    tmp_path.chmod(0o700)
    key = tmp_path / "key"
    key.write_bytes(os.urandom(32))
    key.chmod(0o600)
    bundle = tmp_path / "backup"
    assert await recovery("backup", str(bundle), str(key), "synthetic-8-2") == (
        0,
        {"code": "FOUNDATION_RECOVERY_BACKUP_OK"},
    )
    return bundle, key


@pytest.mark.asyncio
async def test_wrong_key_and_tampered_content_leave_target_pristine(
    recovery_bundle, recovery_target, migration_database
):
    bundle, key = recovery_bundle
    original = bundle.read_bytes()
    await migration_database.execute("SELECT pg_stat_clear_snapshot()")
    sessions = await migration_database.fetchval(
        "SELECT coalesce(sum(sessions), 0) FROM pg_stat_database WHERE datname = $1",
        recovery_target,
    )
    wrong = key.with_name("wrong")
    wrong.write_bytes(os.urandom(32))
    wrong.chmod(0o600)
    rejected = (1, {"code": "FOUNDATION_RECOVERY_REJECTED"})
    assert (
        await recovery("restore", str(bundle), str(wrong), recovery_target) == rejected
    )
    for index in (original.index(b"synthetic-8-2") + 12, len(original) - 1):
        changed = bytearray(original)
        changed[index] ^= 1
        bundle.write_bytes(changed)
        assert (
            await recovery("restore", str(bundle), str(key), recovery_target)
            == rejected
        )
    bundle.write_bytes(original)
    await migration_database.execute("SELECT pg_stat_clear_snapshot()")
    after = await migration_database.fetchval(
        "SELECT coalesce(sum(sessions), 0) FROM pg_stat_database WHERE datname = $1",
        recovery_target,
    )
    assert after == sessions, "FOUNDATION_AUTH_MUST_NOT_CONNECT"
    assert (
        await migration_database.fetchval(
            "SELECT datacl IS NULL AND datallowconn AND shobj_description(oid, 'pg_database') = 'opengym-python-foundation-recovery-v1' FROM pg_database WHERE datname = $1",
            recovery_target,
        )
        is True
    )
    assert await recovery("restore", str(bundle), str(key), recovery_target) == (
        0,
        {"code": "FOUNDATION_RECOVERY_RESTORE_OK"},
    )


@pytest.mark.asyncio
async def test_paths_do_not_escape_follow_links_overwrite_or_transfer_key(
    recovery_bundle, tmp_path
):
    bundle, key = recovery_bundle
    original = bundle.read_bytes()
    rejected = (1, {"code": "FOUNDATION_RECOVERY_REJECTED"})
    assert await recovery("copy", str(bundle), str(bundle)) == rejected
    assert await recovery("backup", str(bundle), str(key), "another") == rejected
    assert bundle.read_bytes() == original
    assert await recovery("copy", str(key), str(tmp_path / "key-copy")) == rejected
    assert not (tmp_path / "key-copy").exists()
    destination = tmp_path / "destination"
    destination.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(destination, target_is_directory=True)
    assert await recovery("copy", str(bundle), str(link / "escape")) == rejected
    assert (
        await recovery("copy", str(bundle), str(destination) + "/../escape") == rejected
    )
    leaf = destination / "leaf"
    leaf.symlink_to(key)
    assert await recovery("copy", str(bundle), str(leaf)) == rejected
    assert (
        await recovery(
            "restore", str(leaf), str(key), "python_foundation_restore_0123456789abcdef"
        )
        == rejected
    )
    assert list(destination.iterdir()) == [leaf]
    bundle.chmod(0o644)
    assert await recovery("copy", str(bundle), str(destination / "public")) == rejected


@pytest.mark.asyncio
async def test_source_unmarked_foreign_and_nonempty_databases_are_rejected(
    recovery_bundle, recovery_target, migration_database
):
    bundle, key = recovery_bundle
    rejected = (1, {"code": "FOUNDATION_RECOVERY_REJECTED"})
    for name in ("python_foundation_test", "postgres", "not-a-db"):
        assert await recovery("restore", str(bundle), str(key), name) == rejected
    await migration_database.execute(f'COMMENT ON DATABASE "{recovery_target}" IS NULL')
    assert await recovery("restore", str(bundle), str(key), recovery_target) == rejected
    await migration_database.execute(
        f"COMMENT ON DATABASE \"{recovery_target}\" IS 'opengym-python-foundation-recovery-v1'"
    )
    await migration_database.execute(
        f'ALTER DATABASE "{recovery_target}" OWNER TO python_foundation_migrator'
    )
    assert await recovery("restore", str(bundle), str(key), recovery_target) == rejected
    await migration_database.execute(
        f'ALTER DATABASE "{recovery_target}" OWNER TO python_foundation_bootstrap'
    )
    connection = await asyncpg.connect(
        host="foundation-db",
        database=recovery_target,
        user="python_foundation_bootstrap",
        password="synthetic-python-foundation-only",
        ssl=False,
    )
    try:
        await connection.execute(
            "CREATE TABLE public.sentinel (id integer); INSERT INTO public.sentinel VALUES (42)"
        )
        assert (
            await recovery("restore", str(bundle), str(key), recovery_target)
            == rejected
        )
        assert await connection.fetchval("SELECT id FROM public.sentinel") == 42
    finally:
        await connection.close(timeout=5)


@pytest.mark.asyncio
async def test_failed_restore_is_atomic_and_target_is_disabled(
    recovery_bundle, recovery_target, migration_database
):
    bundle, key = recovery_bundle
    observer = migration_database
    await observer.execute("CREATE ROLE python_foundation_recovery_probe NOLOGIN")
    try:
        await observer.execute(
            "GRANT USAGE ON SCHEMA foundation TO python_foundation_recovery_probe"
        )
        broken = bundle.with_name("missing-role.bundle")
        assert await recovery("backup", str(broken), str(key), "synthetic-failure") == (
            0,
            {"code": "FOUNDATION_RECOVERY_BACKUP_OK"},
        )
        await observer.execute(
            "DROP OWNED BY python_foundation_recovery_probe; DROP ROLE python_foundation_recovery_probe"
        )
        assert await recovery("restore", str(broken), str(key), recovery_target) == (
            1,
            {"code": "FOUNDATION_RECOVERY_TARGET_UNUSABLE"},
        )
        assert (
            await observer.fetchval(
                "SELECT NOT datallowconn AND shobj_description(oid, 'pg_database') = 'opengym-python-foundation-unusable-v1' FROM pg_database WHERE datname = $1",
                recovery_target,
            )
            is True
        )
        # Fixture-only inspection does not make a failed destination reusable.
        await observer.execute(
            f'ALTER DATABASE "{recovery_target}" ALLOW_CONNECTIONS true'
        )
        inspection = await asyncpg.connect(
            host="foundation-db",
            database=recovery_target,
            user="python_foundation_bootstrap",
            password="synthetic-python-foundation-only",
            ssl=False,
        )
        try:
            assert (
                await inspection.fetchval(
                    "SELECT to_regclass('public.alembic_version')"
                )
                is None
            )
            assert (
                await inspection.fetchval("SELECT to_regnamespace('foundation')")
                is None
            )
        finally:
            await inspection.close(timeout=5)
        assert await recovery("restore", str(bundle), str(key), recovery_target) == (
            1,
            {"code": "FOUNDATION_RECOVERY_REJECTED"},
        )
        assert (
            await observer.fetchval("SELECT version_num FROM public.alembic_version")
            == "0002_health_readiness"
        )
    finally:
        if await observer.fetchval(
            "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = 'python_foundation_recovery_probe')"
        ):
            await observer.execute(
                "DROP OWNED BY python_foundation_recovery_probe; DROP ROLE python_foundation_recovery_probe"
            )


@pytest.mark.asyncio
async def test_oversized_artifacts_are_rejected_without_copying(tmp_path):
    source = tmp_path / "oversized"
    with source.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024 + 1)
    source.chmod(0o600)
    destination = tmp_path / "destination"
    assert await recovery("copy", str(source), str(destination)) == (
        1,
        {"code": "FOUNDATION_RECOVERY_REJECTED"},
    )
    assert not destination.exists()


@pytest.mark.asyncio
async def test_authenticated_history_mismatch_cannot_report_success(
    recovery_bundle, recovery_target
):
    bundle, key = recovery_bundle
    data = bundle.read_bytes()
    size = struct.unpack("!I", data[:4])[0]
    metadata = data[4 : 4 + size]
    cipher = AESGCM(key.read_bytes())
    dump = cipher.decrypt(data[4 + size : 16 + size], data[16 + size :], metadata)
    manifest = json.loads(metadata)
    manifest["history"] = ["not-the-dumped-revision"]
    metadata = json.dumps(manifest, sort_keys=True).encode()
    nonce = os.urandom(12)
    bundle.write_bytes(
        struct.pack("!I", len(metadata))
        + metadata
        + nonce
        + cipher.encrypt(nonce, dump, metadata)
    )
    assert await recovery("restore", str(bundle), str(key), recovery_target) == (
        1,
        {"code": "FOUNDATION_RECOVERY_TARGET_UNUSABLE"},
    )


async def recovery(*arguments):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.recovery",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, diagnostic = await asyncio.wait_for(process.communicate(), timeout=40)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    assert diagnostic == b"", "FOUNDATION_RECOVERY_UNSAFE_STDERR"
    try:
        result = json.loads(output)
    except ValueError, UnicodeError:
        pytest.fail("FOUNDATION_RECOVERY_INVALID_OUTPUT", pytrace=False)
    return process.returncode, result
