"""The unknown-field correction required by Training's revision acknowledgement."""

from copy import deepcopy

ENTRY_LISTS = ("routines", "customEx", "equipProfiles", "gymCards", "workouts")
META = {"id", "_ts", "_f", "_u"}
NOT_KEPT = {
    "_rev",
    "_wid",
    "_wids",
    "_unstamped",
    "_prior",
    "active",
    "resetAt",
    "resetIds",
    "deleted",
    "edited",
}
DROPS = {
    "state": {"showRir"},
    "routines": {"excludeFromProgression"},
    "routines.ex": {
        "id",
        "sg",
        "sets",
        "min",
        "speed",
        "mode",
        "sec",
        "weight",
        "bodyweight",
        "prog",
        "inc",
        "deloadFactor",
        "note",
        "warmupSets",
        "restSec",
        "reps",
        "side",
        "repsMin",
        "repsMax",
        "intensifier",
    },
    "customEx": {"media", "url"},
    "workouts": {"media", "note", "name", "bw", "prs", "vol", "routineIds"},
    "workouts.entries": {"sg", "note", "notePin", "noProg", "topW"},
    "workouts.entries.sets": {
        "w",
        "r",
        "sec",
        "min",
        "km",
        "dist",
        "speed",
        "rir",
        "rpe",
        "planSec",
        "note",
        "done",
        "weightOrigin",
        "at",
        "sides",
        "type",
        "drops",
        "clusters",
        "warmup",
    },
}
NESTED = {"routines": "ex", "workouts": "entries", "workouts.entries": "sets"}


def identity(item):
    value = item.get("id") if isinstance(item, dict) else None
    if isinstance(value, (dict, list)):
        return None
    return ("number" if type(value) in (int, float) else type(value).__name__, value)


def pairs(old, new):
    if not isinstance(old, list) or not isinstance(new, list):
        return []
    # Tag IDs to keep JSON booleans distinct from numbers, as JavaScript Map does.
    a, b = [identity(item) for item in old], [identity(item) for item in new]
    if None in a or None in b:
        return []
    if all(value is not None for _, value in [*a, *b]):
        if len(set(a)) == len(a) and len(set(b)) == len(b):
            by_id = dict(zip(a, old))
            return [(by_id[key], item) for key, item in zip(b, new) if key in by_id]
        if len(a) * len(b) <= 40000:
            lengths = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
            for i in range(len(a) - 1, -1, -1):
                for j in range(len(b) - 1, -1, -1):
                    lengths[i][j] = (
                        lengths[i + 1][j + 1] + 1
                        if a[i] == b[j]
                        else max(lengths[i + 1][j], lengths[i][j + 1])
                    )
            result = []
            i = j = 0
            while i < len(a) and j < len(b):
                if a[i] == b[j]:
                    result.append((old[i], new[j]))
                    i, j = i + 1, j + 1
                elif lengths[i + 1][j] >= lengths[i][j + 1]:
                    i += 1
                else:
                    j += 1
            return result
    return list(zip(old, new)) if a == b else []


def keep_keys(old, new, place):
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    excluded = (
        DROPS.get(place, set()) | META | (NOT_KEPT if place == "state" else set())
    )
    for key in old.keys() - new.keys() - excluded:
        new[key] = deepcopy(old[key])
    if place in NESTED:
        field = NESTED[place]
        for before, after in pairs(old.get(field), new.get(field)):
            keep_keys(before, after, f"{place}.{field}")


def content(value):
    if isinstance(value, dict):
        return {
            key: content(item)
            for key, item in value.items()
            if key
            not in {
                "_ts",
                "_f",
                "_u",
                "_rev",
                "_wid",
                "_wids",
                "_unstamped",
                "_prior",
                "edited",
                "deleted",
                "undone",
            }
        }
    if isinstance(value, list):
        return [content(item) for item in value]
    return value


def preserve_unknown(current, document):
    # shortcut: full edit/deletion stamping and prior-value history belong to 3.3.
    before = content(document)
    keep_keys(current, document, "state")
    for field in ENTRY_LISTS:
        old, new = current.get(field), document.get(field)
        if not isinstance(old, list) or not isinstance(new, list):
            continue
        by_id = {
            identity(item): item
            for item in old
            if isinstance(item, dict)
            and item.get("id") is not None
            and identity(item) is not None
        }
        for item in new:
            if (
                isinstance(item, dict)
                and item.get("id") is not None
                and identity(item) in by_id
            ):
                keep_keys(by_id[identity(item)], item, field)
    return content(document) != before
