"""Ops-only SQL/files capture after the host has stopped application writers."""

import asyncio
import hashlib
import json
import os
import re
import stat
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import asyncpg

from opengym_platform.core.platform_settings import PLATFORM_LOCK_KEY, load_database

SCHEMAS = [
    "public",
    "identity",
    "training",
    "coach",
    "administration",
    "notifications",
    "audit",
]


def read_private(path, max_bytes=65536):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size > max_bytes
            or info.st_nlink != 1
        ):
            raise ValueError("BACKUP_PROOF_INVALID")
        return json.loads(os.read(descriptor, max_bytes + 1))
    finally:
        os.close(descriptor)


def capture_files(sources, destination, deadline, copy):
    """No-follow tree read/copy with byte and identity checks, including empty dirs."""
    records = []

    def visit(parent, name, relative):
        if (
            time.monotonic() > deadline
            or relative.count("/") > 64
            or len(records) >= 100_000
        ):
            raise ValueError("BACKUP_CAPTURE_LIMIT")
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        try:
            before = os.fstat(descriptor)
            if relative == "data" and not stat.S_ISDIR(before.st_mode):
                raise ValueError("BACKUP_DATA_DIRECTORY_REQUIRED")
            if relative.startswith(
                ("configuration/", "runtime-secrets/")
            ) and not stat.S_ISREG(before.st_mode):
                raise ValueError("BACKUP_FILE_TYPE_INVALID")

            def identity(info):
                return (
                    info.st_dev,
                    info.st_ino,
                    info.st_mode,
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ctime_ns,
                    info.st_nlink,
                )

            if stat.S_ISDIR(before.st_mode):
                if copy:
                    (destination / relative).mkdir(mode=0o700, parents=True)
                records.append(
                    {"path": relative, "directory": True, "identity": identity(before)}
                )
                for entry in sorted(os.listdir(descriptor)):
                    if "\\" in entry or any(ord(char) < 32 for char in entry):
                        raise ValueError("BACKUP_FILE_NAME_INVALID")
                    if relative == "data" and not (
                        entry in {"uploads", "vapid.json"}
                        or re.fullmatch(
                            r"coach-(?:auth-[A-Za-z0-9_-]{1,64}|key-[a-f0-9]{32})\.json",
                            entry,
                        )
                    ):
                        raise ValueError("BACKUP_DATA_ENTRY_UNKNOWN")
                    visit(descriptor, entry, f"{relative}/{entry}")
                if copy:
                    output = os.open(
                        destination / relative,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    )
                    try:
                        os.fsync(output)
                    finally:
                        os.close(output)
            elif stat.S_ISREG(before.st_mode) and before.st_nlink == 1:
                digest = hashlib.sha256()
                output = None
                try:
                    if copy:
                        target = destination / relative
                        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                        output = os.open(
                            target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                        )
                    while chunk := os.read(descriptor, 1024 * 1024):
                        if time.monotonic() > deadline:
                            raise ValueError("BACKUP_CAPTURE_DEADLINE")
                        digest.update(chunk)
                        if output is not None:
                            view = memoryview(chunk)
                            while view:
                                written = os.write(output, view)
                                if written <= 0:
                                    raise OSError("BACKUP_WRITE_FAILED")
                                view = view[written:]
                    if output is not None:
                        os.fsync(output)
                finally:
                    if output is not None:
                        os.close(output)
                records.append(
                    {
                        "path": relative,
                        "size": before.st_size,
                        "sha256": digest.hexdigest(),
                        "identity": identity(before),
                    }
                )
            else:
                raise ValueError("BACKUP_FILE_TYPE_INVALID")
            if identity(before) != identity(os.fstat(descriptor)):
                raise ValueError("BACKUP_FILE_CHANGED")
        finally:
            os.close(descriptor)

    for index, source in enumerate(sources):
        if (
            not isinstance(source, dict)
            or source.get("path") != f"/run/capture/{index}"
            or not isinstance(source.get("target"), str)
            or not re.fullmatch(
                r"data|runtime-secrets/[A-Za-z0-9_-]+|configuration/[0-9]+",
                source["target"],
            )
        ):
            raise ValueError("BACKUP_FILE_SOURCE_INVALID")
        visit(None, source["path"], source["target"])
        if source.get("sha256") and records[-1].get("sha256") != source["sha256"]:
            raise ValueError("BACKUP_FILE_CHANGED")
    if len({record["path"] for record in records}) != len(records):
        raise ValueError("BACKUP_DUPLICATE_FILE")
    return records


