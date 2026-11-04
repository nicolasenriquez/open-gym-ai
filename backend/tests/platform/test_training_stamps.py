"""Readable stamping regressions; no transition document dumps or Node runtime."""

from copy import deepcopy

import pytest

from opengym_platform.training.stamps import stamp_put

NOW = 1_800_000_000_000


def stored():
    return {
        "_ts": NOW - 5000,
        "_rev": 3,
        "restSec": 90,
        "queue": {"ids": ["a"]},
        "week": {"1": "r1"},
        "workouts": [{"id": "w1"}, {"id": "w2"}],
        "routines": [
            {"id": "r1", "name": "Push", "ex": [], "_ts": NOW - 9000},
            {"id": "r2", "name": "Pull", "ex": [], "_ts": NOW - 9000},
        ],
        "deleted": {"workouts": {"w9": NOW - 4000}},
        "edited": {"restSec": NOW - 4000},
    }


def test_legacy_changes_keep_records_stamp_changes_and_leave_untouched_entries():
    current = stored()
    next = deepcopy(current)
    for key in ("deleted", "edited", "_rev"):
        del next[key]
    next["workouts"].pop()
    next["restSec"] = 120
    next["routines"][0]["name"] = "Push A"
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["deleted"]["workouts"] == {"w9": NOW - 4000, "w2": NOW}
    assert next["edited"]["restSec"] == NOW
    assert next["routines"][0]["_f"]["name"] == NOW
    assert next["routines"][1]["_ts"] == NOW - 9000


def test_planner_queue_removal_and_missing_setting():
    current = stored()
    current["hints"] = {"swipeSets": True}
    next = deepcopy(current)
    del next["hints"]
    next["queue"] = {"ids": ["b"]}
    next["routines"].pop()
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["edited"]["queue"] == NOW
    assert next["deleted"]["routines"]["r2"] == NOW
    assert "hints" not in next["edited"]


def test_stamped_client_joins_records_without_restamping_or_refilling_fields():
    current = stored()
    next = deepcopy(current)
    next.update(restSec=60, edited={"restSec": NOW - 100}, deleted={"workouts": {"w2": NOW - 100}})
    next["workouts"].pop()
    del next["queue"]
    del next["routines"][0]["name"]
    stamp_put(current, next, over_read=True, stamped=True, now=NOW)
    assert next["deleted"]["workouts"] == {"w9": NOW - 4000, "w2": NOW - 100}
    assert next["edited"]["restSec"] == NOW - 100
    assert "queue" not in next and "name" not in next["routines"][0]


def test_added_back_entries_win_removal_records():
    current = stored()
    current["deleted"].update(favEx={"squat": NOW - 4000})
    current["deleted"]["workouts"]["w1"] = NOW - 4000
    next = deepcopy(current)
    next["favEx"] = ["squat"]
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["deleted"]["favEx"]["squat"] < 0
    assert next["deleted"]["workouts"]["w1"] < 0
    assert [w["id"] for w in next["workouts"]] == ["w1", "w2"]


@pytest.mark.parametrize("stamped", [False, True])
def test_reset_does_not_refill_unknowns_or_old_records(stamped):
    current = stored()
    current["accentCustom"] = "#ff00aa"
    next = {"_ts": NOW, "resetAt": NOW, "workouts": [], "routines": []}
    stamp_put(current, next, over_read=True, stamped=stamped, now=NOW)
    assert "accentCustom" not in next and "deleted" not in next


def test_unconditional_replace_preserves_records_and_marks_restore():
    next = {"workouts": [{"id": "w9"}], "routines": []}
    stamp_put(stored(), next, now=NOW)
    assert next["deleted"]["workouts"]["w9"] < 0
    assert next["edited"]["restSec"] == NOW - 4000


@pytest.mark.parametrize("count", [1, 2])
def test_legacy_exercises_preserve_pyramids_including_duplicate_ids(count):
    current = stored()
    current["routines"][0]["ex"] = [
        {"id": "bench", "weight": 40, "pyramid": [12, 10, "max"], "sg": "g"}
        for _ in range(count)
    ]
    next = deepcopy(current)
    next["routines"][0]["ex"] = [{"id": "bench", "weight": 45} for _ in range(count)]
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["routines"][0]["ex"] == [
        {"id": "bench", "weight": 45, "pyramid": [12, 10, "max"]} for _ in range(count)
    ]
    assert next["routines"][0]["_f"]["ex"] == NOW


