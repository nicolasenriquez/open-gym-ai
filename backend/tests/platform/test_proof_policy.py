"""Retained required-proof checks exercise the current pytest entrypoint."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("source", "options", "expected"),
    [
        ("def test_ok(): pass", [], 0),
        ("def test_bad(): assert False", [], 1),
        ("import pytest\ndef test_skip(): pytest.skip('omitted')", [], 1),
        ("import pytest\ndef test_xfail(): pytest.xfail('omitted')", [], 1),
        ("import pytest\n@pytest.mark.xfail\ndef test_xpass(): pass", [], 1),
        ("# no required proof", [], 1),
        ("def test_one(): pass\ndef test_two(): pass", ["-k", "one"], 1),
    ],
)
def test_required_proof_policy(pytester, source, options, expected):
    policy = Path(__file__).resolve().parents[1] / "conftest.py"
    pytester.makeconftest(policy.read_text())
    pytester.makepyfile(source)
    result = pytester.runpytest_subprocess("-q", *options)
    assert result.ret == expected
