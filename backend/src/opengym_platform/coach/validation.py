"""Closed and bounded proposal vocabulary, independent of provider instructions."""

import copy
import math

from opengym_platform.coach.payload import (
    BY_ID,
    cut,
    glyph,
    items,
    obj,
    records,
    rounded,
)

POLICIES = ("off", "linear", "greyskull", "double", "triple", "time")
MODES = ("reps", "time", "cardio")
TYPES = (
    "add-exercise",
    "remove-exercise",
    "swap-exercise",
    "sets",
    "reps",
    "repsMin",
    "repsMax",
    "sec",
    "cardio",
    "reorder",
    "superset",
    "routine-prog",
    "exercise-prog",
    "inc",
    "add-routine",
    "remove-routine",
    "rename-routine",
    "week",
)
EX_TARGETS = (
    "remove-exercise",
    "swap-exercise",
    "sets",
    "reps",
    "repsMin",
    "repsMax",
    "sec",
    "cardio",
    "exercise-prog",
    "inc",
    "superset",
)
SCALARS = (
    "sets",
    "reps",
    "repsMin",
    "repsMax",
    "sec",
    "inc",
    "routine-prog",
    "exercise-prog",
    "rename-routine",
    "week",
)


def refine_plan(previous, data):
    if (
        not previous
        or not items(obj(data).get("changes"))
        or items(obj(data).get("routines"))
    ):
        return data
    routines = copy.deepcopy(previous.get("routines", []))
    for c in data["changes"]:
        if not isinstance(c, dict):
            return data
        if c.get("type") not in (
            "swap-exercise",
            "remove-exercise",
            "add-exercise",
            "sets",
            "reps",
            "repsMin",
            "repsMax",
            "sec",
        ):
            return data
        target = obj(c.get("target"))
        routine = next(
            (r for r in routines if r.get("id") == target.get("routineId")), None
        )
        if routine is None:
            holding = [
                r
                for r in routines
                if any(e.get("id") == target.get("exId") for e in records(r.get("ex")))
            ]
            if len(holding) != 1:
                return data
            routine = holding[0]
        after = c.get("after")
        if c["type"] == "add-exercise":
            if not isinstance(after, dict) or not isinstance(after.get("id"), str):
                return data
            position = after.get("position")
            row = {
                "sets": 3,
                **{k: v for k, v in after.items() if k != "position"},
                **({"why": c["why"]} if isinstance(c.get("why"), str) else {}),
            }
            routine["ex"].insert(
                int(position)
                if integer(position, 0, len(routine["ex"]))
                else len(routine["ex"]),
                row,
            )
            continue
        exercise = next(
            (
                e
                for e in records(routine.get("ex"))
                if e.get("id") == target.get("exId")
            ),
            None,
        )
        if exercise is None:
            return data
        if c["type"] == "remove-exercise":
            routine["ex"].remove(exercise)
        elif c["type"] == "swap-exercise":
            if not isinstance(after, dict) or not isinstance(after.get("id"), str):
                return data
            kept = {
                k: v
                for k, v in exercise.items()
                if k not in ("id", "weight", "why", "bodyweight", "side")
            }
            kept.update(
                {
                    k: after[k]
                    for k in ("id", "sets", "reps", "weight")
                    if after.get(k) is not None
                }
            )
            if isinstance(c.get("why"), str):
                kept["why"] = c["why"]
            routine["ex"][routine["ex"].index(exercise)] = kept
        else:
            if not is_number(after) or after != math.trunc(after):
                return data
            exercise[c["type"]] = after
    return {
        **previous,
        **(
            {"coach_contract": data["coach_contract"]}
            if "coach_contract" in data
            else {}
        ),
        "summary": data["summary"]
        if is_string(data.get("summary"))
        else previous.get("summary"),
        "routines": routines,
    }


def is_string(v):
    return isinstance(v, str) and bool(v.strip())


def is_number(v):
    try:
        return type(v) in (int, float) and math.isfinite(v)
    except OverflowError:
        return False


def integer(v, lo, hi):
    return is_number(v) and v == math.trunc(v) and lo <= v <= hi


def require(condition, message):
    if not condition:
        raise ValueError(message)


def known(eid, payload, custom=()):
    return isinstance(eid, str) and (
        eid in BY_ID
        or eid in custom
        or any(
            e.get("id") == eid and e.get("custom")
            for e in records(payload.get("library"))
        )
    )


