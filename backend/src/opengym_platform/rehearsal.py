"""Private, bounded rehearsal observer; never a public API or traffic admission."""

import asyncio
import hashlib
import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path

import asyncpg
import httpx

from opengym_platform.backup import read_private
from opengym_platform.bundle import durable_json, record, unique
from opengym_platform.coach.secrets import SecretFiles
from opengym_platform.core.platform_settings import PLATFORM_LOCK_KEY, load_database
from opengym_platform.identity.sessions import sign
from opengym_platform.importer import private_directory
from opengym_platform.restore_access import closed_target, review_file
from opengym_platform.training.stamps import encoded


async def http_checks(connection, destination, review):
    users = await connection.fetch(
        "SELECT id,is_admin,disabled,session_version FROM identity.users"
    )
    credentials = [
        json.loads(p.read_text())
        for p in sorted((destination / "access").glob("credential-*.json"))
    ]
    old = (
        (destination / "runtime-secrets" / review["session_secret"]).read_text().strip()
    )
    async with httpx.AsyncClient(
        base_url="http://rehearsal-api:3000/api/v1", timeout=3, trust_env=False
    ) as client:
        for attempt in range(150):
            try:
                if (await client.get("/health/ready")).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
        else:
            raise ValueError("REHEARSAL_HTTP_UNAVAILABLE")
        for credential in credentials:
            client.cookies.clear()
            response = await client.post(
                "/login/password",
                json={k: credential[k] for k in ("identifier", "password")},
            )
            user = next(row for row in users if row["id"] == credential["uid"])
            if (
                response.status_code != 200
                or response.json()["user"]["id"] != user["id"]
                or response.json()["user"]["admin"] != user["is_admin"]
            ):
                raise ValueError("REHEARSAL_LOGIN_FAILED")
            if (await client.get("/me")).json()["user"]["id"] != user["id"]:
                raise ValueError("REHEARSAL_ACTOR_FAILED")
            for path in (destination / "data/uploads" / user["id"]).glob("*"):
                if path.suffix in {
                    ".jpg",
                    ".png",
                    ".webp",
                    ".gif",
                    ".mp4",
                    ".mov",
                    ".webm",
                }:
                    media = await client.get("/media/" + path.stem)
                    if (
                        media.status_code != 200
                        or hashlib.sha256(media.content).hexdigest() != path.stem
                    ):
                        raise ValueError("REHEARSAL_MEDIA_HTTP_FAILED")
            own = (await client.get("/data")).json()
            forged = (
                await client.get(
                    "/data?owner=foreign", headers={"X-Owner-ID": "foreign"}
                )
            ).json()
            if own != forged:
                raise ValueError("REHEARSAL_OWNER_FORGERY")
            client.cookies.clear()
        for user in users:
            for version in {0, 1, user["session_version"]}:
                token = sign(
                    f"{user['id']}:{int(time.time() * 1000) + 3600000}:{version}", old
                )
                for headers in (
                    {"Cookie": "gymsid=" + token},
                    {"Authorization": "Bearer " + token},
                ):
                    if (await client.get("/me", headers=headers)).status_code != 401:
                        raise ValueError("REHEARSAL_OLD_SESSION_ACCEPTED")


