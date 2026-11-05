"""Native independent Node vectors pin the Python privacy and proposal boundaries."""

import json
from datetime import date
from pathlib import Path

import pytest

from opengym_platform.coach.payload import build, glyph, plan_hash
from opengym_platform.coach.validation import refine_plan, validate

VECTORS = json.loads(
    Path(__file__).with_name("fixtures").joinpath("coach-vectors.json").read_text()
)


@pytest.mark.parametrize("case", VECTORS["glyphs"])
def test_independent_glyph_vectors(case):
    assert glyph(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", VECTORS["hashes"])
def test_fingerprint_preserves_full_schedule_identifiers(case):
    assert plan_hash(case["state"]) == case["expected"]


@pytest.mark.parametrize("case", VECTORS["validation"])
def test_independent_proposal_vectors(case):
    actual = validate(case["data"], case["kind"], case["payload"])
    assert {key: actual.get(key) for key in case["expected"]} == case["expected"]


@pytest.mark.parametrize("case", VECTORS["payloads"])
def test_independent_payload_and_plan_fingerprint(case):
    assert (
        build(
            case["state"],
            "A",
            "synthetic-vector-key-only",
            case["kind"],
            case["opts"],
            today=date(2026, 10, 30),
        )
        == case["expected"]
    )
    assert plan_hash(case["state"]) == case["hash"]


def test_malformed_refinement_cannot_be_accepted_as_an_unchanged_plan():
    previous = {
        "week": {"1": "r1"},
        "routines": [
            {"id": "r1", "name": "A", "ex": [{"id": "0001", "sets": 3, "reps": 8}]}
        ],
    }
    data = {"changes": [None]}
    assert not validate(refine_plan(previous, data), "create", {})["ok"]


def test_oversized_json_number_is_an_unusable_answer_instead_of_a_validator_crash():
    assert not validate(
        {"summary": "s", "score": 10**400, "highlights": ["h"]}, "debrief", {}
    )["ok"]
