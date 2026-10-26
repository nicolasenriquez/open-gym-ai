"""Platform suites fail on skipped, xfailed or uncollected proofs."""

_skipped: list[str] = []


def pytest_runtest_logreport(report):
    if report.skipped or getattr(report, "wasxfail", None) is not None:
        _skipped.append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if _skipped or session.testscollected == 0:
        session.exitstatus = 1
