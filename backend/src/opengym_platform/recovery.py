"""Bounded recovery CLI, exclusively for the private synthetic cluster."""

import asyncio
import hashlib
import json
import os
import re
import resource
import stat
import struct
import subprocess
import sys
from contextlib import contextmanager
from tempfile import TemporaryFile

import asyncpg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from opengym_platform.migrate import _validate_target

# shortcut: fixture dumps stay in memory; stream before raising the 32 MiB cap.
LIMIT = 32 * 1024 * 1024
ROLES = [
    "python_foundation_migrator",
    "python_foundation_runtime",
    "python_foundation_training",
]
SOURCE = "python_foundation_test"
MARKER = "opengym-python-foundation-recovery-v1"


@contextmanager
def parent(path):
    parts = path.split("/")
    if (
        parts[:2] != ["", "tmp"]
        or len(parts) < 4
        or any(p in ("", ".", "..") for p in parts[2:])
    ):
        raise ValueError()
    with open("/proc/mounts") as mounts:
        # Require the isolated tmpfs; this is a mount check, not a temporary filename.
        if not any(line.split()[1:3] == ["/tmp", "tmpfs"] for line in mounts):  # nosec B108
            raise ValueError()
    # Traverse via directory descriptors without following links; never create a file here.
    descriptor = os.open("/tmp", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)  # nosec B108
    try:
        for part in parts[2:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError()
        yield descriptor, parts[-1]
    finally:
        os.close(descriptor)


def read_private(path):
    with parent(path) as (directory, name):
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
                or info.st_size > LIMIT
            ):
                raise ValueError()
            data = stream.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise ValueError()
            return data


def write_private(path, data):
    if len(data) > LIMIT:
        raise ValueError()
    with parent(path) as (directory, name):
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
        except BaseException:
            os.unlink(name, dir_fd=directory)
            raise


def tool(name, arguments, database=SOURCE, data=None):
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "HOME": "/nonexistent",
        "PGHOST": "foundation-db",
        "PGPORT": "5432",
        "PGDATABASE": database,
        "PGUSER": "python_foundation_bootstrap",
        "PGPASSWORD": "synthetic-python-foundation-only",
        "PGSSLMODE": "disable",
        "PGCONNECT_TIMEOUT": "5",
        "PGOPTIONS": "-c statement_timeout=15000 -c lock_timeout=2000",
    }

    def cap_output():
        resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))

    with TemporaryFile() as output, TemporaryFile() as diagnostic:
        result = subprocess.run(
            [
                "/opt/pg-tools/ld.so",
                "--library-path",
                "/opt/pg-tools/lib",
                f"/opt/pg-tools/{name}",
                *arguments,
            ],
            input=data,
            stdout=output,
            stderr=diagnostic,
            env=env,
            timeout=30,
            check=False,
            preexec_fn=cap_output,
        )
        if result.returncode or diagnostic.tell() or output.tell() > LIMIT:
            raise ValueError()
        output.seek(0)
        return output.read(LIMIT + 1)


async def connect(database=SOURCE):
    return await asyncpg.connect(
        host="foundation-db",
        port=5432,
        database=database,
        user="python_foundation_bootstrap",
        password="synthetic-python-foundation-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
        server_settings={"statement_timeout": "5000", "lock_timeout": "2000"},
    )


async def roles_valid(connection):
    roles = await connection.fetchval(
        """
        SELECT array_agg(rolname::text ORDER BY rolname) FROM pg_roles
        WHERE rolname = ANY($1::text[]) AND rolcanlogin
            AND NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit)
    """,
        ROLES,
    )
    memberships = await connection.fetchval(
        """
        SELECT count(*) FROM pg_auth_members WHERE member IN
            (SELECT oid FROM pg_roles WHERE rolname = ANY($1::text[]))
    """,
        ROLES,
    )
    if roles != ROLES or memberships:
        raise ValueError()


def versions():
    for name in ("pg_dump", "pg_restore"):
        if not re.match(
            rf"^{name} \(PostgreSQL\) 18\.6(?:\s|$)", tool(name, ["--version"]).decode()
        ):
            raise ValueError()
    return {"pg_dump": "18.6", "pg_restore": "18.6"}


async def backup(path, key_path, revision):
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", revision)
        or path == key_path
    ):
        raise ValueError()
    key = read_private(key_path)
    if len(key) != 32:
        raise ValueError()
    tools = versions()
    connection = await connect()
    try:
        await roles_valid(connection)
        async with connection.transaction(isolation="repeatable_read", readonly=True):
            version = await connection.fetchval("SHOW server_version")
            if version.split()[0] != "18.6":
                raise ValueError()
            snapshot = await connection.fetchval("SELECT pg_export_snapshot()")
            history = [
                row[0]
                for row in await connection.fetch(
                    "SELECT version_num FROM public.alembic_version ORDER BY version_num"
                )
            ]
            dump = tool(
                "pg_dump",
                ["--format=custom", "--no-password", f"--snapshot={snapshot}"],
            )
            manifest = json.dumps(
                {
                    "format": 1,
                    "revision": revision,
                    "history": history,
                    "database_version": "18.6",
                    "tools": tools,
                    "roles": ROLES,
                    "source": SOURCE,
                    "scope": "synthetic-same-cluster-database-only",
                    "cipher": "AES-256-GCM",
                    "sha256": hashlib.sha256(dump).hexdigest(),
                },
                sort_keys=True,
            ).encode()
    finally:
        await connection.close(timeout=5)
    nonce = os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, dump, manifest)
    write_private(path, struct.pack("!I", len(manifest)) + manifest + nonce + encrypted)


