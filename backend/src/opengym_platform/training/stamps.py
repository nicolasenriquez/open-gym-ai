"""Pure port of api/sync-stamps.js; independent Node vectors guard compatibility."""

import json
import math
import time
from copy import deepcopy

MISSING = object()


def number(value):
    if value is MISSING:
        return 0
    if isinstance(value, list):
        value = ",".join(string(item) if item is not None else "" for item in value)
    try:
        if isinstance(value, str):
            text = value.strip()
            if text.lower().startswith(("0x", "0b", "0o")):
                return float(int(text, 0))
        result = float(value or 0)
        return 0 if math.isnan(result) else result
    except OverflowError:
        return -math.inf if str(value).startswith("-") else math.inf
    except (ValueError, TypeError):
        return 0


def get(value, key, default=MISSING):
    return value.get(key, default) if isinstance(value, dict) else default


def mapping(value):
    return value if isinstance(value, dict) else {}


def sequence(value):
    return value if isinstance(value, list) else []


def string(value):
    if value is MISSING:
        return "undefined"
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, dict):
        return "[object Object]"
    if isinstance(value, list):
        return ",".join("" if item is None else string(item) for item in value)
    if type(value) in (int, float):
        return encoded(value)
    return str(value)


def encoded(value):
    """JSON.stringify spelling for the JSON values hashed in legacy metadata."""
    if type(value) in (int, float):
        try:
            n = float(value)
        except OverflowError:
            return "null"
        if not math.isfinite(n):
            return "null"
        if n == 0:
            return "0"
        if n.is_integer() and abs(n) < 1e21:
            return str(int(n))
        text = repr(n)
        if "e" in text:
            mantissa, exponent = text.split("e")
            e = int(exponent)
            if -6 <= e < 21:
                from decimal import Decimal

                return format(Decimal(text), "f")
            return f"{mantissa.removesuffix('.0')}e{'+' if e >= 0 else '-'}{abs(e)}"
        return text
    if isinstance(value, dict):
        indices = sorted(
            (
                key
                for key in value
                if key.isascii()
                and key.isdigit()
                and str(int(key)) == key
                and int(key) < 4294967295
            ),
            key=int,
        )
        numeric = set(indices)
        keys = [*indices, *(key for key in value if key not in numeric)]
        return (
            "{"
            + ",".join(encoded(key) + ":" + encoded(value[key]) for key in keys)
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(encoded(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def same(a, b):
    if a is MISSING or b is MISSING:
        return a is b
    return encoded(a) == encoded(b)


def keys(a, b):
    return dict.fromkeys([*mapping(a), *mapping(b)])


def hash_text(text, *, fingerprint=False):
    units = text.encode("utf-16-le", errors="surrogatepass")
    a, b = 0x811C9DC5, 5381
    for i in range(0, len(units), 2):
        c = units[i] + 256 * units[i + 1]
        a = ((a ^ c) * 0x01000193) & 0xFFFFFFFF
        b = (b * 33 + c) & 0xFFFFFFFF

    def base36(n):
        result = ""
        while n:
            n, digit = divmod(n, 36)
            result = "0123456789abcdefghijklmnopqrstuvwxyz"[digit] + result
        return result or "0"

    return f"{len(units) // 2}.{base36(a)}" + (f".{base36(b)}" if fingerprint else "")


def value_hash(value):
    return hash_text("u" if value is MISSING else encoded(value))


def jsonb_order(value):
    # JSONB orders object keys by UTF-8 length then bytes; legacy hashes still use sent order.
    if isinstance(value, dict):
        return {
            k: jsonb_order(value[k])
            for k in sorted(
                value, key=lambda k: (len(k.encode("utf-8")), k.encode("utf-8"))
            )
        }
    if isinstance(value, list):
        return [jsonb_order(item) for item in value]
    return value


def fingerprint(sent):
    if not isinstance(sent, dict):
        return "none"
    return hash_text(
        encoded(
            [
                [k, sent[k]]
                for k in sorted(
                    sent, key=lambda k: k.encode("utf-16-be", errors="surrogatepass")
                )
            ]
        ),
        fingerprint=True,
    )


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


PER_KEY = {"week", "dayPlan", "exNotes", "barWeights"}
STAMPED_MAPS = (
    "balanceOverrides",
    "loadKind",
    "plates",
    "dbLoad",
    "dumbbells",
    "dayNotes",
)
OWN_MERGE = NOT_KEPT | {
    "_ts",
    "unit",
    "unitSet",
    "undone",
    "routineOrder",
    *ENTRY_LISTS,
    "bodyweight",
    "measurements",
    "favEx",
    "exWeights",
    *STAMPED_MAPS,
}
DEL_LISTS = (*ENTRY_LISTS, "bodyweight", "measurements", "favEx")


def entry_key(field, item):
    if field == "favEx":
        return item
    if field in {"bodyweight", "measurements"}:
        return get(item, "d")
    key = get(item, "id")
    if field == "workouts" and (key is MISSING or key is None):
        return f"{string(get(item, 'd'))}|{string(get(item, 'start'))}"
    return key


def entry_time(field, item):
    if field == "favEx":
        return 0
    if field in {"bodyweight", "measurements"}:
        return number(get(item, "t"))
    stamp = number(get(item, "_ts"))
    if field == "workouts":
        return stamp or number(get(item, "end")) or number(get(item, "start"))
    return stamp


def cap_stamps(stamps):
    excess = len(stamps) - 5000
    if excess > 0:
        for key in sorted(stamps, key=lambda k: abs(number(stamps[k])))[:excess]:
            del stamps[key]
    return stamps


def merge_deletions(a, b):
    out = {}
    for field in DEL_LISTS:
        merged = deepcopy(mapping(get(a, field)))
        for key, value in mapping(get(b, field)).items():
            x, y = number(value), number(merged.get(key))
            if key not in merged or abs(x) > abs(y) or (abs(x) == abs(y) and x < y):
                merged[key] = value
        if merged:
            out[field] = cap_stamps(merged)
    return out


def merge_edits(a, b):
    out = deepcopy(mapping(a))
    for key, value in mapping(b).items():
        if number(out.get(key)) < number(value):
            out[key] = value
    return out


def highest_stamp(state):
    state = mapping(state)
    stamps = [state.get("_ts"), get(state.get("unitSet"), "at"), state.get("resetAt")]
    stamps.extend(mapping(state.get("edited")).values())
    for deleted in mapping(state.get("deleted")).values():
        stamps.extend(mapping(deleted).values())
    for field in ENTRY_LISTS:
        for item in sequence(state.get(field)):
            stamps.append(get(item, "_ts"))
            stamps.extend(mapping(get(item, "_f")).values())
    for field in STAMPED_MAPS:
        stamps.extend(
            get(item, "_ts", 0) for item in mapping(state.get(field)).values()
        )
    return max([0, *(abs(number(stamp)) for stamp in stamps)])


def assign(target, key, value):
    if value is MISSING:
        target.pop(key, None)
    else:
        target[key] = deepcopy(value)


def same_entry(a, b):
    return same({**a, "_ts": 0, "_f": 0, "_u": 0}, {**b, "_ts": 0, "_f": 0, "_u": 0})


def stamp_entry(old, item, now):
    item["_ts"] = now
    stamps = deepcopy(mapping(old.get("_f")))
    for key in keys(old, item):
        if key not in META and not same(get(old, key), get(item, key)):
            stamps[key] = now
    if stamps:
        item["_f"] = stamps
    else:
        item.pop("_f", None)
    marks = {}
    for key, mark in mapping(item.get("_u")).items():
        at = number(stamps.get(key))
        if isinstance(mark, list):
            if len(mark) == 2 and at == now:
                marks[key] = [number(mark[0]), number(mark[1]), now]
            elif len(mark) == 3 and at > 0 and number(mark[2]) == at:
                marks[key] = mark
    if marks:
        item["_u"] = marks
    else:
        item.pop("_u", None)


def own_stamp(marks, key, value):
    return number(get(marks, key)) > 0 and number(get(marks, key)) == number(value)


def own_record(document, now, own, fp):
    edited, fields = {}, {}
    for key, value in mapping(document.get("edited")).items():
        if number(value) == now or own_stamp(get(own, "ed"), key, value):
            edited[key] = number(value)
    for field in ENTRY_LISTS:
        for item in sequence(document.get(field)):
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            key = f"{field}|{string(item['id'])}"
            stamps = {
                k: number(v)
                for k, v in mapping(item.get("_f")).items()
                if number(v) == now or own_stamp(get(get(own, "f"), key), k, v)
            }
            if stamps:
                fields[key] = stamps
    return (
        {
            "fp": fp,
            **({"ed": edited} if edited else {}),
            **({"f": fields} if fields else {}),
        }
        if edited or fields
        else None
    )


def by_id(items):
    return {
        identity(item): item
        for item in sequence(items)
        if isinstance(item, dict)
        and item.get("id") is not None
        and identity(item) is not None
    }


def note_prior(current, document):
    prior = deepcopy(mapping(current.get("_prior")))

    def note(key, before, after):
        if same(before, after):
            return
        hashed = value_hash(before)
        prior.pop(key, None)
        prior[key] = [
            *([v for v in sequence(get(current.get("_prior"), key)) if v != hashed]),
            hashed,
        ][-6:]

    for key in keys(current, document):
        if key in OWN_MERGE:
            continue
        if key in PER_KEY:
            before, after = mapping(current.get(key)), mapping(document.get(key))
            for sub in keys(before, after):
                note(f"{key}.{sub}", get(before, sub), get(after, sub))
        elif key in document:
            note(key, get(current, key), document[key])
    live = set()
    for field in ENTRY_LISTS:
        before = by_id(current.get(field))
        for item in sequence(document.get(field)):
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            prefix = f"{field}|{string(item['id'])}"
            live.add(prefix)
            old = before.get(identity(item))
            if old is None or same_entry(old, item):
                continue
            for key in keys(old, item):
                if key not in META:
                    note(f"{prefix}|{key}", get(old, key), get(item, key))
    for key in list(prior):
        if (
            any(key.startswith(f"{f}|") for f in ENTRY_LISTS)
            and key.rsplit("|", 1)[0] not in live
        ):
            del prior[key]
    for key in list(prior)[: max(0, len(prior) - 5000)]:
        del prior[key]
    if prior:
        document["_prior"] = prior


def order_moved(old, new):
    a = [
        identity(item)
        for item in sequence(old)
        if isinstance(item, dict) and item.get("id") is not None
    ]
    b = [
        identity(item)
        for item in sequence(new)
        if isinstance(item, dict) and item.get("id") is not None
    ]
    in_a, in_b = set(a), set(b)
    return [key for key in a if key in in_b] != [key for key in b if key in in_a]


def in_order_of(old, new):
    by = by_id(new)
    out = [by[identity(item)] for item in sequence(old) if identity(item) in by]
    at = {identity(item) for item in out}
    previous = None
    for item in sequence(new):
        if not isinstance(item, dict) or item.get("id") is None:
            out.append(item)
            continue
        key = identity(item)
        if key not in at:
            index = next(
                (
                    i
                    for i, entry in enumerate(out)
                    if previous is not None and identity(entry) == previous
                ),
                -1,
            )
            out.insert(index + 1, item)
            at.add(key)
        previous = key
    return out


def stamp_unstamped(current, document, sent, now, own):
    def was_before(key, value):
        history = get(current.get("_prior"), key)
        return (
            not isinstance(history, list)
            or value_hash(value) in history
            or value_hash(jsonb_order(value)) in history
        )

    deleted = mapping(document.get("deleted"))
    for field in DEL_LISTS:
        have = {
            string(entry_key(field, item))
            for item in sequence(document.get(field))
            if item is not None
        }
        for item in sequence(current.get(field)):
            if item is None:
                continue
            key = string(entry_key(field, item))
            if key in have:
                continue
            marks = mapping(deleted.get(field))
            deleted[field] = marks
            if not (
                number(marks.get(key)) > 0
                and number(marks.get(key)) >= entry_time(field, item)
            ):
                marks[key] = max(now, entry_time(field, item) + 1)
        if isinstance(deleted.get(field), dict):
            cap_stamps(deleted[field])
    if deleted:
        document["deleted"] = deleted
    edited = mapping(document.get("edited"))
    mine, theirs = mapping(sent), mapping(current.get("edited"))

    def moved(key):
        return number(mine.get(key)) > number(theirs.get(key))

    def stale(key):
        return (
            isinstance(sent, dict)
            and number(theirs.get(key)) > number(mine.get(key))
            and not own_stamp(get(own, "ed"), key, theirs.get(key))
        )

    for key in keys(current, document):
        if key in OWN_MERGE:
            continue
        old, new = get(current, key), get(document, key)
        if key in PER_KEY:
            before, after = mapping(old), mapping(new)
            for sub in keys(before, after):
                stamp_key = f"{key}.{sub}"
                if same(get(before, sub), get(after, sub)):
                    continue
                if stale(stamp_key) and was_before(stamp_key, get(after, sub)):
                    if not isinstance(document.get(key), dict):
                        document[key] = {}
                    assign(document[key], sub, get(before, sub))
                elif not moved(stamp_key):
                    edited[stamp_key] = now
        elif new is not MISSING and not same(old, new):
            if stale(key) and was_before(key, new):
                assign(document, key, old)
            elif not moved(key):
                edited[key] = now
    if isinstance(document.get("routines"), list) and order_moved(
        current.get("routines"), document["routines"]
    ):
        if stale("routineOrder"):
            document["routines"] = in_order_of(
                current.get("routines"), document["routines"]
            )
        elif not moved("routineOrder"):
            edited["routineOrder"] = now
    if edited:
        document["edited"] = edited
    for field in ENTRY_LISTS:
        before = by_id(current.get(field))
        for item in sequence(document.get(field)):
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            old = before.get(identity(item))
            if old is None:
                if field != "workouts" and item.get("_ts") is None:
                    item["_ts"] = now
                continue
            if same_entry(old, item):
                continue
            if isinstance(sent, dict) or isinstance(item.get("_f"), dict):
                base, of = mapping(item.get("_f")), mapping(old.get("_f"))
                for key in keys(old, item):
                    if key in META or number(of.get(key)) <= number(base.get(key)):
                        continue
                    if own_stamp(
                        get(get(own, "f"), f"{field}|{string(item['id'])}"),
                        key,
                        of[key],
                    ):
                        continue
                    if same(get(old, key), get(item, key)) or not was_before(
                        f"{field}|{string(item['id'])}|{key}", get(item, key)
                    ):
                        continue
                    assign(item, key, get(old, key))
                merged = merge_edits(base, of)
                if merged:
                    item["_f"] = merged
                else:
                    item.pop("_f", None)
                if same_entry(old, item):
                    item["_ts"] = max(number(item.get("_ts")), number(old.get("_ts")))
                    continue
            stamp_entry(old, item, now)


def stamp_put(current, document, *, over_read=False, stamped=False, now=None):
    exists = current is not None
    now = max(
        number(int(time.time() * 1000) if now is None else now),
        highest_stamp(current) + 1,
        highest_stamp(document) + 1,
    )
    current = mapping(current)
    reset = number(document.get("resetAt")) > number(current.get("resetAt"))
    sent = (
        deepcopy(document.get("edited"))
        if isinstance(document.get("edited"), dict)
        else None
    )
    previous = current.get("_unstamped")
    document.pop("_unstamped", None)
    document.pop("_prior", None)
    corrected = False
    if exists and not reset:
        deleted = merge_deletions(current.get("deleted"), document.get("deleted"))
        edited = merge_edits(current.get("edited"), document.get("edited"))
        edited.pop("_wid", None)
        edited.pop("_wids", None)
        for key, value in (("deleted", deleted), ("edited", edited)):
            if value:
                document[key] = value
            else:
                document.pop(key, None)
        before = deepcopy(content(document))
        if not stamped:
            preserve_unknown(current, document)
        record = None
        if not stamped and over_read:
            fp = fingerprint(sent)
            own = (
                previous
                if isinstance(previous, dict) and previous.get("fp") == fp
                else None
            )
            stamp_unstamped(current, document, sent, now, own)
            record = own_record(document, now, own, fp)
        elif isinstance(previous, dict):
            record = own_record(document, math.nan, previous, previous.get("fp"))
        if record:
            document["_unstamped"] = record
        corrected = not stamped and not same(content(document), before)
    deleted = mapping(document.get("deleted"))
    for field in DEL_LISTS:
        marks = mapping(deleted.get(field))
        for item in sequence(document.get(field)):
            if item is None:
                continue
            key = string(entry_key(field, item))
            at = number(marks.get(key))
            if at > 0 and at >= entry_time(field, item):
                marks[key] = -max(now, at + 1)
    if exists and not reset:
        note_prior(current, document)
    return corrected
