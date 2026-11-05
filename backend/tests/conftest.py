"""Required verification fails closed on omitted or empty proofs."""

import os

import pytest

pytest_plugins = ["pytester"]


def pytest_addoption(parser):
    parser.addoption(
        "--allow-deselected",
        action="store_true",
        help="Allow intentional local selection; ignored when CI is set.",
    )


def pytest_sessionfinish(session, exitstatus):
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    omitted = ("skipped", "xfailed", "xpassed", "deselected")
    if session.config.getoption("--allow-deselected") and not os.environ.get("CI"):
        omitted = ("skipped", "xfailed", "xpassed")
    if (
        not session.testscollected
        or reporter is None
        or any(reporter.stats.get(outcome) for outcome in omitted)
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
