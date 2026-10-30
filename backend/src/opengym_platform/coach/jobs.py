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
        self.by_id = {}
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
            pending = await self._pending(handle, session.owner)
            history = await handle.fetch(
                "SELECT job_id,kind,outcome,error_class,occurred_at,details FROM coach.history_events ORDER BY occurred_at DESC,event_id DESC LIMIT 1"
            )
            details = json.loads(history[0]["details"]) if history else {}
            last = (
                {
                    "id": history[0]["job_id"],
                    "kind": history[0]["kind"],
                    "outcome": history[0]["outcome"],
                    "errorClass": history[0]["error_class"],
                    "at": int(history[0]["occurred_at"].timestamp() * 1000),
                    **(
                        {"reading": details["reading"]}
                        if details.get("reading")
                        else {}
                    ),
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
                "pending": pending,
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
        self.by_id[job_id] = task
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(lambda done: self.by_id.pop(job_id, None))
        return job

    async def resolve(self, session, body):
        async with self.database.transaction() as handle:
            if not await authorize(handle, session):
                raise Refused("unauthorized")
            await self._config(handle, session)
            pending = await self._pending(handle, session.owner)
            if pending:
                await self._archive(
                    handle,
                    session.owner,
                    pending,
                    "dismissed"
                    if body.get("dismissed") not in (None, False, 0, "")
                    else "applied",
                    {
                        key: len(body[key]) if isinstance(body.get(key), list) else 0
                        for key in ("accepted", "rejected")
                    },
                )
        return {"ok": True}

    async def forget(self, session):
        async with self.database.transaction() as handle:
            if not await authorize(handle, session):
                raise Refused("unauthorized")
            job_id = await self.forget_content(handle, session.owner)
        self.cancel(job_id)
        return {"ok": True}

    def cancel(self, job_id):
        if task := self.by_id.get(job_id):
            task.cancel()

    async def training_changed(self, handle, owner, current, document):
        """Forget atomically with a committed opt-out or full Training reset."""
        if not await coach_consent(handle) or (
            document.get("resetAt", 0) != (current or {}).get("resetAt", 0)
        ):
            return await self.forget_content(handle, owner)
        return None

    async def forget_content(self, handle, owner):
        """Participate in the initiating owner's transaction; never commit here."""
        jobs = await handle.fetch("SELECT job_id FROM coach.jobs")
        await handle.execute(
            """INSERT INTO coach.profile_state(owner_id,sharing,forget_generation)
            VALUES($1,false,1) ON CONFLICT(owner_id) DO UPDATE
            SET sharing=false,forget_generation=coach.profile_state.forget_generation+1""",
            owner,
        )
        for table in ("jobs", "pending_proposals", "history_events"):
            await handle.execute(f"DELETE FROM coach.{table}")
        await handle.execute(
            "DELETE FROM coach.daily_usage WHERE day<>$1", datetime.now(UTC).date()
        )
        return jobs[0]["job_id"] if jobs else None

    async def _pending(self, handle, owner):
        rows = await handle.fetch("SELECT document FROM coach.pending_proposals")
        if not rows:
            return None
        pending = json.loads(rows[0]["document"])
        if pending["expiresAt"] < datetime.now(UTC).timestamp() * 1000:
            await self._archive(handle, owner, pending, "expired")
            return None
        return pending

    async def _archive(self, handle, owner, pending, outcome, details=None):
        await handle.execute(
            """INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at,details)
            VALUES($1,$2,$3,$4,clock_timestamp(),$5::jsonb)""",
            owner,
            pending["id"],
            pending["kind"],
            outcome,
            json.dumps(details or {}),
        )
        await handle.execute("DELETE FROM coach.pending_proposals")
        await self._trim(handle)

    async def _trim(self, handle):
        await handle.execute("""DELETE FROM coach.history_events WHERE event_id IN (
            SELECT event_id FROM coach.history_events ORDER BY occurred_at DESC,event_id DESC OFFSET 20)""")

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
        await self._trim(handle)

    async def close(self):
        self.closed = True
        pending = list(self.tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
