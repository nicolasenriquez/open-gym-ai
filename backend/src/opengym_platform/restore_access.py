"""Local operator's new-path recovery; restored data never authorizes old access."""

import asyncio
import json
import os
import re
import secrets
import stat
from pathlib import Path

import asyncpg

from opengym_platform.backup import read_private
from opengym_platform.bundle import (
    durable_json,
    record,
    regular,
    sync_directory,
    unique,
)
from opengym_platform.core.platform_settings import PLATFORM_LOCK_KEY, load_database
from opengym_platform.identity.passwords import make_hash
from opengym_platform.importer import TABLES, private_directory


def review_file(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("RECOVERY_REVIEW_PATH_INVALID")
    with regular(path) as stream:
        info = os.fstat(stream.fileno())
        if (
            info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 65536
        ):
            raise ValueError("RECOVERY_REVIEW_PRIVATE_REQUIRED")
        return json.load(stream, object_pairs_hook=unique)


def exclusive(path, value):
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


async def closed_target(connection, target):
    if (
        await connection.fetchval(
            "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"
        )
        != f"opengym-restore:{target}"
        or await connection.fetchval(
            "SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"
        )
        or await connection.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
        )
        or await connection.fetchval("SELECT version_num FROM public.alembic_version")
        != "p004_audit"
    ):
        raise ValueError("RECOVERY_TARGET_NOT_CLOSED")
    names = await connection.fetch(
        "SELECT format('%I.%I',schemaname,tablename) AS name FROM pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema')"
    )
    if {row["name"] for row in names} != {
        *TABLES,
        "administration.deletion_tasks",
        "public.alembic_version",
    }:
        raise ValueError("RECOVERY_SCHEMA_INVALID")


def validate_accounts(review, users, passwords, passkeys):
    accounts = review["accounts"]
    if not isinstance(accounts, list) or len(accounts) != len(users):
        raise ValueError("RECOVERY_COVERAGE_REQUIRED")
    by_id = {row["id"]: row for row in users}
    seen = set()
    for account in accounts:
        if not isinstance(account, dict) or set(account) != {
            "uid",
            "decision",
            "status",
            "identity_verified",
            "evidence",
            "password",
            "passkeys",
        }:
            raise ValueError("RECOVERY_ACCOUNT_INVALID")
        owner = account["uid"]
        if not isinstance(owner, str) or owner not in by_id or owner in seen:
            raise ValueError("RECOVERY_COVERAGE_REQUIRED")
        seen.add(owner)
        credentials = account["passkeys"]
        if (
            type(account["password"]) is not bool
            or account["password"] != (owner in passwords)
            or not isinstance(credentials, list)
            or any(not isinstance(key, str) for key in credentials)
            or len(set(credentials)) != len(credentials)
            or set(credentials)
            != {p["credential_id"] for p in passkeys if p["owner_id"] == owner}
            or account["decision"] not in {"recover", "block"}
            or account["status"] not in {"active", "unknown", "disabled", "deleted"}
            or type(account["identity_verified"]) is not bool
            or not isinstance(account["evidence"], list)
            or any(
                not isinstance(item, str) or not item.strip()
                for item in account["evidence"]
            )
        ):
            raise ValueError("RECOVERY_ACCOUNT_INVALID")
        if account["decision"] == "recover" and (
            account["status"] != "active"
            or not account["identity_verified"]
            or not account["evidence"]
            or by_id[owner]["disabled"]
        ):
            raise ValueError("RECOVERY_IDENTITY_REQUIRED")
    if not any(a["decision"] == "recover" for a in accounts):
        raise ValueError("RECOVERY_SELECTION_REQUIRED")