def test_unknown_fields_are_preserved_but_removed_middle_sets_are_not_guessed():
    current = stored()
    current.update(accentCustom="#ff00aa", showRir=True)
    current["workouts"][0].update(newer="x", entries=[{"id": "bench", "sets": [{"w": 1, "max": True}, {"w": 2}, {"w": 3, "max": True}]}])
    next = deepcopy(current)
    del next["accentCustom"], next["showRir"], next["workouts"][0]["newer"]
    next["workouts"][0]["entries"][0]["sets"] = [{"w": 1}, {"w": 3}]
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["accentCustom"] == "#ff00aa" and "showRir" not in next
    assert next["workouts"][0]["newer"] == "x"
    assert next["workouts"][0]["entries"][0]["sets"] == [{"w": 1}, {"w": 3}]


def test_stale_copy_cannot_undo_newer_settings_plan_or_routine_fields():
    current = stored()
    current.update(restSec=60, week={"1": "r2"}, edited={"restSec": NOW - 1000, "week.1": NOW - 1000, "theme": NOW - 9000}, theme="dark")
    current["routines"][0].update(ex=[{"id": "bench", "sets": 5}], _ts=NOW - 1000, _f={"ex": NOW - 1000})
    next = deepcopy(current)
    next.update(restSec=90, week={"1": "r1"}, edited={"restSec": NOW - 8000, "theme": NOW - 9000}, theme="light", _ts=NOW - 500)
    next["routines"][0] = {"id": "r1", "name": "Push A", "ex": [{"id": "bench", "sets": 3}], "_ts": NOW - 500}
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["restSec"] == 60 and next["week"] == {"1": "r2"}
    assert next["theme"] == "light" and next["edited"]["theme"] == NOW
    assert next["routines"][0]["name"] == "Push A"
    assert next["routines"][0]["ex"] == [{"id": "bench", "sets": 5}]
    assert next["routines"][0]["_f"]["ex"] == NOW - 1000


@pytest.mark.parametrize("record,expected", [(None, 45), ({}, 90), ({"restSec": NOW - 4000}, 45)])
def test_seen_or_unrecorded_change_is_admitted(record, expected):
    current = stored()
    next = deepcopy(current)
    if record is None:
        del next["edited"]
    else:
        next["edited"] = record
    next["restSec"] = 45
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["restSec"] == expected
    assert next["edited"]["restSec"] == (NOW if expected == 45 else NOW - 4000)


@pytest.mark.parametrize("value,expected", [
    (None, "4.x0xxgk"), (False, "5.324swo"), (0, "1.epw9f3"),
    ("😃 café", "9.1lpla4w"), ({"2": "two", "10": "ten", "a": 1}, "28.dktlfj"),
    ([0, 0.000001, 1e-7, 1e21], "23.f6bk8w"),
])
def test_independent_json_type_utf16_and_number_hash_answers(value, expected):
    next = {"setting": "new", "workouts": []}
    stamp_put({"setting": value, "workouts": []}, next, over_read=True, now=NOW)
    assert next["_prior"] == {"setting": [expected]}


@pytest.mark.parametrize("old,new,expected", [(None, {}, "4.x0xxgk"), ({}, None, "1.1ulrqj4")])
def test_absent_and_null_have_distinct_prior_history(old, new, expected):
    current = {"exNotes": {} if old == {} else {"x": old}}
    next = {"exNotes": {} if new == {} else {"x": new}}
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["_prior"] == {"exNotes.x": [expected]}


def test_numeric_string_marks_and_write_ids_are_not_settings():
    current = {"edited": {"setting": "0x10"}, "deleted": {"favEx": {"gone": "0b10000"}}}
    next = {"setting": 3, "_wid": "new", "_wids": ["old"], "edited": {"setting": 2, "_wid": 1}, "deleted": {"favEx": {"gone": 4}}}
    stamp_put(current, next, stamped=True, now=NOW)
    assert next["edited"] == {"setting": "0x10"}
    assert next["deleted"] == {"favEx": {"gone": "0b10000"}}


