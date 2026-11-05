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


@pytest.mark.parametrize("ci,expected", [(False, 0), (True, 1)])
def test_local_selection_never_relaxes_ci(pytester, monkeypatch, ci, expected):
    if ci:
        monkeypatch.setenv("CI", "true")
    else:
        monkeypatch.delenv("CI", raising=False)
    policy = Path(__file__).resolve().parents[1] / "conftest.py"
    pytester.makeconftest(policy.read_text())
    pytester.makepyfile("def test_one(): pass\ndef test_two(): pass")
    result = pytester.runpytest_subprocess("-q", "--allow-deselected", "-k", "one")
    assert result.ret == expected


@pytest.mark.parametrize(
    "source,options",
    [
        ("def test_bad(): assert False", []),
        ("import pytest\ndef test_skip(): pytest.skip('omitted')", []),
        ("import pytest\ndef test_xfail(): pytest.xfail('omitted')", []),
        ("import pytest\n@pytest.mark.xfail\ndef test_xpass(): pass", []),
        ("# no required proof", []),
        ("def test_one(): pass", ["-k", "unmatched_case_987654321"]),
    ],
)
def test_local_selection_still_rejects_missing_or_failed_proof(
    pytester, monkeypatch, source, options
):
    monkeypatch.delenv("CI", raising=False)
    policy = Path(__file__).resolve().parents[1] / "conftest.py"
    pytester.makeconftest(policy.read_text())
    pytester.makepyfile(source)
    result = pytester.runpytest_subprocess("-q", "--allow-deselected", *options)
    assert result.ret == 1


def test_failed_subtest_fails_the_proof_without_omitting_later_cases(pytester):
    policy = Path(__file__).resolve().parents[1] / "conftest.py"
    pytester.makeconftest(policy.read_text())
    pytester.makepyfile("""
        def test_vectors(subtests):
            with subtests.test(case="bad"):
                assert False
            with subtests.test(case="later"):
                print("later-case-executed")
                assert True
    """)
    result = pytester.runpytest_subprocess("-q", "-s")
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*later-case-executed*"])
