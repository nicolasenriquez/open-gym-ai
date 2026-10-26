"""Required verification fails closed on omitted or empty proofs."""

import pytest

pytest_plugins = ["pytester"]


def pytest_sessionfinish(session, exitstatus):
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    omitted = ("skipped", "xfailed", "xpassed", "deselected")
    if (
        not session.testscollected
        or reporter is None
        or any(reporter.stats.get(outcome) for outcome in omitted)
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