def envelope(data):
    size = struct.unpack("!I", data[:4])[0]
    if not 1 <= size <= 8192 or len(data) < 4 + size + 28:
        raise ValueError()
    metadata = data[4 : 4 + size]
    manifest = json.loads(metadata)
    if (
        manifest.get("format") != 1
        or manifest.get("source") != SOURCE
        or manifest.get("database_version") != "18.6"
        or manifest.get("roles") != ROLES
        or manifest.get("tools") != {"pg_dump": "18.6", "pg_restore": "18.6"}
        or manifest.get("scope") != "synthetic-same-cluster-database-only"
        or manifest.get("cipher") != "AES-256-GCM"
        or not isinstance(manifest.get("history"), list)
        or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", manifest.get("revision", "")
        )
        or not re.fullmatch(r"[a-f0-9]{64}", manifest.get("sha256", ""))
    ):
        raise ValueError()
    return manifest, metadata, data[4 + size : 4 + size + 12], data[4 + size + 12 :]


class RestoreUnusable(Exception):
    """A verified destination was touched; it must be discarded."""


async def restore(path, key_path, target):
    if not re.fullmatch(r"python_foundation_restore_[a-f0-9]{16}", target):
        raise ValueError()
    manifest, metadata, nonce, encrypted = envelope(read_private(path))
    key = read_private(key_path)
    if len(key) != 32:
        raise ValueError()
    dump = AESGCM(key).decrypt(nonce, encrypted, metadata)
    if hashlib.sha256(dump).hexdigest() != manifest["sha256"] or not dump.startswith(
        b"PGDMP"
    ):
        raise ValueError()
    versions()
    tool("pg_restore", ["--list"], data=dump)
    # All bundle authentication precedes even the source metadata connection.
    admin = await connect()
    connection = None
    started = False
    try:
        valid = await admin.fetchval(
            """
            SELECT pg_get_userbyid(datdba) = 'python_foundation_bootstrap'
                AND datacl IS NULL AND datallowconn AND NOT datistemplate
                AND shobj_description(oid, 'pg_database') = $2
            FROM pg_database WHERE datname = $1
        """,
            target,
            MARKER,
        )
        if valid is not True:
            raise ValueError()
        await roles_valid(admin)
        connection = await connect(target)
        if not await connection.fetchval("SELECT pg_try_advisory_lock(728322)"):
            raise ValueError()
        schemas = await connection.fetchval("""
            SELECT count(*) FROM pg_namespace
            WHERE nspname !~ '^pg_' AND nspname NOT IN ('information_schema', 'public')
        """)
        objects = await connection.fetchval("""
            SELECT count(*) FROM (
                SELECT relnamespace AS ns FROM pg_class UNION ALL
                SELECT pronamespace FROM pg_proc UNION ALL SELECT typnamespace FROM pg_type
            ) objects JOIN pg_namespace n ON n.oid = objects.ns
            WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
        """)
        if schemas or objects:
            raise ValueError()
        started = True
        tool(
            "pg_restore",
            [
                "--no-password",
                "--single-transaction",
                "--exit-on-error",
                "--dbname",
                target,
            ],
            target,
            dump,
        )
        async with connection.transaction():
            history = [
                row[0]
                for row in await connection.fetch(
                    "SELECT version_num FROM public.alembic_version ORDER BY version_num"
                )
            ]
            if history != manifest["history"]:
                raise ValueError()
            await connection.execute(f'REVOKE ALL ON DATABASE "{target}" FROM PUBLIC')
            await connection.execute(
                f'GRANT CONNECT, CREATE ON DATABASE "{target}" TO python_foundation_migrator'
            )
            await connection.execute(
                f'GRANT CONNECT ON DATABASE "{target}" TO python_foundation_runtime, python_foundation_training'
            )
            await connection.execute(
                f"COMMENT ON DATABASE \"{target}\" IS 'opengym-python-foundation-restored-v1'"
            )
    except Exception:
        if started:
            # Deny new connections as well as reporting unusable; never retry this target.
            try:
                await admin.execute(
                    f'ALTER DATABASE "{target}" ALLOW_CONNECTIONS false'
                )
                await admin.execute(
                    f"COMMENT ON DATABASE \"{target}\" IS 'opengym-python-foundation-unusable-v1'"
                )
            finally:
                raise RestoreUnusable() from None
        raise
    finally:
        if connection is not None:
            await connection.close(timeout=5)
        await admin.close(timeout=5)


def main() -> int:
    try:
        _validate_target()
        if len(sys.argv) == 5 and sys.argv[1] == "backup":
            asyncio.run(backup(*sys.argv[2:]))
        elif len(sys.argv) == 5 and sys.argv[1] == "restore":
            asyncio.run(restore(*sys.argv[2:]))
        elif len(sys.argv) == 4 and sys.argv[1] == "copy":
            data = read_private(sys.argv[2])
            envelope(data)
            write_private(sys.argv[3], data)
        else:
            raise ValueError()
    except RestoreUnusable:
        print(json.dumps({"code": "FOUNDATION_RECOVERY_TARGET_UNUSABLE"}))
        return 1
    except Exception:  # noqa: BLE001
        print(json.dumps({"code": "FOUNDATION_RECOVERY_REJECTED"}))
        return 1
    print(json.dumps({"code": f"FOUNDATION_RECOVERY_{sys.argv[1].upper()}_OK"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