async def watch(config, target):
    connection = None
    destination = None
    probe = None
    granted = False
    try:
        settings = read_private(config)
        if settings["instance_id"] != target:
            raise ValueError("REHEARSAL_TARGET_INVALID")
        destination = Path(settings["target_root"]) / target
        private_directory(destination)
        gate = json.loads((destination / "gate/admission.json").read_text())
        restored = json.loads((destination / "restore.json").read_text())
        review = review_file(destination / "access/review.json")
        if (
            gate["allowed"] is not False
            or restored["target"] != target
            or review["target"] != target
        ):
            raise ValueError("REHEARSAL_TARGET_EXPOSED")
        if (
            json.loads((destination / "access/result.json").read_text())["code"]
            != "RESTORE_ACCESS_REVIEWED"
        ):
            raise ValueError("REHEARSAL_ACCESS_UNREVIEWED")
        db = load_database("bootstrap")
        connection = await asyncpg.connect(
            host=db.host,
            database=db.database,
            user=db.user,
            password=db.password,
            ssl=False,
            timeout=5,
            command_timeout=10,
        )
        if not await connection.fetchval(
            "SELECT pg_try_advisory_lock($1)", PLATFORM_LOCK_KEY
        ):
            raise ValueError("REHEARSAL_DATABASE_LOCKED")
        await closed_target(connection, target)
        if await connection.fetchval(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','training','coach','administration','notifications') AND c.relkind='r' AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity OR pg_get_userbyid(c.relowner)<>'opengym_schema_owner')"
        ):
            raise ValueError("REHEARSAL_CATALOG_INVALID")
        manifest = json.loads((destination / "manifest.json").read_text())
        for item in manifest["files"]:
            if (
                item["path"].startswith("data/")
                and not item.get("directory")
                and record(destination / item["path"], item["path"]) != item
            ):
                raise ValueError("REHEARSAL_MEDIA_CHANGED")
        for table in (
            "identity.passkeys",
            "identity.device_links",
            "identity.password_resets",
            "coach.jobs",
        ):
            if await connection.fetchval("SELECT count(*) FROM " + table):
                raise ValueError("REHEARSAL_HISTORICAL_ACCESS_ACTIVE")
        os.environ["DATA_DIR"] = str(destination / "data")
        os.environ["PLATFORM_COACH_SECRET_FILE"] = str(
            destination / "access/coach-secret"
        )
        files = SecretFiles()
        for path in (destination / "data").glob("coach-auth-*.json"):
            if files.decrypt(files.read(path.name)) is None:
                raise ValueError("REHEARSAL_COACH_UNREADABLE")
        probe = destination / "rehearsal"
        probe.mkdir(mode=0o700)
        stop = probe / "stop"
        asyncio.get_running_loop().add_signal_handler(
            signal.SIGTERM, lambda: stop.touch(mode=0o600, exist_ok=True)
        )
        keys = probe / "keys"
        keys.mkdir(mode=0o700)
        for source, name in (
            (destination / "access/session-secret", "session-secret"),
            (destination / "access/coach-secret", "coach-secret"),
            (Path("/run/secrets/runtime"), "runtime"),
        ):
            shutil.copyfile(source, keys / name)
            (keys / name).chmod(0o600)
        (keys / "gate").mkdir(mode=0o700)
        durable_json(
            keys / "gate/admission.json",
            {"instance_id": target, "operation": restored["bundle"], "allowed": True},
        )
        client = probe / "client"
        client.mkdir(mode=0o700)
        shutil.copyfile(
            destination / "access/credential-0.json", client / "credential.json"
        )
        (client / "credential.json").chmod(0o600)
        durable_json(
            client / "binding.json",
            {
                "operation": os.environ["PLATFORM_REHEARSAL_OPERATION"],
                "target": target,
                "bundle": restored["bundle"],
            },
        )
        # This independent guardian revokes CONNECT even if the host controller dies.
        granted = True
        await connection.execute(
            "GRANT CONNECT ON DATABASE "
            + '"'
            + db.database.replace('"', '""')
            + '"'
            + " TO opengym_api_runtime"
        )
        runtime = await asyncpg.connect(
            host=db.host,
            database=db.database,
            user="opengym_api_runtime",
            password=(keys / "runtime").read_text().strip(),
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        try:
            role = await runtime.fetchrow(
                "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user"
            )
            rls = await runtime.fetchrow(
                "SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner)=current_user AS owned FROM pg_class WHERE oid='training.documents'::regclass"
            )
            if (
                any(role.values())
                or not rls["relrowsecurity"]
                or not rls["relforcerowsecurity"]
                or rls["owned"]
            ):
                raise ValueError("REHEARSAL_RUNTIME_PRIVILEGED")
            if await runtime.fetchval("SELECT count(*) FROM training.documents"):
                raise ValueError("REHEARSAL_RLS_LEAK")
            for account in review["accounts"]:
                if account["decision"] == "recover":
                    async with runtime.transaction():
                        await runtime.execute(
                            "SELECT set_config('app.owner_id',$1,true)", account["uid"]
                        )
                        if await runtime.fetchval(
                            "SELECT count(*) FROM training.documents WHERE owner_id<>$1",
                            account["uid"],
                        ):
                            raise ValueError("REHEARSAL_RLS_LEAK")
        finally:
            await runtime.close()
        durable_json(probe / "ready.json", {"ready": True})
        await http_checks(connection, destination, review)
        checks = {
            "http": True,
            "rls": True,
            "media": True,
            "coach_decrypt": True,
            "sessions_links_jobs": True,
        }
        durable_json(probe / "checks.json", checks)
        deadline = time.monotonic() + 600
        while not (probe / "stop").exists() and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
        return 0 if (probe / "stop").exists() else 1
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        StopIteration,
        httpx.HTTPError,
        asyncpg.PostgresError,
    ):
        return 1
    finally:
        if connection is not None:
            try:
                if granted:
                    await connection.execute(
                        "REVOKE CONNECT ON DATABASE "
                        + '"'
                        + db.database.replace('"', '""')
                        + '"'
                        + " FROM opengym_api_runtime"
                    )
                    await connection.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND usename='opengym_api_runtime'"
                    )
                    for _ in range(50):
                        if not await connection.fetchval(
                            "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
                        ):
                            break
                        await asyncio.sleep(0.1)
                if probe is not None:
                    durable_json(
                        probe / "keys/gate/admission.json",
                        {
                            "instance_id": target,
                            "allowed": False,
                            "operation": restored["bundle"],
                        },
                    )
                    await closed_target(connection, target)
                    durable_json(probe / "closed.json", {"closed": True})
            finally:
                await connection.close()


