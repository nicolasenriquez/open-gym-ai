"""One-worker external deletion and private, credential-file-authorized operator CLI."""

import argparse
import asyncio
import json
import logging
import re
from uuid import UUID

from opengym_platform.coach.secrets import SecretFiles
from opengym_platform.core.database import Database, DatabaseError
from opengym_platform.media.service import remove_deleted_owner


class Cleanup:
    def __init__(self, database, secrets):
        self.database, self.secrets = database, secrets

    async def run_one(self, task=None):
        # Commit the attempt before touching files; crash/cancel consumes its durable budget.
        rows = await self.database.fetch(
            "SELECT * FROM administration.claim_cleanup($1)", task
        )
        if not rows:
            return False
        task, attempt = rows[0]["id"], rows[0]["attempt"]
        async with self.database.transaction() as handle:
            rows = await handle.fetch(
                "SELECT * FROM administration.lock_cleanup($1,$2)", task, attempt
            )
            if not rows:
                return False
            work = rows[0]
            error = work["error_code"]
            owner = work["deleted_owner_id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", owner):
                error = "media"
            if error is None:
                error = "secret"
                try:
                    # Local no-follow unlinks only, no crypto/network/thread can outlive these locks.
                    self.secrets.remove_owner(owner, work["secret_refs"])
                    error = "media"
                    remove_deleted_owner(self.secrets.directory, owner)
                    error = None
                except (OSError, ValueError):
                    pass
                except Exception:  # noqa: BLE001 -- preserve task and safe code for unexpected filesystem failures
                    error = "internal"
            await handle.fetch(
                "SELECT administration.finish_cleanup($1,$2,$3)", task, attempt, error
            )
        if error:
            logging.getLogger(__name__).warning("PLATFORM_CLEANUP_PENDING %s", error)
        return True

    async def maintain(self):
        from opengym_platform.application import SCHEMA_REVISION

        while True:
            try:
                rows = await self.database.fetch(
                    "SELECT version_num FROM public.alembic_version LIMIT 2"
                )
                if [row["version_num"] for row in rows] == [SCHEMA_REVISION]:
                    await self.run_one()
            except DatabaseError:
                logging.getLogger(__name__).warning("PLATFORM_CLEANUP_DATABASE_FAILED")
            await asyncio.sleep(1)


async def operate(action, task):
    from opengym_platform.application import SCHEMA_REVISION

    database = await Database.open_platform()
    try:
        revisions = await database.fetch(
            "SELECT version_num FROM public.alembic_version LIMIT 2"
        )
        if [row["version_num"] for row in revisions] != [SCHEMA_REVISION]:
            raise ValueError("PLATFORM_CLEANUP_SCHEMA_INVALID")
        if action == "run":
            await Cleanup(database, SecretFiles()).run_one(task)
        elif action == "retry":
            await database.fetch("SELECT administration.retry_cleanup($1)", task)
        rows = await database.fetch(
            "SELECT administration.cleanup_status($1) AS status", task
        )
        value = json.loads(rows[0]["status"]) if rows[0]["status"] else None
        print(json.dumps(value, separators=(",", ":")))
        return (
            0
            if (action == "status" or value)
            and (action != "run" or value[0]["status"] == "done")
            else 1
        )
    finally:
        await database.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "run", "retry"))
    parser.add_argument("task", type=UUID, nargs="?")
    args = parser.parse_args()
    if args.action != "status" and args.task is None:
        parser.error("run/retry requires an exact task UUID")
    try:
        return asyncio.run(operate(args.action, args.task))
    except (DatabaseError, OSError, ValueError):
        print('{"code":"PLATFORM_CLEANUP_FAILED"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