def equipped(eid, payload):
    equipment = obj(payload.get("coachProfile")).get("equipment", [])
    return (
        not equipment
        or eid not in BY_ID
        or any(e.get("id") == eid for e in records(payload.get("library")))
        or BY_ID[eid]["eq"].lower() == "body weight"
        or BY_ID[eid]["eq"].lower() in [str(e).lower() for e in equipment]
    )


def prescription(v, *, create=False, name=False):
    result = {"id": v["id"], "sets": v["sets"] if integer(v.get("sets"), 1, 10) else 3}
    kind = v.get("mode") if v.get("mode") in MODES else "reps"
    if name:
        result["name"] = obj(BY_ID.get(v["id"])).get("n")
    if not create or kind != "cardio":
        result["mode"] = kind
    for key, lo, hi in (
        ("reps", 1, 100),
        ("sec", 5, 3600),
        ("repsMin", 1, 100),
        ("repsMax", 1, 100),
        ("setsMax", 1, 10),
    ):
        if integer(v.get(key), lo, hi) and (
            not create
            or key not in ("reps", "sec")
            or (key == "reps" and kind == "reps")
            or (key == "sec" and kind == "time")
        ):
            result[key] = v[key]
    if create:
        if kind == "reps":
            result.setdefault("reps", 10)
        elif kind == "time":
            result.setdefault("sec", 45)
        else:
            result["min"] = v["min"] if integer(v.get("min"), 1, 180) else 20
            result["speed"] = (
                v["speed"] if is_number(v.get("speed")) and 0 < v["speed"] <= 60 else 8
            )
    if v.get("prog") in POLICIES:
        result["prog"] = v["prog"]
    if create and v.get("prog") is not None:
        require(v["prog"] in POLICIES, "exercise progression is not allowed")
    if (
        is_number(v.get("weight"))
        and 0 < v["weight"] <= 1000
        and (not create or kind != "cardio")
    ):
        result["weight"] = v["weight"]
    if is_number(v.get("inc")) and 0 < v["inc"] <= 50:
        result["inc"] = v["inc"]
    if v.get("bodyweight") is not None:
        result["bodyweight"] = bool(v["bodyweight"])
    if v.get("side"):
        result["side"] = True
        require(
            not integer(result.get("reps"), 1, 100) or result["reps"] % 2 == 0,
            "per-side repetitions must be even",
        )
    require(
        not (
            result.get("repsMax") is not None
            and result.get("repsMin") is not None
            and result["repsMax"] < result["repsMin"]
        ),
        "rep ceiling must be at least the floor",
    )
    if create:
        for key, limit in (("sg", 20), ("why", 400)):
            if is_string(v.get(key)):
                result[key] = cut(v[key], limit)
    return result