def test_repeated_legacy_changes_on_one_unread_copy_keep_its_own_new_values():
    current = stored()
    current["edited"]["week.1"] = NOW - 4000
    old = deepcopy(current)
    for index, (rest, name, day) in enumerate([
        (120, "Push B", ["r1"]), (150, "Push C", ["r1", "r2"]), (75, "Push D", []),
    ]):
        old.update(restSec=rest, week={"1": day}, _ts=NOW + index * 1000)
        old["routines"][0].update(name=name, _ts=NOW + index * 1000)
        old["routines"][0]["ex"].append({"id": str(index), "sets": 3})
        next = deepcopy(old)
        stamp_put(current, next, over_read=True, now=NOW + index * 1000)
        assert next["restSec"] == rest and next["week"] == {"1": day}
        assert next["routines"][0]["name"] == name
        assert len(next["routines"][0]["ex"]) == index + 1
        current = next


def test_own_changes_survive_interleaved_stamped_writer_but_old_queue_does_not():
    current = stored()
    old = deepcopy(current)
    old["workouts"].append({"id": "w3", "entries": [{"id": "bench", "sets": [{"w": 60, "r": 5}]}]})
    for index, rest in enumerate([180, 200]):
        old["restSec"] = rest
        next = deepcopy(old)
        stamp_put(current, next, over_read=True, now=NOW + index * 1000)
        current = next
    app = deepcopy(current)
    app.pop("_prior", None)
    app.pop("_unstamped", None)
    app.update(queue={"ids": ["b"]}, edited={**app["edited"], "queue": NOW + 2000})
    stamp_put(current, app, over_read=True, stamped=True, now=NOW + 2000)
    old["restSec"] = 270
    old["workouts"][-1]["entries"][0]["sets"].append({"w": 80, "r": 3})
    next = deepcopy(old)
    stamp_put(app, next, over_read=True, now=NOW + 3000)
    assert next["restSec"] == 270 and next["queue"] == {"ids": ["b"]}
    assert [s["w"] for s in next["workouts"][-1]["entries"][0]["sets"]] == [60, 80]
    old["queue"] = {"ids": ["c"]}
    changed = deepcopy(old)
    stamp_put(next, changed, over_read=True, now=NOW + 4000)
    assert changed["queue"] == {"ids": ["c"]}
    old["workouts"].pop()
    removed = deepcopy(old)
    stamp_put(changed, removed, over_read=True, now=NOW + 5000)
    assert removed["deleted"]["workouts"]["w3"] > 0
    assert not any(key.startswith("workouts|w3|") for key in removed.get("_prior", {}))


def test_inserted_exercises_keep_duplicate_exercise_pyramids_by_occurrence():
    current = stored()
    current["routines"][0]["ex"] = [
        {"id": "sq", "pyramid": [12, 10, 8, 6]}, {"id": "bench"}, {"id": "sq", "pyramid": [5, 5, 3]},
    ]
    next = deepcopy(current)
    next.pop("edited")
    next["routines"][0]["ex"] = [{"id": id} for id in ["sq", "row", "bench", "sq", "curl"]]
    stamp_put(current, next, over_read=True, now=NOW)
    assert [e.get("pyramid") for e in next["routines"][0]["ex"]] == [[12, 10, 8, 6], None, None, [5, 5, 3], None]


def test_legacy_reorder_stamp_advances_past_the_document_clock():
    current = stored()
    next = deepcopy(current)
    next["routines"].reverse()
    next["_ts"] = NOW + 9000
    stamp_put(current, next, over_read=True, now=NOW)
    assert next["edited"]["routineOrder"] == NOW + 9001


def test_old_order_cannot_undo_new_order_but_its_new_routine_is_kept():
    original = {"_ts": NOW - 5000, "edited": {"restSec": NOW - 5000}, "routines": [{"id": id, "name": id, "ex": []} for id in ["a", "b", "c"]]}
    current = deepcopy(original)
    current["routines"].reverse()
    current["edited"] = {"routineOrder": NOW - 1000}
    old = deepcopy(original)
    old["routines"].append({"id": "z", "name": "z", "ex": []})
    old["_ts"] = NOW + 9000
    stamp_put(current, old, over_read=True, now=NOW)
    assert [r["id"] for r in old["routines"]] == ["c", "z", "b", "a"]