async def recover(config, target, review_path):
    connection = None
    try:
        settings = read_private(config)
        if set(settings) != {
            "instance_id",
            "target_root",
            "bundle_root",
            "identity_file",
        }:
            raise ValueError("RECOVERY_CONFIG_INVALID")
        if (
            not isinstance(target, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", target)
            or settings["instance_id"] != target
        ):
            raise ValueError("RECOVERY_TARGET_INVALID")
        root = Path(settings["target_root"])
        private_directory(root)
        destination = root / target
        private_directory(destination)
        restored = read_private(destination / "restore.json")
        gate = read_private(destination / "gate/admission.json")
        review = review_file(review_path)
        if (
            set(review)
            != {
                "target",
                "instance_id",
                "bundle",
                "snapshot_at",
                "session_secret",
                "coach_secret",
                "accounts",
            }
            or review["target"] != target
            or review["instance_id"] != target
            or restored["target"] != target
            or restored["code"] != "RESTORE_QUARANTINED"
            or restored["q1"] != "pending"
            or review["bundle"] != restored["bundle"]
            or review["snapshot_at"] != restored["snapshot_at"]
            or gate
            != {
                "instance_id": target,
                "operation": restored["bundle"],
                "allowed": False,
            }
        ):
            raise ValueError("RECOVERY_BINDING_INVALID")
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
            raise ValueError("RECOVERY_DATABASE_LOCKED")
        await closed_target(connection, target)
        users = await connection.fetch(
            "SELECT id,disabled FROM identity.users ORDER BY id"
        )
        passwords = {
            row["owner_id"]
            for row in await connection.fetch(
                "SELECT owner_id FROM identity.password_credentials"
            )
        }
        passkeys = await connection.fetch(
            "SELECT credential_id,owner_id FROM identity.passkeys"
        )
        validate_accounts(review, users, passwords, passkeys)
        manifest = read_private(destination / "manifest.json")
        selections = []
        for entry in manifest["files"]:
            if re.fullmatch(r"configuration/[0-9]+", entry["path"]):
                path = destination / entry["path"]
                if record(path, entry["path"]) != entry:
                    raise ValueError("RECOVERY_CONFIGURATION_CHANGED")
                try:
                    value = read_private(path)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(value, dict) and isinstance(value.get("api"), dict):
                    selections.append(value)
        if len(selections) != 1:
            raise ValueError("RECOVERY_CONFIGURATION_REQUIRED")
        environment = dict(
            item.split("=", 1) for item in selections[0]["api"]["config"]["Env"]
        )
        for field, variable in (
            ("session_secret", "PLATFORM_SESSION_SECRET_FILE"),
            ("coach_secret", "PLATFORM_COACH_SECRET_FILE"),
        ):
            if environment.get(variable) != "/run/secrets/" + review[field]:
                raise ValueError("RECOVERY_SECRET_SELECTION_INVALID")
        keys = {}
        for field in ("session_secret", "coach_secret"):
            name = review[field]
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                raise ValueError("RECOVERY_SECRET_INVALID")
            relative = "runtime-secrets/" + name
            path = destination / relative
            if record(path, relative) not in manifest["files"]:
                raise ValueError("RECOVERY_SECRET_CHANGED")
            with regular(path) as stream:
                value = stream.read(4097)
            if not 32 <= len(value) <= 4096:
                raise ValueError("RECOVERY_SECRET_INVALID")
            keys[field] = value
        selected = []
        for account in review["accounts"]:
            if account["decision"] == "recover":
                password = secrets.token_urlsafe(32)
                selected.append(
                    (
                        account["uid"],
                        "recovered-" + secrets.token_hex(16),
                        password,
                        await asyncio.to_thread(make_hash, password),
                    )
                )
        # Exclusive directory is also the fail-closed retry barrier after uncertain completion.
        output = destination / "access"
        output.mkdir(mode=0o700)
        sync_directory(destination)
        exclusive(
            output / "review.json", json.dumps(review, ensure_ascii=False).encode()
        )
        exclusive(output / "coach-secret", keys["coach_secret"])
        signing_key = secrets.token_hex(32).encode()
        if signing_key in keys.values():
            raise ValueError("RECOVERY_KEY_COLLISION")
        exclusive(output / "session-secret", signing_key)
        for index, (owner, alias, password, _) in enumerate(selected):
            exclusive(
                output / f"credential-{index}.json",
                json.dumps(
                    {"uid": owner, "identifier": alias, "password": password}
                ).encode(),
            )
        sync_directory(output)
        await closed_target(connection, target)
        async with connection.transaction():
            await connection.execute(
                "LOCK TABLE identity.users IN ACCESS EXCLUSIVE MODE"
            )
            await connection.execute("UPDATE identity.users SET disabled=true")
            for statement in (
                "DELETE FROM identity.device_links",
                "DELETE FROM identity.password_resets",
                "DELETE FROM identity.password_credentials",
                "DELETE FROM identity.passkeys",
            ):
                await connection.execute(statement)
            await connection.execute(
                "DELETE FROM identity.login_aliases WHERE NOT email_claim"
            )
            await connection.execute(
                "UPDATE identity.login_aliases SET password_name_claim=false,reset_name_until=NULL"
            )
            for owner, alias, _, hashed in selected:
                await connection.execute(
                    "INSERT INTO identity.password_credentials VALUES ($1,$2,clock_timestamp())",
                    owner,
                    hashed,
                )
                await connection.execute(
                    "INSERT INTO identity.login_aliases VALUES ($1,$2,false,true,NULL)",
                    alias,
                    owner,
                )
                await connection.execute(
                    "UPDATE identity.users SET disabled=false WHERE id=$1", owner
                )
            await connection.execute("SELECT coach.fail_interrupted_jobs()")
            await connection.execute("UPDATE coach.settings SET enabled=false")
        durable_json(
            output / "result.json",
            {
                "code": "RESTORE_ACCESS_REVIEWED",
                "access": "quarantined",
                "target": target,
            },
        )
        sync_directory(destination)
        return 0, {
            "code": "RESTORE_ACCESS_REVIEWED",
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
        TimeoutError,
        asyncpg.PostgresError,
    ):
        return 1, {"code": "RESTORE_ACCESS_BLOCKED"}
    finally:
        if connection is not None:
            try:
                await connection.close(timeout=5)
            except (OSError, asyncpg.PostgresError, TimeoutError):
                connection.terminate()