def validate_plan(data, payload):
    require(not data.get("nochange"), "a complete plan was requested")
    require(
        isinstance(data.get("routines"), list) and data["routines"],
        "routines must be a non-empty array",
    )
    for c in records(data.get("customEx")):
        require(
            not is_string(c.get("id")) or c["id"] not in BY_ID,
            "custom exercise shadows a catalogue id",
        )
    custom = [
        {
            "id": cut(c["id"], 40),
            "n": cut(c["n"], 60),
            "bp": cut(c.get("bp") or "waist", 30),
            **({"desc": cut(c["desc"], 400)} if c.get("desc") else {}),
        }
        for c in records(data.get("customEx"))
        if is_string(c.get("id"))
        and c["id"] not in ("__proto__", "constructor", "prototype")
        and c["id"] not in BY_ID
        and is_string(c.get("n"))
    ][:20]
    routines = []
    weights = {
        w.get("id"): w.get("best")
        for w in records(obj(payload.get("history")).get("workingWeights"))
    }
    for i, r in enumerate(data["routines"][:7]):
        require(
            isinstance(r, dict) and is_string(r.get("name")), "routine name is required"
        )
        require(
            r.get("prog") is None or r["prog"] in POLICIES,
            "routine progression is not allowed",
        )
        exercises = []
        for e in items(r.get("ex"))[:20]:
            require(
                isinstance(e, dict)
                and known(e.get("id"), payload, [c["id"] for c in custom]),
                "exercise must exist in catalogue or custom exercises",
            )
            require(
                equipped(e["id"], payload), "exercise requires unavailable equipment"
            )
            require(
                not any(x["id"] == e["id"] for x in exercises),
                "duplicate exercise in routine",
            )
            clean = prescription(e, create=True)
            if "weight" in clean:
                cap = weights.get(e["id"])
                if cap is None:
                    del clean["weight"]
                elif clean["weight"] > cap:
                    clean["weight"] = cap
            exercises.append(clean)
        require(exercises, "routine must have exercises")
        rid = (
            cut(r["id"], 40)
            if is_string(r.get("id"))
            and r["id"] not in ("__proto__", "constructor", "prototype")
            else f"r{i}"
        )
        require(not any(x["id"] == rid for x in routines), "duplicate routine id")
        routines.append(
            {
                "id": rid,
                "name": cut(r["name"], 40),
                "emoji": glyph(r.get("emoji")),
                **({"prog": r["prog"]} if r.get("prog") in POLICIES else {}),
                **({"why": cut(r["why"], 400)} if is_string(r.get("why")) else {}),
                "ex": exercises,
            }
        )
    week = {}
    for d, rid in obj(data.get("week")).items():
        require(str(d).strip() in [str(i) for i in range(7)], "weekday must be 0-6")
        require(
            any(r["id"] == rid for r in routines), "week references an unknown routine"
        )
        week[str(int(d))] = rid
    want = obj(payload.get("coachProfile")).get("daysPerWeek")
    require(
        not integer(want, 1, 7) or len(week) == want, "week must honor requested days"
    )
    bundle = {
        "opengym_plan": 1,
        "name": cut(data.get("name") or "Coach plan", 40),
        "summary": cut(data.get("summary"), 1200),
        "basedOn": cut(data.get("basedOn"), 400),
        "week": week,
        "routines": routines,
        "customEx": custom,
    }
    return {"ok": True, "result": {"bundle": bundle, "summary": bundle["summary"]}}


