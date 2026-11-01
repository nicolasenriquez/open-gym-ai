"""Ops-only restore into a separately provisioned, closed target."""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

import asyncpg

from opengym_platform.backup import read_private
from opengym_platform.bundle import (
    durable_json,
    record,
    regular,
    sync_directory,
    unique,
    verify,
)
from opengym_platform.core.platform_settings import PLATFORM_LOCK_KEY, load_database
from opengym_platform.importer import TABLES, private_directory, target_guard


def unpack(settings, bundle_id, target):
    root = Path(settings["target_root"])
    source = Path(settings["bundle_root"]) / f"{bundle_id}.age"
    identity = Path(settings["identity_file"])
    for path in (root, source, identity):
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise ValueError("RESTORE_PATH_INVALID")
    private_directory(root)
    if (
        root.is_relative_to(source.parent)
        or source.parent.is_relative_to(root)
        or identity.is_relative_to(root)
    ):
        raise ValueError("RESTORE_PATH_OVERLAP")
    with regular(identity):
        pass
    ciphertext = record(source, source.name)
    manifest = verify(source, identity, None)
    versions = json.loads(Path("/app/versions.json").read_text())
    if (
        type(manifest["version"]) is not int
        or manifest["version"] != 1
        or manifest["operation"] != bundle_id
        or not isinstance(manifest["instance_id"], str)
        or manifest["instance_id"] == target
        or manifest["schema"] != "p004_audit"
        or manifest["tools"]["postgres"].split(".")[0]
        != versions["postgres"].split(".")[0]
        or manifest["tools"]["age"] != versions["age"]["version"]
        or set(manifest["coverage"])
        != {"database", "data", "runtime-secrets", "configuration"}
    ):
        raise ValueError("RESTORE_MANIFEST_INVALID")
    entries = {item["path"]: item for item in manifest["files"]}
    for name in ("database.dump", "capture.json", "host-journal.json"):
        if not entries.get(name, {}).get("size"):
            raise ValueError("RESTORE_COVERAGE_INVALID")
    for name in ("data", "runtime-secrets", "configuration"):
        if entries.get(name) != {"path": name, "directory": True}:
            raise ValueError("RESTORE_COVERAGE_INVALID")
    if not any(name.startswith("runtime-secrets/") for name in entries) or not any(
        name.startswith("configuration/") for name in entries
    ):
        raise ValueError("RESTORE_COVERAGE_INVALID")
    if any(
        name.split("/")[0]
        not in {
            "database.dump",
            "capture.json",
            "host-journal.json",
            "data",
            "runtime-secrets",
            "configuration",
        }
        for name in entries
    ):
        raise ValueError("RESTORE_COVERAGE_INVALID")
    required = sum(item.get("size", 0) for item in entries.values()) + 32 * 1024 * 1024
    if shutil.disk_usage(root).free < required:
        raise ValueError("RESTORE_SPACE_REQUIRED")
    destination = root / target
    destination.mkdir(mode=0o700)
    gate = destination / "gate"
    gate.mkdir(mode=0o700)
    durable_json(
        gate / "admission.json",
        {"instance_id": target, "operation": bundle_id, "allowed": False},
    )
    durable_json(
        destination / "journal.json",
        {"phase": "extracting", "bundle": bundle_id, "access": "quarantined"},
    )
    verify(source, identity, manifest, destination)
    with regular(destination / "capture.json") as stream:
        if os.fstat(stream.fileno()).st_size > 32 * 1024 * 1024:
            raise ValueError("RESTORE_CAPTURE_INVALID")
        capture = json.load(stream, object_pairs_hook=unique)
    captured = {item["path"]: item for item in capture["files"]}
    expected = dict(captured)
    for name in captured:
        for parent in Path(name).parents:
            if parent != Path("."):
                expected.setdefault(
                    parent.as_posix(), {"path": parent.as_posix(), "directory": True}
                )
    if (
        capture["operation"] != bundle_id
        or capture["instance_id"] != manifest["instance_id"]
        or capture["schema"] != manifest["schema"]
        or capture["snapshot_at"] != manifest["snapshot_at"]
        or len(captured) != len(capture["files"])
        or entries
        != {
            **expected,
            "capture.json": entries["capture.json"],
            "host-journal.json": entries["host-journal.json"],
        }
    ):
        raise ValueError("RESTORE_CAPTURE_INVALID")
    if record(source, source.name) != ciphertext:
        raise ValueError("RESTORE_SOURCE_CHANGED")
    for name, item in entries.items():
        path = destination / name
        if item.get("directory"):
            if path.is_symlink() or not path.is_dir():
                raise ValueError("RESTORE_DESTINATION_CHANGED")
        elif record(path, name) != item:
            raise ValueError("RESTORE_DESTINATION_CHANGED")
    for path in sorted(
        (p for p in destination.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        sync_directory(path)
    durable_json(destination / "manifest.json", manifest)
    return destination, manifest, ciphertext


def load_dump(database, dump):
    with TemporaryDirectory() as private:
        password_file = Path(private) / "pgpass"
        escaped = database.password.replace("\\", "\\\\").replace(":", "\\:")
        password_file.write_text(
            f"db:5432:{database.database}:{database.user}:{escaped}\n"
        )
        password_file.chmod(0o600)
        subprocess.run(
            [
                "pg_restore",
                "--host=db",
                "--port=5432",
                f"--dbname={database.database}",
                f"--username={database.user}",
                "--no-password",
                "--data-only",
                "--no-owner",
                "--no-privileges",
                "--disable-triggers",
                "--single-transaction",
                "--exit-on-error",
                str(dump),
            ],
            env={"PATH": os.environ["PATH"], "PGPASSFILE": str(password_file)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=300,
        )


async def check_target(connection, target):
    await target_guard(connection, target, "restore")
    tables = await connection.fetch(
        "SELECT format('%I.%I',schemaname,tablename) AS name FROM pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1"
    )
    names = [row["name"] for row in tables]
    if set(names) != {
        *TABLES,
        "administration.deletion_tasks",
        "public.alembic_version",
    }:
        raise ValueError("RESTORE_TARGET_SCHEMA_INVALID")
    return names


async def restore(config, bundle_id, target):
    connection = None
    configured = False
    try:
        settings = read_private(config)
        if set(settings) != {
            "instance_id",
            "target_root",
            "bundle_root",
            "identity_file",
        }:
            raise ValueError("RESTORE_CONFIG_INVALID")
        if (
            not isinstance(target, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", target)
            or settings["instance_id"] != target
        ):
            raise ValueError("RESTORE_TARGET_INVALID")
        if not isinstance(bundle_id, str) or not re.fullmatch(
            r"[a-f0-9]{32}", bundle_id
        ):
            raise ValueError("RESTORE_BUNDLE_INVALID")
        root = Path(settings["target_root"])
        private_directory(root)
        if os.path.lexists(root / target):
            raise ValueError("RESTORE_TARGET_EXISTS")
        configured = True
        database = load_database("bootstrap")
        connection = await asyncpg.connect(
            host=database.host,
            database=database.database,
            user=database.user,
            password=database.password,
            ssl=False,
            timeout=5,
            command_timeout=10,
        )
        if not await connection.fetchval(
            "SELECT pg_try_advisory_lock($1)", PLATFORM_LOCK_KEY
        ):
            raise ValueError("RESTORE_DATABASE_LOCKED")
        await check_target(connection, target)
        destination, manifest, ciphertext = await asyncio.to_thread(
            unpack, settings, bundle_id, target
        )
        # Recheck after IO, with no transaction held across decryption or file transfer.
        tables = await check_target(connection, target)
        # Never cascade into foreign tables, even if DDL races the final check.
        await connection.execute("TRUNCATE " + ",".join(tables))
        durable_json(
            destination / "journal.json",
            {"phase": "loading", "bundle": bundle_id, "access": "quarantined"},
        )
        await asyncio.to_thread(load_dump, database, destination / "database.dump")
        if (
            await connection.fetchval("SELECT version_num FROM public.alembic_version")
            != manifest["schema"]
        ):
            raise ValueError("RESTORE_SCHEMA_INVALID")
        if await connection.fetchval(
            "SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"
        ):
            raise ValueError("RESTORE_TARGET_EXPOSED")
        source = Path(settings["bundle_root"]) / f"{bundle_id}.age"
        if await asyncio.to_thread(record, source, source.name) != ciphertext:
            raise ValueError("RESTORE_SOURCE_CHANGED")
        result = {
            "code": "RESTORE_QUARANTINED",
            "target": target,
            "bundle": bundle_id,
            "source_instance": manifest["instance_id"],
            "snapshot_at": manifest["snapshot_at"],
            "access": "quarantined",
            "q1": "pending",
            "cleanup_pending": True,
        }
        durable_json(destination / "restore.json", result)
        durable_json(
            destination / "journal.json",
            {
                "phase": "restored_quarantined",
                "bundle": bundle_id,
                "access": "quarantined",
            },
        )
        sync_directory(root)
        return 0, {
            "code": "RESTORE_QUARANTINED",
            "target": target,
            "access": "quarantined",
        }
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        subprocess.SubprocessError,
        tarfile.TarError,
        asyncpg.PostgresError,
    ):
        return (1 if configured else 2), {"code": "RESTORE_BLOCKED"}
    finally:
        if connection is not None:
            try:
                await connection.close(timeout=5)
            except (OSError, asyncpg.PostgresError, TimeoutError):
                connection.terminate()
