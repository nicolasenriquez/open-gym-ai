"""One-worker Coach coordination; SQL owns admission, never provider I/O."""

import asyncio
import os
import secrets
from datetime import UTC, datetime

from opengym_platform.coach.service import public_config
from opengym_platform.core.database import DatabaseError
from opengym_platform.core.platform_settings import environment_number
from opengym_platform.identity.sessions import authorize
from opengym_platform.training.service import coach_consent

ERRORS = {
    "off": (503, "the Coach is not set up on this instance"),
    "busy": (409, "the Coach is already thinking about your training"),
    "cap": (429, "the Coach is taking a rest day, try again tomorrow"),
    "consent": (403, "the Coach needs your go-ahead first"),
    "unauthorized": (401, "not signed in"),
}


class Refused(Exception):
    def __init__(self, code):
        self.status, error = ERRORS[code]
        self.body = {
            "error": error,
            **({"code": code} if code != "unauthorized" else {}),
        }


class Jobs:
    def __init__(self, database, execute):
        self.database = database
        self.execute = execute
        self.slots = asyncio.Semaphore(2)
        self.tasks = set()
        self.timeout = environment_number("COACH_JOB_TIMEOUT_MS", 300000, 60000) / 1000
        self.closed = False

    async def enqueue(self, session, *, kind, trigger="manual", at=None):
        if self.closed:
            raise Refused("off")
        if os.environ.get("COACH_DISABLED", "").lower() in {"1", "true", "yes", "on"}:
            raise Refused("off")
        at = at or datetime.now(UTC)
        job_id = secrets.token_hex(8)
        async with self.database.transaction() as handle:
            if not await authorize(handle, session):
                raise Refused("unauthorized")
            rows = await handle.fetch(
                "SELECT forget_generation FROM coach.profile_state"
            )
            generation = rows[0]["forget_generation"] if rows else 0
            result = (
                await handle.fetch(
                    "SELECT * FROM coach.reserve_job($1,$2,$3,$4,$5,$6,$7,$8)",
                    session.owner,
                    session.version,
                    session.expires_at,
                    job_id,
                    kind,
                    trigger,
                    generation,
                    at,
                )
            )[0]
            if result["state"] != "queued":
                raise Refused(result["state"])
        job = {
            "id": job_id,
            "kind": kind,
            "state": "queued",
            "startedAt": int(at.timestamp() * 1000),
        }
        task = asyncio.create_task(self._run(session, job, generation))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def _run(self, session, job, generation):
        try:
            async with self.slots:
                async with self.database.transaction() as handle:
                    if not await authorize(handle, session):
                        return
                    if not await self._current(handle, job, generation):
                        return
                    config = await public_config(handle)
                    if (
                        not config
                        or not config["enabled"]
                        or config["provider"] != "fixture"
                        or config["authMode"] != "instance"
                    ):
                        await self._finish(handle, job, "failed", "off")
                        return
                    await handle.execute(
                        "UPDATE coach.jobs SET state='running' WHERE job_id=$1",
                        job["id"],
                    )
                outcome, error = "nochange", None
                try:
                    async with asyncio.timeout(self.timeout):
                        await self.execute(session.owner, job)
                except TimeoutError:
                    outcome, error = "failed", "timeout"
                except Exception:  # noqa: BLE001 -- provider text must never escape into history/logs.
                    outcome, error = "failed", "internal"
                async with self.database.transaction() as handle:
                    if await authorize(handle, session) and await self._current(
                        handle, job, generation
                    ):
                        await self._finish(handle, job, outcome, error)
        except DatabaseError:
            # Unknown admission/completion is never retried: recovery labels it restart.
            return

    async def _current(self, handle, job, generation):
        rows = await handle.fetch(
            """SELECT j.job_id FROM coach.jobs j
            JOIN coach.profile_state p USING(owner_id)
            WHERE j.job_id=$1 AND j.forget_generation=$2 AND p.forget_generation=$2""",
            job["id"],
            generation,
        )
        if not rows:
            return False
        if not await coach_consent(handle):
            await handle.execute("DELETE FROM coach.jobs WHERE job_id=$1", job["id"])
            return False
        return True

    async def _finish(self, handle, job, outcome, error):
        await handle.execute(
            """INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at,error_class)
            SELECT owner_id,job_id,kind,$2,clock_timestamp(),$3 FROM coach.jobs WHERE job_id=$1""",
            job["id"],
            outcome,
            error,
        )
        await handle.execute("DELETE FROM coach.jobs WHERE job_id=$1", job["id"])
        await handle.execute("""DELETE FROM coach.history_events WHERE event_id IN (
            SELECT event_id FROM coach.history_events ORDER BY occurred_at DESC,event_id DESC OFFSET 20)""")

    async def close(self):
        self.closed = True
        pending = list(self.tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