def validate_review(data, payload):
    if data.get("nochange"):
        return {
            "ok": True,
            "nochange": True,
            "reading": cut(data.get("reading") or data.get("summary"), 1200),
        }
    require(isinstance(data.get("changes"), list), "changes must be an array")
    plan = obj(payload.get("plan"))
    routines = {r.get("id"): r for r in records(plan.get("routines"))}
    changes, dropped, seen = [], [], set()
    for i, c in enumerate(data["changes"][:25]):
        require(
            isinstance(c, dict) and c.get("type") in TYPES, "change type is not allowed"
        )
        require(is_string(c.get("why")), "every change must cite evidence")
        kind, target, after = c["type"], obj(c.get("target")), c.get("after")
        routine = (
            routines.get(target.get("routineId"))
            if is_string(target.get("routineId"))
            else None
        )
        if kind not in ("add-routine", "week"):
            require(routine is not None, "target must name a routine from the plan")
        planned = next(
            (
                e
                for e in records(obj(routine).get("ex"))
                if e.get("id") == target.get("exId")
            ),
            None,
        )
        if kind in EX_TARGETS:
            require(planned is not None, "target must name an exercise in this routine")
        cid = cut(c["id"], 40) if is_string(c.get("id")) else f"c{i}"
        if cid in seen:
            cid += f"-{i}"
        seen.add(cid)
        before = (
            obj(planned).get(kind)
            if kind in ("sets", "reps", "repsMin", "repsMax", "sec", "inc")
            else obj(planned).get("prog")
            if kind == "exercise-prog"
            else obj(routine).get("prog")
            if kind == "routine-prog"
            else obj(routine).get("name")
            if kind == "rename-routine"
            else obj(plan.get("week")).get(str(target.get("weekday")))
            if kind == "week"
            else None
        )
        clean_target = {
            k: cut(target[k], 40)
            for k in ("routineId", "exId")
            if is_string(target.get(k))
        }
        if integer(target.get("weekday"), 0, 6):
            clean_target["weekday"] = target["weekday"]
        out = {
            "id": cid,
            "type": kind,
            "target": clean_target,
            "why": cut(c["why"], 600),
            **({"routineName": cut(routine.get("name"), 40)} if routine else {}),
            "before": before,
            "after": after,
        }
        if kind in ("add-exercise", "swap-exercise"):
            a = obj(after)
            have = [e.get("id") for e in records(routine.get("ex"))]
            if a.get("id") in have and (
                kind == "add-exercise" or a.get("id") != target.get("exId")
            ):
                dropped.append(
                    (target.get("routineId"), [target.get("exId"), a.get("id")])
                )
                continue
            require(
                known(a.get("id"), payload) and equipped(a["id"], payload),
                "new exercise must be known and available",
            )
            if kind == "swap-exercise":
                require(
                    a["id"] != target.get("exId"), "cannot swap exercise for itself"
                )
                out["after"] = {
                    "id": a["id"],
                    "name": obj(BY_ID.get(a["id"])).get("n"),
                    **{
                        k: a[k]
                        for k, lo, hi in (("sets", 1, 10), ("reps", 1, 100))
                        if integer(a.get(k), lo, hi)
                    },
                    **(
                        {"weight": a["weight"]}
                        if is_number(a.get("weight")) and 0 < a["weight"] <= 1000
                        else {}
                    ),
                }
            else:
                clean = prescription(a, name=True)
                clean.pop("inc", None)
                if integer(a.get("position"), 0, 20):
                    clean["position"] = a["position"]
                out["after"] = clean
        elif kind in ("remove-exercise", "remove-routine"):
            out["after"] = None
        elif kind in ("sets", "reps", "repsMin", "repsMax", "sec"):
            lo, hi = (
                (1, 10) if kind == "sets" else (5, 3600) if kind == "sec" else (1, 100)
            )
            require(
                integer(after, lo, hi), "prescription must be a whole number in range"
            )
            if kind == "reps" and planned.get("side"):
                require(after % 2 == 0, "per-side repetitions must be even")
            if kind == "repsMin" and planned.get("repsMax") is not None:
                require(after <= planned["repsMax"], "rep floor exceeds ceiling")
            if kind == "repsMax" and planned.get("repsMin") is not None:
                require(after >= planned["repsMin"], "rep ceiling below floor")
        elif kind == "inc":
            require(
                is_number(after) and 0 < after <= 50,
                "increment must be positive and at most 50",
            )
        elif kind in ("routine-prog", "exercise-prog"):
            require(after in POLICIES, "progression is not allowed")
        elif kind == "cardio":
            a = obj(after)
            require(
                integer(a.get("min"), 1, 180) or is_number(a.get("speed")),
                "cardio requires minutes or speed",
            )
            out["after"] = {
                **({"min": a["min"]} if integer(a.get("min"), 1, 180) else {}),
                **(
                    {"speed": a["speed"]}
                    if is_number(a.get("speed")) and 0 < a["speed"] <= 60
                    else {}
                ),
            }
        elif kind == "reorder":
            have = [e.get("id") for e in records(routine.get("ex"))]
            require(
                isinstance(after, list)
                and len(after) == len(have)
                and all(is_string(v) for v in after)
                and len(set(after)) == len(after)
                and set(after) == set(have),
                "reorder must list every exercise exactly once",
            )
        elif kind == "superset":
            a = obj(after)
            if a.get("link"):
                require(
                    is_string(a.get("with"))
                    and a["with"] != target.get("exId")
                    and any(
                        e.get("id") == a["with"] for e in records(routine.get("ex"))
                    ),
                    "superset must name a different planned exercise",
                )
            out["after"] = {
                "link": bool(a.get("link")),
                **({"with": a["with"]} if a.get("link") else {}),
            }
        elif kind == "add-routine":
            a = obj(after)
            require(is_string(a.get("name")), "new routine requires a name")
            require(
                items(a.get("ex"))
                and all(
                    isinstance(e, dict)
                    and known(e.get("id"), payload)
                    and equipped(e["id"], payload)
                    for e in items(a.get("ex"))
                ),
                "new routine must name known available exercises",
            )
            exercises = [prescription(e, name=True) for e in a["ex"][:20]]
            for e in exercises:
                e.pop("weight", None)
            out["after"] = {
                "name": cut(a["name"], 40),
                "emoji": glyph(a.get("emoji")),
                **({"prog": a["prog"]} if a.get("prog") in POLICIES else {}),
                "ex": exercises,
            }
        elif kind == "rename-routine":
            require(is_string(after), "new routine name is required")
            out["after"] = cut(after, 40)
        elif kind == "week":
            require(integer(target.get("weekday"), 0, 6), "weekday must be 0-6")
            require(
                after is None
                or after == "rest"
                or is_string(after)
                and after in routines,
                "week must name a routine or rest",
            )
        changes.append(out)
    for rid, ids in dropped:
        require(
            not any(
                c["target"].get("routineId") == rid
                and any(
                    v in ids
                    for v in [
                        c["target"].get("exId"),
                        obj(c["after"]).get("id"),
                        obj(c["after"]).get("with"),
                    ]
                    if v is not None
                )
                for c in changes
            ),
            "cannot drop a change another change depends on",
        )
    changes = [
        c
        for c in changes
        if c["type"] not in SCALARS
        or c["before"] != c["after"]
        or isinstance(c["before"], bool) != isinstance(c["after"], bool)
    ]
    require(not dropped or changes, "duplicate exercise proposal requires repair")
    incoming, weekdays, by_routine = set(), set(), {}
    added, removed = 0, set()
    for c in changes:
        kind, target = c["type"], c["target"]
        rid = target.get("routineId")
        if rid:
            by_routine.setdefault(rid, []).append(kind)
        if kind in ("add-exercise", "swap-exercise"):
            key = (rid, c["after"]["id"])
            require(key not in incoming, "two changes introduce the same exercise")
            incoming.add(key)
        if kind == "remove-routine":
            removed.add(rid)
        if kind == "add-routine":
            added += 1
        if kind == "week":
            require(
                target["weekday"] not in weekdays,
                "two changes reschedule the same weekday",
            )
            weekdays.add(target["weekday"])
    for rid, types in by_routine.items():
        require(
            not (
                "reorder" in types
                and any(
                    t in types
                    for t in ("add-exercise", "remove-exercise", "swap-exercise")
                )
            ),
            "routine cannot be reordered and restructured together",
        )
        require(
            rid not in removed or all(t == "remove-routine" for t in types),
            "routine cannot be removed and changed together",
        )
        require(
            len(items(routines[rid].get("ex"))) + types.count("add-exercise") <= 20,
            "routine exceeds 20 exercises",
        )
    require(len(routines) + added - len(removed) <= 7, "plan exceeds seven routines")
    if not changes:
        return {
            "ok": True,
            "nochange": True,
            "reading": cut(data.get("summary") or data.get("reading"), 1200),
        }
    evidence = obj(data.get("evidence"))
    return {
        "ok": True,
        "result": {
            "summary": cut(data.get("summary"), 1200),
            "evidence": {
                "from": cut(evidence["from"], 40)
                if is_string(evidence.get("from"))
                else None,
                "to": cut(evidence["to"], 40)
                if is_string(evidence.get("to"))
                else None,
                "sessions": evidence["sessions"]
                if integer(evidence.get("sessions"), 0, 10000)
                else None,
            },
            "changes": changes,
            "notes": [cut(n, 600) for n in items(data.get("notes")) if is_string(n)][
                :6
            ],
        },
    }


