"""Node queue/nudge rules, using the user's local calendar, not server weekdays."""

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

COPY = json.loads(Path(__file__).with_name("copy.json").read_text())


def obj(value):
    return value if isinstance(value, dict) else {}


def records(value):
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def minute(value):
    match = re.fullmatch(r"(\d{2}):(\d{2})", value) if isinstance(value, str) else None
    return int(match[1]) * 60 + int(match[2]) if match else None


def local_now(reminder, now):
    try:
        return now.astimezone(ZoneInfo(reminder.get("tz") or "UTC"))
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None


def queue(state):
    q = obj(state.get("queue"))
    if not isinstance(q.get("ids"), list):
        return None
    ids = []
    for rid in q["ids"]:
        if rid not in ids and any(
            r.get("id") == rid for r in records(state.get("routines"))
        ):
            ids.append(rid)
    if not ids:
        return None
    starts = q.get("startsOn")
    if not isinstance(starts, str):
        applied = datetime.fromtimestamp((q.get("since") or 0) / 1000, UTC)
        starts = (
            (local_now(obj(state.get("reminder")), applied) or applied)
            .date()
            .isoformat()
        )
    return ids, starts


def queue_done(state, rid, starts):
    name = next(
        (r.get("name") for r in records(state.get("routines")) if r.get("id") == rid),
        None,
    )
    q = state["queue"]
    for w in records(state.get("workouts")):
        ids = (
            w.get("routineIds")
            if isinstance(w.get("routineIds"), list)
            else [w.get("routineId")]
        )
        if rid in ids and (
            (w.get("start") or 0) >= q.get("since", 0)
            or (
                q.get("strict") is not True
                and str(w.get("d") or "") >= starts
                and name in str(w.get("name") or "").split(" + ")
            )
        ):
            return True
    return False


def remaining(state, iso):
    q = queue(state)
    if not q or iso < q[1]:
        return []
    return [rid for rid in q[0] if not queue_done(state, rid, q[1])]


def effective_routine(state, iso):
    override = obj(state.get("dayPlan")).get(iso)
    if override == "rest":
        return None
    q = queue(state)
    pin = (
        ("done" if queue_done(state, override, q[1]) else "open")
        if q and override in q[0]
        else None
    )
    if pin == "open" or (
        not pin
        and override
        and any(r.get("id") == override for r in records(state.get("routines")))
    ):
        return override
    left = remaining(state, iso)
    pins = {
        d: rid
        for d, rid in obj(state.get("dayPlan")).items()
        if d >= iso and rid in left
    }
    chosen = pins.get(iso) or next(
        (rid for rid in left if rid not in pins.values()), None
    )
    if chosen:
        return chosen
    weekday = str((date.fromisoformat(iso).weekday() + 1) % 7)
    week = state.get("week")
    assigned = (
        week.get(weekday)
        if isinstance(week, dict)
        else week[int(weekday)]
        if isinstance(week, list) and len(week) > int(weekday)
        else None
    )
    for rid in assigned if isinstance(assigned, list) else [assigned]:
        if any(r.get("id") == rid for r in records(state.get("routines"))) and not (
            left and q and rid in q[0]
        ):
            return rid
    return None


def logged(state, iso):
    return any(w.get("d") == iso for w in records(state.get("workouts")))


def excused(state, iso):
    note = obj(obj(state.get("dayNotes")).get(iso))
    return note.get("tag") in ("sick", "travel", "rest", "injured") or (
        isinstance(note.get("text"), str) and bool(note["text"].strip())
    )


def missed(state, iso):
    if logged(state, iso) or excused(state, iso):
        return None
    if remaining(state, iso) and logged(
        state, (date.fromisoformat(iso) - timedelta(days=1)).isoformat()
    ):
        return None
    return effective_routine(state, iso)


def nudge_for(state, iso):
    rid = missed(state, iso)
    if not rid:
        return None
    last = max(
        (
            w["d"]
            for w in records(state.get("workouts"))
            if isinstance(w.get("d"), str) and w["d"] < iso
        ),
        default="",
    )
    misses = 0
    for back in range(1, 15):
        previous = (date.fromisoformat(iso) - timedelta(days=back)).isoformat()
        if previous <= last:
            break
        if missed(state, previous):
            misses += 1
            if misses >= 3:
                return None
    return rid


def planned(state, now, active=False):
    reminder = obj(state.get("reminder"))
    local = local_now(reminder, now)
    if not reminder.get("on") or local is None:
        return []
    iso, clock = local.date().isoformat(), local.hour * 60 + local.minute
    at = minute(reminder.get("time"))
    result = []
    if (
        reminder.get("nudge")
        and not active
        and max(1200, at + 120 if at is not None else 0) <= clock <= 1290
    ):
        rid = nudge_for(state, iso)
        if rid:
            result.append(("nudge", rid, local.date()))
    if (
        at is not None
        and 0 <= clock - at <= 15
        and not logged(state, iso)
        and not excused(state, iso)
    ):
        rid = effective_routine(state, iso)
        if rid:
            result.append(("reminder", rid, local.date()))
    return result


def message(state, kind, rid, day):
    routine = next(
        (r for r in records(state.get("routines")) if r.get("id") == rid), None
    )
    lang = state.get("lang")
    if kind == "reminder":
        copy = COPY["reminders"].get(lang, COPY["reminders"]["en"])
        if routine is None:
            return copy["fallback"].copy()
        return {
            **copy["named"],
            "title": copy["named"]["title"].format(
                emoji=routine.get("emoji") or "🏋️",
                name=routine.get("name", "undefined"),
            ),
        }
    copy = COPY["nudges"].get("de" if lang == "de-CH" else lang, COPY["nudges"]["en"])
    tone = obj(state.get("reminder")).get("tone")
    text = copy[tone if tone in COPY["nudges"]["en"] else "friendly"]
    index = (day - date(1970, 1, 1)).days % len(text["lines"])
    title, line = text["title"], text["lines"][index]
    if lang == "de-CH":
        title, line = title.replace("ß", "ss"), line.replace("ß", "ss")
    return {
        "title": title,
        "body": line.replace("{0}", str(obj(routine).get("name") or "openGym"), 1),
        "tag": "nudge",
    }
