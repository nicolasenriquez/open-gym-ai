"""Bounded allowlist of the Training categories disclosed to the Coach."""

import hashlib
import hmac
import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

ASSETS = json.loads(Path(__file__).with_name("assets.json").read_text(encoding="utf-8"))
LIBRARY = ASSETS["library"]
BY_ID = {e["id"]: e for e in LIBRARY}
POLICIES = ("off", "linear", "greyskull", "double", "time")


def obj(value):
    return value if isinstance(value, dict) else {}


def items(value):
    return value if isinstance(value, list) else []


def records(value):
    return [v for v in items(value) if isinstance(v, dict)]


def string(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return "[object Object]"
    if isinstance(value, list):
        return ",".join(string(v) for v in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def cut(value, size):
    return string(value)[:size]


def text(value, size):
    return value[:size] if isinstance(value, str) else ""


def number(value):
    if type(value) in (int, float):
        try:
            return value if math.isfinite(value) else None
        except OverflowError:
            return None
    if isinstance(value, str) and re.fullmatch(r"-?\d{1,9}(\.\d{1,6})?", value):
        return value
    return None


def numeric(value):
    try:
        result = float(value) if type(value) in (str, int, float) else 0
        return result if math.isfinite(result) else 0
    except (ValueError, OverflowError):
        return 0


def rounded(value):
    return math.floor(numeric(value) + 0.5)


def ident(value):
    return text(value, 64) if isinstance(value, str) else number(value)


def day(value):
    return (
        value[:10]
        if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value)
        else None
    )


def lang(value):
    return (
        value.strip()
        if isinstance(value, str)
        and re.fullmatch(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?", value.strip())
        else None
    )


def glyph(value):
    if value in ASSETS["glyphs"]:
        return value
    if isinstance(value, str) and len(value.encode("utf-16-le")) <= 32:
        if re.fullmatch("[\U0001f1e6-\U0001f1ff]{2}", value):
            return value
        if value and all(
            any(low <= ord(c) <= high for low, high in ASSETS["pictographs"])
            or 0x1F3FB <= ord(c) <= 0x1F3FF
            or c in "\u200d\ufe0f"
            for c in value
        ):
            return value
    return "figureStrength"


def mode(exercise, catalogue=None):
    value = obj(exercise).get("mode")
    return (
        value
        if value in ("reps", "time", "cardio")
        else "cardio"
        if obj(catalogue).get("bp") == "cardio"
        else "reps"
    )


def warmup(row):
    phase = text(row.get("phase"), 50).strip().lower()
    return (
        phase in ("warmup", "warm-up", "warm_up")
        if phase
        else row.get("warmup") is True
    )


def bodyweight(exercise, catalogue):
    return (
        bool(exercise["bodyweight"])
        if exercise.get("bodyweight") is not None
        else obj(catalogue).get("eq") == "body weight"
    )


def profile(value):
    value = obj(value)
    result = {
        k: text(value.get(k), n)
        for k, n in {
            "limitations": 600,
            "likes": 300,
            "dislikes": 300,
            "notes": 600,
        }.items()
    }
    result.update({k: text(value.get(k), 40) or None for k in ("goal", "experience")})
    for key, high in (("daysPerWeek", 7), ("sessionMin", 1440)):
        n = numeric(value.get(key))
        result[key] = min(high, max(1, rounded(n))) if n else None
    result["equipment"] = [
        e[:40] for e in items(value.get("equipment")) if isinstance(e, str) and e
    ][:40]
    result["preferredDays"] = list(
        dict.fromkeys(
            int(d)
            for d in items(value.get("preferredDays"))
            if type(d) in (int, float, str) and re.fullmatch("[0-6]", string(d))
        )
    )
    return result


def clean_ex(exercise):
    eid = ident(exercise.get("id"))
    kind = mode(exercise, BY_ID.get(eid))
    result = {
        "id": eid,
        "name": obj(BY_ID.get(eid)).get("n"),
        "sets": number(exercise.get("sets")),
        "mode": kind,
    }
    fields = (
        ["min", "speed"]
        if kind == "cardio"
        else ["sec"]
        if kind == "time"
        else ["reps"]
    )
    fields += ["repsMin", "repsMax", "setsMax"]
    if kind != "cardio" and exercise.get("weight"):
        fields.append("weight")
    if numeric(exercise.get("inc")) > 0:
        fields.append("inc")
    result.update(
        {k: exercise[k] for k in fields if number(exercise.get(k)) is not None}
    )
    if exercise.get("prog") in POLICIES:
        result["prog"] = exercise["prog"]
    if exercise.get("bodyweight") is not None:
        result["bodyweight"] = bool(exercise["bodyweight"])
    if exercise.get("side"):
        result["side"] = True
    if exercise.get("sg"):
        result["sg"] = ident(exercise["sg"])
    return result


def clean_plan(state):
    routines = []
    for routine in records(state.get("routines")):
        row = {
            "id": ident(routine.get("id")),
            "name": cut(routine.get("name"), 80)
            if routine.get("name") is not None
            else None,
            "emoji": glyph(routine["emoji"])
            if routine.get("emoji") is not None
            else None,
            "ex": [clean_ex(e) for e in records(routine.get("ex"))],
        }
        for key in ("name", "emoji"):
            if key not in routine:
                row.pop(key)
        if routine.get("prog") in POLICIES:
            row["prog"] = routine["prog"]
        routines.append(row)
    return {
        "routines": routines,
        "week": {
            str(d): [ident(v) for v in (v if isinstance(v, list) else [v])]
            for d in (1, 2, 3, 4, 5, 6, 0)
            if (v := obj(state.get("week")).get(str(d)))
        },
    }


def canonical_plan(state):
    custom = {
        c.get("id"): c
        for c in records(state.get("customEx"))
        if isinstance(c.get("id"), str)
    }
    routines = []
    for routine in records(state.get("routines")):
        exercises = []
        for e in records(routine.get("ex")):
            eid = e.get("id")
            catalogue = BY_ID.get(eid) or custom.get(eid)
            kind = mode(e, catalogue)
            row = {
                "id": eid,
                "mode": kind,
                "sets": e.get("sets") or 0,
                "reps": (e.get("reps") or 0) if kind == "reps" else 0,
                "sec": (e.get("sec") or 0) if kind == "time" else 0,
                "min": (e.get("min") or 0) if kind == "cardio" else 0,
                "speed": (e.get("speed") or 0) if kind == "cardio" else 0,
                "weight": 0 if kind == "cardio" else (e.get("weight") or 0),
                "prog": e.get("prog") or "",
                "inc": e.get("inc") or 0,
                "repsMin": e.get("repsMin") or 0,
                "repsMax": e.get("repsMax") or 0,
                "bodyweight": bodyweight(e, catalogue),
                "side": bool(e.get("side")),
                "sg": e.get("sg") or "",
            }
            exercises.append(row)
        routines.append(
            {
                "id": routine.get("id"),
                "name": routine.get("name") or "",
                "prog": routine.get("prog") or "",
                "ex": exercises,
            }
        )
    week = {
        str(d): value if isinstance(value, list) else [value]
        for d in (1, 2, 3, 4, 5, 6, 0)
        if isinstance(value := obj(state.get("week")).get(str(d)), (str, list))
        and len(value)
    }
    return {"routines": routines, "week": week}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def plan_hash(state):
    plan = canonical_plan(state)
    fields = (
        "id",
        "mode",
        "sets",
        "reps",
        "sec",
        "min",
        "speed",
        "weight",
        "prog",
        "inc",
        "repsMin",
        "repsMax",
        "bodyweight",
        "side",
        "sg",
    )
    canon = dumps(
        {
            "routines": [
                [
                    r["id"],
                    r["name"],
                    r["prog"],
                    [":".join(string(e.get(k)) for k in fields) for e in r["ex"]],
                ]
                for r in plan["routines"]
            ],
            "week": [
                k + "=" + "+".join(string(v) for v in plan["week"][k])
                for k in sorted(plan["week"])
            ],
        }
    )
    h1, h2 = 0x811C9DC5, 0x01000193
    encoded = canon.encode("utf-16-le")
    for i in range(len(encoded) // 2):
        c = int.from_bytes(encoded[i * 2 : i * 2 + 2], "little")
        h1 = ((h1 ^ c) * 0x01000193) & 0xFFFFFFFF
        h2 = ((h2 ^ ((c << 3) | (i & 7))) * 0x85EBCA6B) & 0xFFFFFFFF
    return f"{h1:08x}{h2:08x}"


def library_slice(state, equipment, keep, maximum):
    wanted = [string(e).lower() for e in equipment]
    equipped = [
        e
        for e in LIBRARY
        if not wanted or e["eq"].lower() in wanted or e["eq"].lower() == "body weight"
    ] or LIBRARY
    base = [
        e
        for e in equipped
        if not re.search(r"\bstretch(es|ing)?\b", e["n"], re.IGNORECASE)
    ] or equipped
    out = list({eid: BY_ID[eid] for eid in keep if eid in BY_ID}.values())
    taken = {e["id"] for e in out}
    if len(base) + len(out) <= maximum:
        out += [e for e in base if e["id"] not in taken]
    else:
        lanes = {}
        for e in base:
            lanes.setdefault(e["bp"], []).append(e)
        weights = {
            "back": 4,
            "chest": 4,
            "upper legs": 4,
            "shoulders": 3,
            "upper arms": 2,
            "waist": 2,
        }
        cursor = {key: 0 for key in lanes}
        progressed = True
        while len(out) < maximum and progressed:
            progressed = False
            for key, lane in sorted(lanes.items()):
                for _ in range(weights.get(key, 1)):
                    while cursor[key] < len(lane) and lane[cursor[key]]["id"] in taken:
                        cursor[key] += 1
                    if cursor[key] >= len(lane) or len(out) >= maximum:
                        break
                    e = lane[cursor[key]]
                    cursor[key] += 1
                    out.append(e)
                    taken.add(e["id"])
                    progressed = True
    custom = [
        {
            "id": text(c["id"], 64),
            "n": text(c.get("n"), 80),
            "bp": text(c.get("bp"), 40),
            "custom": True,
        }
        for c in records(state.get("customEx"))
        if isinstance(c.get("id"), str) and c["id"]
    ]
    return custom + [{k: e[k] for k in ("id", "n", "bp")} for e in out]


def minutes(workout):
    return (
        rounded((numeric(workout["end"]) - numeric(workout["start"])) / 60000)
        if workout.get("end") and workout.get("start")
        else None
    )


def clean_set(row):
    result = {"done": bool(row.get("done"))}
    if warmup(row):
        result["warmup"] = True
    elif row.get("failure") is True:
        result["failure"] = True
    result.update(
        {
            k: row[k]
            for k in ("w", "r", "sec", "min", "speed", "rir", "rpe")
            if number(row.get(k)) is not None
        }
    )
    return result


def fmt_set(row):
    effort = (
        "@RIR" + string(row["rir"])
        if row.get("rir") is not None
        else "@RPE" + string(row["rpe"])
        if row.get("rpe") is not None
        else "@failure"
        if row.get("failure") and not warmup(row)
        else ""
    )
    if row.get("sec") is not None:
        return string(row["sec"]) + "s" + effort
    if row.get("min") is not None:
        return (
            string(row["min"])
            + "min"
            + ("/" + string(row["speed"]) if row.get("speed") is not None else "")
            + effort
        )
    return (
        (string(row["w"]) + "x" if row.get("w") is not None else "")
        + (string(row["r"]) if row.get("r") is not None else "?")
        + effort
    )


def clean_workout(workout, compact=False):
    result = {
        "d": day(workout.get("d")),
        "name": text(workout.get("name"), 80) or None,
        "minutes": minutes(workout),
        "prs": len(items(workout.get("prs"))),
        "entries": [],
    }
    if compact:
        result["compact"] = True
    else:
        if workout.get("rating"):
            result["rating"] = (
                workout["rating"]
                if type(workout["rating"]) in (int, float)
                else cut(workout["rating"], 20)
            )
        if workout.get("note"):
            result["note"] = cut(workout["note"], 500)
    for en in records(workout.get("entries")):
        target = (
            {
                k: en["target"][k]
                for k in ("sets", "reps", "sec", "weight")
                if number(obj(en.get("target")).get(k)) is not None
            }
            if isinstance(en.get("target"), dict)
            else None
        )
        row = {
            "id": ident(en.get("id")),
            "name": obj(BY_ID.get(ident(en.get("id")))).get("n"),
        }
        sets = [
            clean_set(s)
            for s in records(en.get("sets"))
            if not compact or not warmup(s)
        ]
        if compact:
            done = [s for s in sets if s["done"]]
            row["done"] = f"{len(done)}/{len(sets)}"
            if target is not None:
                row["target"] = fmt_set(
                    {
                        "w": target.get("weight"),
                        "r": target.get("reps"),
                        "sec": target.get("sec"),
                    }
                )
            if done:
                row["top"] = fmt_set(
                    max(
                        done,
                        key=lambda s: (
                            numeric(s.get("w")) * numeric(s.get("r"))
                            + numeric(s.get("sec"))
                        ),
                    )
                )
        else:
            row.update(target=target, sets=sets)
        result["entries"].append(row)
    return result


def aggregates(state, workouts):
    configs = {
        ident(e.get("id")): e
        for r in records(state.get("routines"))
        for e in records(r.get("ex"))
    }
    sessions = {}
    for workout in records(state.get("workouts")):
        for en in records(workout.get("entries")):
            logged = [s for s in records(en.get("sets")) if not warmup(s)]
            if not any(s.get("done") for s in records(en.get("sets"))):
                continue
            eid = ident(en.get("id"))
            target = obj(en.get("target")) or configs.get(eid, {})
            goals = (
                items(target.get("rowReps"))
                if en.get("target") and mode(target, BY_ID.get(eid)) == "reps"
                else []
            )
            planned = (
                len(goals) if goals else numeric(target.get("sets")) or len(logged)
            )
            selected = logged[: max(1, int(planned))] if en.get("target") else logged
            field = "sec" if mode(target, BY_ID.get(eid)) == "time" else "r"
            goal = (
                max([numeric(v) for v in goals])
                if goals
                else numeric(target.get("sec" if field == "sec" else "reps"))
            )
            hit = (
                goal > 0
                and len(logged) >= planned
                and bool(selected)
                and all(
                    (numeric(s.get(field)) if s.get("done") else 0)
                    >= (numeric(goals[i]) if i < len(goals) else goal)
                    for i, s in enumerate(selected)
                )
            )
            sessions.setdefault(eid, []).append(hit)
    exercises = []
    for eid, hits in sessions.items():
        stalls = 0
        for hit in reversed(hits):
            if hit:
                break
            stalls += 1
        if stalls or len(hits) >= 3:
            exercises.append(
                {
                    "id": eid,
                    "name": obj(BY_ID.get(eid)).get("n"),
                    "sessions": len(hits),
                    "stalls": stalls,
                    "lastOk": hits[-1],
                }
            )
    coverage = {}
    for w in workouts:
        for en in records(w.get("entries")):
            bp = obj(BY_ID.get(ident(en.get("id")))).get("bp")
            done = sum(
                1 for s in records(en.get("sets")) if s.get("done") and not warmup(s)
            )
            if bp and done:
                coverage[bp] = coverage.get(bp, 0) + done
    durations = sorted(m for w in workouts if (m := minutes(w)))
    dates = {w.get("d") for w in workouts}
    return {
        "exercises": exercises,
        "adherence": {
            "plannedPerWeek": sum(bool(v) for v in obj(state.get("week")).values()),
            "sessionsInWindow": len(workouts),
            "distinctDays": len(dates),
            "dayOverrides": sum(
                1
                for d in obj(state.get("dayPlan"))
                if d in dates or d >= (workouts[0].get("d", "") if workouts else "")
            ),
        },
        "setsByBodyPart": coverage,
        "sessionMinutes": {
            "median": durations[len(durations) // 2],
            "min": durations[0],
            "max": durations[-1],
        }
        if durations
        else None,
    }


def find_workout(state, workout_id):
    workouts = [w for w in records(state.get("workouts")) if w.get("d")]
    return next(
        (w for w in workouts if workout_id and w.get("id") == workout_id),
        workouts[-1] if workouts else None,
    )


def workout_meta(state, workout_id):
    w = find_workout(state, workout_id)
    if w is None:
        return None
    sets = [
        s
        for en in records(w.get("entries"))
        for s in records(en.get("sets"))
        if s.get("done") and not warmup(s)
    ]
    return {
        "id": w.get("id") or None,
        "d": w["d"],
        "name": w.get("name") or None,
        "minutes": minutes(w),
        "vol": rounded(
            w["vol"]
            if type(w.get("vol")) in (int, float)
            else sum(numeric(s.get("w")) * numeric(s.get("r")) for s in sets)
        ),
        "sets": len(sets),
        "prs": len(items(w.get("prs"))),
    }


def build(state, owner, secret, kind, opts, previous=None, today=None):
    today = today or datetime.now(UTC).date()
    coach = obj(state.get("coach"))
    intake = opts.get("intake") or coach.get("profile")
    handle = hmac.new(
        secret.encode(), ("coach-handle:" + owner).encode(), hashlib.sha256
    ).digest()
    import base64

    p = {
        "coach_contract": 1,
        "task": kind,
        "meta": {
            "profile": base64.urlsafe_b64encode(handle).decode().rstrip("=")[:16],
            "lang": lang(opts.get("lang")) or text(state.get("lang"), 16) or "en",
            "unit": text(state.get("unit"), 8) or "kg",
            "effortScale": state.get("effort")
            if state.get("effort") in ("none", "rir", "rpe")
            else "rir"
            if state.get("showRir")
            else "none",
            "today": today.isoformat(),
        },
        "coachProfile": profile(intake) if isinstance(intake, dict) else None,
        "plan": clean_plan(state),
    }
    if (
        p["coachProfile"] is not None
        and not p["coachProfile"]["equipment"]
        and state.get("equipFilterOn")
    ):
        active = next(
            (
                x
                for x in records(state.get("equipProfiles"))
                if x.get("id") == state.get("activeEquipId")
            ),
            {},
        )
        p["coachProfile"]["equipment"] = profile(active)["equipment"]
    declined = [
        {"type": text(d.get("type"), 40) or None, "why": text(d.get("why"), 600)}
        for e in records(coach.get("log"))
        for d in records(e.get("decisions"))
        if d.get("status") == "rejected"
    ][-15:]
    if declined:
        p["previouslyDeclined"] = declined
    all_workouts = records(state.get("workouts"))
    if kind == "debrief":
        w = find_workout(state, opts.get("workoutId"))
        p.update(session=None, previous=[])
        if w is not None:
            p["session"] = {"id": ident(w.get("id")) or None, **clean_workout(w)}
            before = all_workouts[: all_workouts.index(w)]
            p["previous"] = [
                clean_workout(x)
                for x in before
                if x.get("name") and x.get("name") == w.get("name")
            ][-3:]
            p["aggregates"] = aggregates(state, [w])
            in_session = {ident(e.get("id")) for e in records(w.get("entries"))}
            p["aggregates"]["exercises"] = [
                e for e in p["aggregates"]["exercises"] if e["id"] in in_session
            ]
            try:
                since = (
                    datetime.fromisoformat(day(w.get("d"))).date() - timedelta(days=28)
                ).isoformat()
            except (TypeError, ValueError):
                since = None
            p["bodyweight"] = {
                "goal": number(state.get("targetW")),
                "series": weigh_ins(state, since, day(w.get("d"))) if since else [],
            }
        return p
    if kind == "review":
        cutoff = (today - timedelta(days=84)).isoformat()
        since = cut(obj(coach.get("lastReview")).get("at"), 10)
        window = [
            w
            for w in all_workouts
            if isinstance(w.get("d"), str) and w["d"] >= max(cutoff, since)
        ][-60:]
        p["window"] = {
            "from": day(window[0].get("d")) if window else None,
            "to": day(window[-1].get("d")) if window else None,
            "workouts": [
                clean_workout(w, i < len(window) - 3) for i, w in enumerate(window)
            ],
        }
        p["aggregates"] = aggregates(state, window)
        p["bodyweight"] = {
            "goal": number(state.get("targetW")),
            "series": weigh_ins(state, p["window"]["from"], None),
        }
        if opts.get("note"):
            p["userNote"] = cut(opts["note"], 4000)
    else:
        window = all_workouts
        best = {}
        for w in window:
            for en in records(w.get("entries")):
                for s in records(en.get("sets")):
                    eid = ident(en.get("id"))
                    if s.get("done") and numeric(s.get("w")) > 0 and not warmup(s):
                        best[eid] = max(best.get(eid, 0), numeric(s["w"]))
        if best:
            p["history"] = {
                "sessions": len(window),
                "since": day(window[0].get("d")),
                "workingWeights": [
                    {"id": eid, "name": obj(BY_ID.get(eid)).get("n"), "best": n}
                    for eid, n in best.items()
                ],
            }
        if opts.get("refine"):
            if previous:
                p["refine"] = {"text": cut(opts["refine"], 4000), "previous": previous}
            else:
                p["userNote"] = cut(opts["refine"], 4000)
    keep = [
        ident(e.get("id"))
        for r in records(state.get("routines"))
        for e in records(r.get("ex"))
    ]
    keep += [ident(e.get("id")) for w in window for e in records(w.get("entries"))]
    equipment = obj(p["coachProfile"]).get("equipment", [])
    p["library"] = library_slice(
        state, equipment, keep, 60 if kind == "review" else 160
    )
    current = {
        cut(opts.get("note"), 4000).strip(),
        cut(opts.get("refine"), 4000).strip(),
    }
    conversation = [
        {"who": m["role"], "text": m["text"].strip()[:240]}
        for m in records(coach.get("chat"))
        if isinstance(m.get("text"), str)
        and m["text"].strip()
        and (
            m.get("role") == "user"
            and m.get("kind") == "text"
            and m["text"].strip() not in current
            or m.get("role") == "coach"
            and m.get("kind") in ("nochange", "text")
        )
    ][-6:]
    if conversation:
        p["conversation"] = conversation
    return p


def weigh_ins(state, since, until):
    return [
        {"d": day(b.get("d")), "w": b["w"]}
        for b in records(state.get("bodyweight"))
        if day(b.get("d"))
        and number(b.get("w")) is not None
        and (not since or day(b["d"]) >= since)
        and (not until or day(b["d"]) <= until)
    ]
