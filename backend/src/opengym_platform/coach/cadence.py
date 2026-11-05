"""One-worker consented cadence, with no session tokens or replay queue."""

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from opengym_platform.coach.jobs import Refused
from opengym_platform.coach.payload import items, numeric, obj
from opengym_platform.coach.service import public_config
from opengym_platform.core.database import DatabaseError


@dataclass(frozen=True)
class ScheduledOwner:
    owner: str
    generation: int
    version: None = None
    expires_at: None = None


def due(state, reviewed_at, now):
    coach = obj(state.get("coach"))
    cadence = obj(coach.get("cadence"))
    last = max(numeric(obj(coach.get("lastReview")).get("at")), reviewed_at)
    if last >= now.timestamp() * 1000:
        return False
    last_day = (
        datetime.fromtimestamp(last / 1000, UTC).date().isoformat() if last else ""
    )
    workouts = [
        w
        for w in items(state.get("workouts"))
        if isinstance(w, dict)
        and (
            not last
            or (
                numeric(w.get("end")) > last
                if w.get("end")
                else isinstance(w.get("d"), str) and w["d"] > last_day
            )
        )
    ]
    if not workouts:
        return False
    if cadence.get("everyWorkouts"):
        try:
            required = float(cadence["everyWorkouts"])
        except ValueError, TypeError, OverflowError:
            return False
        return not math.isnan(required) and len(workouts) >= max(1, min(20, required))
    weekly = obj(cadence.get("weekly"))
    if not weekly:
        return False
    try:
        zone = ZoneInfo(obj(state.get("reminder")).get("tz") or "UTC")
    except ZoneInfoNotFoundError, ValueError, TypeError:
        zone = UTC
    local = now.astimezone(zone)
    try:
        time = weekly.get("time") or "18:00"
        if not isinstance(time, str):
            return False
        hour, minute = map(int, time.split(":"))
        day = int(weekly.get("day") or 0)
        if not 0 <= day <= 6 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return False
        back = ((local.weekday() + 1) % 7 - day + 7) % 7
        slot = (local - timedelta(days=back)).replace(
            hour=hour, minute=minute, second=0, microsecond=0, fold=0
        )
        if slot.timestamp() > now.timestamp():
            slot -= timedelta(days=7)
        return last < slot.timestamp() * 1000
    except ValueError, TypeError, OverflowError:
        return False


async def tick(jobs, now=None):
    now = now or datetime.now(UTC)
    config = await public_config(jobs.database)
    if jobs.closed or not config or not config["enabled"]:
        return
    candidates = await jobs.database.fetch(
        "SELECT * FROM coach.scheduled_candidates($1)", now
    )
    for row in candidates:
        try:
            await jobs.enqueue_scheduled(row["owner_id"], now)
        except Refused:
            pass


async def maintain(jobs):
    while True:
        try:
            await tick(jobs)
        except DatabaseError:
            logging.getLogger(__name__).warning("PLATFORM_COACH_CADENCE_UNAVAILABLE")
        await asyncio.sleep(60)