def validate(data, kind, payload):
    try:
        require(isinstance(data, dict), "answer must be an object")
        require(
            "coach_contract" not in data
            or type(data["coach_contract"]) in (int, float)
            and data["coach_contract"] == 1,
            "coach_contract must be 1",
        )
        if kind == "create":
            return validate_plan(data, payload)
        if kind == "review":
            return validate_review(data, payload)
        require(
            not data.get("nochange") and not items(data.get("changes")),
            "a debrief cannot carry changes",
        )
        require(is_string(data.get("summary")), "debrief requires a summary")
        require(is_number(data.get("score")), "debrief score must be numeric")
        lists = {}
        for key in ("highlights", "watch", "nextTime"):
            require(
                data.get(key) is None or isinstance(data[key], list),
                "debrief lists must contain short strings",
            )
            lists[key] = [
                cut(v.strip(), 300) for v in items(data.get(key)) if is_string(v)
            ][:5]
        require(any(lists.values()), "debrief requires at least one observation")
        return {
            "ok": True,
            "result": {
                "summary": cut(data["summary"].strip(), 600),
                "score": max(1, min(10, rounded(data["score"]))),
                **lists,
            },
        }
    except (ValueError, TypeError, KeyError, AttributeError):
        return {
            "ok": False,
            "errors": [
                "answer violates task schema, target, equipment or prescription constraints; return the complete requested shape using the supplied plan and library"
            ],
        }