async def capture(config, check_only=False):
    connection = None
    deadline = time.monotonic() + 120
    try:
        settings = read_private(config)
        if not isinstance(settings, dict) or set(settings) != {
            "instance_id",
            "project",
            "staging_root",
            "expected_schema",
        }:
            raise ValueError("BACKUP_CONFIG_INVALID")
        root = Path(settings["staging_root"])
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ValueError("BACKUP_STAGING_INVALID")
        proof = read_private(root / "journal.json")
        if (
            not isinstance(proof, dict)
            or proof.get("version") != 1
            or proof.get("instance_id") != settings["instance_id"]
            or proof.get("project") != settings["project"]
            or proof.get("phase") != ("checking" if check_only else "capturing")
            or not (root / "exclusive").is_dir()
            or not re.fullmatch(r"[a-f0-9]{32}", proof.get("operation", ""))
            or not isinstance(proof.get("writers"), list)
            or not proof["writers"]
            or any(
                not isinstance(writer, dict)
                or not isinstance(writer.get("id"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", writer["id"])
                for writer in proof["writers"]
            )
        ):
            raise ValueError("BACKUP_WRITER_PROOF_REQUIRED")
        target = load_database("backup")
        connection = await asyncpg.connect(
            host=target.host,
            port=5432,
            database=target.database,
            user=target.user,
            password=target.password,
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        if not await connection.fetchval(
            "SELECT pg_try_advisory_lock($1)", PLATFORM_LOCK_KEY
        ):
            raise ValueError("BACKUP_DATABASE_LOCKED")
        role_safe = await connection.fetchval("""
            SELECT NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)
            FROM pg_roles WHERE rolname=current_user
        """)
        if not role_safe or not await connection.fetchval(
            "SELECT pg_has_role(current_user, 'pg_read_all_stats', 'USAGE')"
        ):
            raise ValueError("BACKUP_ROLE_UNSAFE")
        if await connection.fetchval("""
            SELECT EXISTS(SELECT FROM pg_auth_members
                WHERE roleid='opengym_backup'::regrole
                    OR (member='opengym_backup'::regrole AND roleid<>'pg_read_all_stats'::regrole))
        """):
            raise ValueError("BACKUP_ROLE_UNSAFE")
        other_clients = await connection.fetchval("""
            SELECT count(*) FROM pg_stat_activity
            WHERE datname=current_database() AND backend_type='client backend'
                AND pid<>pg_backend_pid()
        """)
        if other_clients:
            raise ValueError("BACKUP_EXTERNAL_WRITER")
        revisions = await connection.fetch(
            "SELECT version_num FROM public.alembic_version"
        )
        if [row["version_num"] for row in revisions] != [settings["expected_schema"]]:
            raise ValueError("BACKUP_SCHEMA_INCOMPATIBLE")
        from opengym_platform.application import SCHEMA_REVISION

        if settings["expected_schema"] != SCHEMA_REVISION:
            raise ValueError("BACKUP_SCHEMA_INCOMPATIBLE")
        if await connection.fetchval("SELECT pg_is_in_recovery()"):
            raise ValueError("BACKUP_DATABASE_NOT_PRIMARY")
        tables = await connection.fetch("""
            SELECT n.nspname, c.relname, c.relrowsecurity,
                has_table_privilege(c.oid,'SELECT') AS readable,
                has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') AS writable
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema')
                AND n.nspname NOT LIKE 'pg_toast%'
        """)
        for table in tables:
            if (
                table["nspname"] not in SCHEMAS
                or not table["readable"]
                or table["writable"]
            ):
                raise ValueError("BACKUP_TABLE_ACCESS_INVALID")
            if table["relrowsecurity"] and not await connection.fetchval(
                """
                SELECT EXISTS(SELECT FROM pg_policies WHERE schemaname=$1 AND tablename=$2
                    AND 'opengym_backup'=ANY(roles) AND cmd='SELECT' AND qual='true'
                    AND permissive='PERMISSIVE')
            """,
                table["nspname"],
                table["relname"],
            ):
                raise ValueError("BACKUP_RLS_INCOMPLETE")
        if await connection.fetchval("""
            SELECT EXISTS(SELECT FROM pg_policies WHERE permissive='RESTRICTIVE'
                AND cmd IN ('SELECT','ALL') AND roles && ARRAY['public','opengym_backup']::name[])
        """):
            raise ValueError("BACKUP_RLS_INCOMPLETE")
        if check_only:
            return 0, {"code": "BACKUP_SCHEMA_COMPATIBLE"}
        destination = root / proof["operation"]
        destination.mkdir(mode=0o700)
        sources = proof.get("capture_sources")
        if sources is not None and (
            not isinstance(sources, list)
            or not sources
            or not isinstance(sources[0], dict)
            or sources[0].get("target") != "data"
        ):
            raise ValueError("BACKUP_FILE_SOURCE_INVALID")
        before = (
            capture_files(sources, destination, deadline, False) if sources else None
        )
        async with connection.transaction(isolation="repeatable_read", readonly=True):
            snapshot = await connection.fetchval("SELECT pg_export_snapshot()")
            snapshot_at = datetime.now(UTC).isoformat()
            # libpq's password file keeps credentials out of argv, output and env.
            with TemporaryDirectory() as private:
                password_file = Path(private) / "pgpass"
                escaped = target.password.replace("\\", "\\\\").replace(":", "\\:")
                password_file.write_text(
                    f"db:5432:{target.database}:{target.user}:{escaped}\n"
                )
                password_file.chmod(0o600)
                process = await asyncio.create_subprocess_exec(
                    "pg_dump",
                    "--host=db",
                    "--port=5432",
                    f"--dbname={target.database}",
                    f"--username={target.user}",
                    "--no-password",
                    "--format=custom",
                    "--enable-row-security",
                    "--inserts",
                    f"--snapshot={snapshot}",
                    f"--file={destination / 'database.dump'}",
                    env={"PATH": os.environ["PATH"], "PGPASSFILE": str(password_file)},
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await asyncio.wait_for(
                        process.wait(), min(110, max(0, deadline - time.monotonic()))
                    )
                except BaseException:
                    process.kill()
                    await process.wait()
                    raise
                if process.returncode != 0:
                    raise ValueError("BACKUP_DUMP_FAILED")
        dump = destination / "database.dump"
        dump.chmod(0o600)
        with dump.open("rb") as stream:
            os.fsync(stream.fileno())
        if sources:
            copied = capture_files(sources, destination, deadline, True)
            after = capture_files(sources, destination, deadline, False)
            if before != copied or before != after:
                raise ValueError("BACKUP_FILE_CHANGED")
            files = [
                {key: value for key, value in record.items() if key != "identity"}
                for record in copied
            ]
            with dump.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files.append(
                {"path": "database.dump", "size": dump.stat().st_size, "sha256": digest}
            )
            manifest = {
                "version": 1,
                "instance_id": settings["instance_id"],
                "operation": proof["operation"],
                "snapshot_at": snapshot_at,
                "schema": settings["expected_schema"],
                "verified": False,
                "sources": sources,
                "files": files,
            }
            with (destination / "capture.json").open("x", encoding="utf-8") as stream:
                os.chmod(stream.fileno(), 0o600)
                json.dump(manifest, stream, ensure_ascii=True)
                stream.flush()
                os.fsync(stream.fileno())
            descriptor = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        if time.monotonic() > deadline:
            raise ValueError("BACKUP_CAPTURE_DEADLINE")
        return 0, {
            "code": "BACKUP_SET_CAPTURED" if sources else "BACKUP_SQL_CAPTURED",
            "capture_ms": round((time.monotonic() - deadline + 120) * 1000),
            "operation": proof["operation"],
            "snapshot_at": snapshot_at,
        }
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        asyncpg.PostgresError,
        TimeoutError,
    ):
        # No SQL values, paths, credentials or subprocess stderr in operator output.
        return 1, {"code": "BACKUP_CAPTURE_BLOCKED"}
    finally:
        if connection is not None:
            await connection.close(timeout=5)