async def confirm(config, target, digest):
    raw = Path("/run/client-evidence.json").read_bytes()
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != digest:
        return 1
    evidence = json.loads(raw, object_pairs_hook=unique)
    settings = read_private(config)
    if settings["instance_id"] != target:
        return 1
    root = Path(settings["target_root"]) / target
    binding = json.loads((root / "rehearsal/client/binding.json").read_text())
    review = review_file(root / "access/review.json")
    observed = evidence["observation"]
    if any(evidence.get(key) != value for key, value in binding.items()) or observed[
        "uid"
    ] not in {a["uid"] for a in review["accounts"] if a["decision"] == "recover"}:
        return 1
    db = load_database("bootstrap")
    connection = await asyncpg.connect(
        host=db.host,
        database=db.database,
        user=db.user,
        password=db.password,
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        row = await connection.fetchrow(
            "SELECT document,revision,write_id FROM training.documents WHERE owner_id=$1",
            observed["uid"],
        )
        if (
            not row
            or row["revision"] != observed["rev"]
            or row["write_id"] != observed["wid"]
        ):
            return 1
        document = json.loads(row["document"])
        document.pop("_prior", None)
        document.pop("_unstamped", None)
        if hashlib.sha256(encoded(document).encode()).hexdigest() != observed["sha256"]:
            return 1
        print(json.dumps({"persisted": True}))
        return 0
    finally:
        await connection.close()


def main():
    command, config, target = sys.argv[1:4]
    if command == "confirm":
        return asyncio.run(confirm(config, target, sys.argv[4]))
    if command == "watch":

        async def bounded():
            try:
                async with asyncio.timeout(600):
                    return await watch(config, target)
            except TimeoutError:
                return 1

        return asyncio.run(bounded())
    settings = read_private(config)
    if settings["instance_id"] != target:
        return 1
    root = Path(settings["target_root"]) / target / "rehearsal"
    if command == "stop":
        (root / "stop").touch(mode=0o600, exist_ok=False)
        return 0
    if command == "status":
        result = {}
        for name in ("ready", "checks", "closed"):
            if (root / f"{name}.json").exists():
                result[name] = json.loads(
                    (root / f"{name}.json").read_text(), object_pairs_hook=unique
                )
        print(json.dumps(result))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
