"""One-worker Coach coordination; SQL owns admission, never provider I/O."""

import asyncio
import json
import os
import secrets
from datetime import UTC, datetime

from opengym_platform.coach.payload import cut
from opengym_platform.coach.service import execution_config, public_config
from opengym_platform.core.database import DatabaseError
from opengym_platform.core.platform_settings import environment_number
from opengym_platform.identity.sessions import authorize
from opengym_platform.training.service import coach_consent, coach_document

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
    def __init__(self, database, execute=None, *, pipeline=None):
        self.database = database
        self.execute = execute
        self.pipeline = pipeline
        self.slots = asyncio.Semaphore(2)
        self.tasks = set()
        self.timeout = environment_number("COACH_JOB_TIMEOUT_MS", 300000, 60000) / 1000
        self.closed = False

    async def _config(self, handle, session):
        if self.closed or self.pipeline is None:
            raise Refused("off")
        public = await public_config(handle)
        if not public or not public["enabled"] or public["authMode"] != "instance":
            raise Refused("off")
        if not await coach_consent(handle):
            raise Refused("consent")
        config = await execution_config(handle, session)
        if not config or not self.pipeline.available(config, session.owner):
            raise Refused("off")
        return config

    async def preflight(self, session):
        async with self.database.transaction() as handle:
            if not await authorize(handle, session):
                raise Refused("unauthorized")
            await self._config(handle, session)

    async def status(self, session):
        async with self.database.transaction() as handle:
            if not await authorize(handle, session):
                raise Refused("unauthorized")
            try:
                config = await self._config(handle, session)
            except Refused as error:
                if error.body.get("code") == "consent":
                    raise Refused("off") from None
                raise
            rows = await handle.fetch(
                "SELECT job_id,kind,state,started_at FROM coach.jobs"
            )
            current = (
                {
                    "id": rows[0]["job_id"],
                    "kind": rows[0]["kind"],
                    "state": rows[0]["state"],
                    "startedAt": int(rows[0]["started_at"].timestamp() * 1000),
                }
                if rows
                else None
            )
            pending = await handle.fetch("SELECT document FROM coach.pending_proposals")
            history = await handle.fetch(
                "SELECT job_id,kind,outcome,error_class,occurred_at,details FROM coach.history_events ORDER BY occurred_at DESC,event_id DESC LIMIT 1"
            )
            last = (
                {
                    "id": history[0]["job_id"],
                    "kind": history[0]["kind"],
                    "outcome": history[0]["outcome"],
                    "errorClass": history[0]["error_class"],
                    "at": int(history[0]["occurred_at"].timestamp() * 1000),
                    **json.loads(history[0]["details"]),
                }
                if history
                else None
            )
            used = await handle.fetch(
                "SELECT count FROM coach.daily_usage WHERE day=$1",
                datetime.now(UTC).date(),
            )
            return {
                "job": current,
                "pending": json.loads(pending[0]["document"]) if pending else None,
                "cap": {
                    "used": used[0]["count"] if used else 0,
                    "limit": config["per_profile_daily"],
                },
                "last": last,
                "maxMessageLen": config["max_message_len"],
            }

    async def enqueue(self, session, *, kind, trigger="manual", at=None, opts=None):
        if self.closed:
            raise Refused("off")
        if os.environ.get("COACH_DISABLED", "").lower() in {"1", "true", "yes", "on"}:
            raise Refused("off")
        at = at or datetime.now(UTC)
        job_id = secrets.token_hex(8)
        async with self.database.transaction() as handle:
            if not await authorize(handle, session):
                raise Refused("unauthorized")
            if self.pipeline is not None:
                config = await self._config(handle, session)
                opts = dict(opts or {})
                for key in ("note", "refine"):
                    opts[key] = cut(opts.get(key), config["max_message_len"])
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
        task = asyncio.create_task(self._run(session, job, generation, opts or {}))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def _run(self, session, job, generation, opts):
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
                        or (self.pipeline is None and config["provider"] != "fixture")
                        or config["authMode"] != "instance"
                    ):
                        await self._finish(handle, job, "failed", "off")
                        return
                    if self.pipeline is not None:
                        config = await execution_config(handle, session)
                        if not config or not self.pipeline.available(
                            config, session.owner
                        ):
                            await self._finish(handle, job, "failed", "off")
                            return
                        state = await coach_document(handle)
                        previous_rows = await handle.fetch(
                            "SELECT document FROM coach.pending_proposals"
                        )
                        previous = (
                            json.loads(previous_rows[0]["document"])
                            if previous_rows
                            else {}
                        )
                    await handle.execute(
                        "UPDATE coach.jobs SET state='running' WHERE job_id=$1",
                        job["id"],
                    )
                outcome, error, result = "nochange", None, {}
                try:
                    async with asyncio.timeout(self.timeout):
                        if self.pipeline is not None:
                            result = await self.pipeline.run(
                                session.owner,
                                job,
                                state,
                                config,
                                opts,
                                previous,
                                self.timeout,
                            )
                            outcome, error = result["outcome"], result.get("error")
                        else:
                            await self.execute(session.owner, job)
                except TimeoutError:
                    outcome, error = "failed", "timeout"
                except Exception:  # noqa: BLE001 -- provider text must never escape into history/logs.
                    outcome, error = "failed", "internal"
                async with self.database.transaction() as handle:
                    if await authorize(handle, session) and await self._current(
                        handle, job, generation
                    ):
                        await self._finish(handle, job, outcome, error, result)
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

    async def _finish(self, handle, job, outcome, error, result=None):
        result = result or {}
        if outcome == "ready":
            await handle.execute(
                """INSERT INTO coach.pending_proposals(owner_id,document)
                SELECT owner_id,$2::jsonb FROM coach.jobs WHERE job_id=$1
                ON CONFLICT(owner_id) DO UPDATE SET document=excluded.document""",
                job["id"],
                json.dumps(result["pending"]),
            )
        elif outcome == "nochange":
            await handle.execute("DELETE FROM coach.pending_proposals")
        await handle.execute(
            """INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at,error_class,details)
            SELECT owner_id,job_id,kind,$2,clock_timestamp(),$3,$4::jsonb FROM coach.jobs WHERE job_id=$1""",
            job["id"],
            outcome,
            error,
            json.dumps({"reading": result["reading"]} if result.get("reading") else {}),
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
