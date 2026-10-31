"""Coarse consented medians; raw participants never leave this module."""

import math
from datetime import UTC, datetime, timedelta

from opengym_platform.coach.jobs import Refused
from opengym_platform.coach.payload import BY_ID, items, numeric, obj
from opengym_platform.coach.service import public_config
from opengym_platform.training.service import coach_document


async def share(jobs, session, value):
    async with jobs.database.transaction() as handle:
        if not await jobs._authorize(handle, session):
            raise Refused("unauthorized")
        await jobs._config(handle, session)
        sharing = value not in (None, False, 0, "")
        await handle.execute(
            "INSERT INTO coach.profile_state(owner_id,sharing) VALUES($1,$2) ON CONFLICT(owner_id) DO UPDATE SET sharing=excluded.sharing",
            session.owner,
            sharing,
        )
    return {"ok": True, "sharing": sharing}


def round1(value):
    scaled = value * 10
    return math.floor(scaled + 0.5) / 10 if math.isfinite(scaled) else None


def median(values):
    values = sorted(value for value in values if math.isfinite(value))
    return values[len(values) // 2] if values else None


def participant(document, now):
    since = (now - timedelta(weeks=12)).date().isoformat()
    frequency = (now - timedelta(weeks=8)).date().isoformat()
    workouts = [
        w
        for w in items(document.get("workouts"))
        if isinstance(w, dict) and isinstance(w.get("d"), str) and w["d"] >= since
    ]
    if not workouts:
        return None
    best = {}
    for workout in workouts:
        for entry in items(workout.get("entries")):
            entry = obj(entry)
            identifier = entry.get("id")
            if not isinstance(identifier, str) or identifier not in BY_ID:
                continue
            for row in items(entry.get("sets")):
                row = obj(row)
                phase = row.get("phase", "")
                warm = (
                    phase.strip().lower() in {"warmup", "warm-up", "warm_up"}
                    if isinstance(phase, str) and phase.strip()
                    else row.get("warmup") is True
                )
                weight, reps = numeric(row.get("w")), numeric(row.get("r"))
                if not row.get("done") or warm or weight <= 0 or reps <= 0:
                    continue
                estimate = (
                    weight
                    * (0.45359237 if document.get("unit") == "lb" else 1)
                    * (1 + min(reps, 12) / 30)
                )
                if math.isfinite(estimate):
                    best[identifier] = max(best.get(identifier, 0), estimate)
    return {
        "sessionsPerWeek": round1(sum(w["d"] >= frequency for w in workouts) / 8),
        "best": best,
    }


def aggregate(rows, owner, unit, *, payload=False):
    people = len(rows)
    if people < 3:
        return {
            "ok": False,
            "enabled": True,
            "sharing": True,
            "people": people,
            "minPeople": 3,
        }
    me = rows.get(owner)
    by_ex = {}
    for row in rows.values():
        for identifier, value in row["best"].items():
            by_ex.setdefault(identifier, []).append(value)
    exercises = [
        {
            "id": identifier,
            "name": BY_ID[identifier]["n"],
            "people": len(values),
            "medianKg": median(values),
            "youKg": me["best"].get(identifier) if me else None,
            "values": values,
        }
        for identifier, values in by_ex.items()
        if len(values) >= 3
    ]
    if payload:
        exercises.sort(key=lambda row: (row["youKg"] is None, row["name"]))
        return {
            "unit": "kg",
            "people": people,
            "sessionsPerWeek": {
                "median": median([p["sessionsPerWeek"] for p in rows.values()]),
                "you": me["sessionsPerWeek"] if me else 0,
            },
            "exercises": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "median": round1(row["medianKg"]),
                    "you": round1(row["youKg"]) if row["youKg"] is not None else None,
                }
                for row in exercises[:12]
            ],
        }
    exercises.sort(key=lambda row: (-row["people"], row["name"]))
    exercises = exercises[:12]
    ranks = [
        (sum(v <= row["youKg"] for v in row["values"]) - 1) / (len(row["values"]) - 1)
        for row in exercises
        if row["youKg"] is not None
    ]

    def out(value):
        return (
            round1(value / (0.45359237 if unit == "lb" else 1))
            if value is not None
            else None
        )

    return {
        "ok": True,
        "enabled": True,
        "sharing": True,
        "people": people,
        "minPeople": 3,
        "unit": unit,
        "sessionsPerWeek": {
            "median": median([p["sessionsPerWeek"] for p in rows.values()]),
            "you": me["sessionsPerWeek"] if me else 0,
        },
        "exercises": [
            {
                "id": row["id"],
                "name": row["name"],
                "people": row["people"],
                "median": out(row["medianKg"]),
                "you": out(row["youKg"]),
            }
            for row in exercises
        ],
        "rankPct": math.floor(sum(ranks) / len(ranks) * 100 + 0.5) if ranks else None,
    }


async def compute(jobs, session, *, now=None, payload=False):
    now = now or datetime.now(UTC)
    async with jobs.database.transaction() as handle:
        if not await jobs._authorize(handle, session):
            raise Refused("unauthorized")
        await jobs._config(handle, session)
        config = await public_config(handle)
        if not config["community"]:
            return {"ok": False, "enabled": False}
        sharing = await handle.fetch("SELECT sharing FROM coach.profile_state")
        if not sharing or not sharing[0]["sharing"]:
            return {"ok": False, "enabled": True, "sharing": False}
        document = await coach_document(handle)
        candidates = await handle.fetch(
            "SELECT * FROM coach.cohort_candidates($1,$2,$3)",
            session.owner,
            session.version,
            session.expires_at,
        )
    rows = {}
    for candidate in candidates:
        async with jobs.database.transaction() as handle:
            allowed = await handle.fetch(
                "SELECT * FROM coach.lock_cohort_owner($1,$2,$3,$4)",
                session.owner,
                session.version,
                session.expires_at,
                candidate["owner_id"],
            )
            if allowed:
                value = participant(await coach_document(handle) or {}, now)
                if value:
                    rows[candidate["owner_id"]] = value
    async with jobs.database.transaction() as handle:
        if not await jobs._authorize(handle, session):
            raise Refused("unauthorized")
        await jobs._config(handle, session)
        if not (await public_config(handle))["community"]:
            return {"ok": False, "enabled": False}
        sharing = await handle.fetch("SELECT sharing FROM coach.profile_state")
        if not sharing or not sharing[0]["sharing"]:
            return {"ok": False, "enabled": True, "sharing": False}
    return aggregate(
        rows,
        session.owner,
        "lb" if document.get("unit") == "lb" else "kg",
        payload=payload,
    )
