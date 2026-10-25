"""Container entry point. Unimplemented proofs fail instead of being skipped."""

import json
import re
import subprocess
import sys
from tempfile import TemporaryFile

_MARKERS = (
    (
        "secret",
        (
            "synthetic-python-foundation-only",
            "synthetic-python-foundation-pool-only",
            "synthetic-python-foundation-migrator-only",
            "synthetic-python-foundation-runtime-only",
            "synthetic-python-foundation-training-only",
            "synthetic-sensitive-value",
            "synthetic-secret-dsn",
        ),
    ),
    (
        "sql",
        (
            "CREATE ROLE",
            "CREATE TABLE",
            "DROP ROLE",
            "DROP SCHEMA",
            "INSERT INTO",
            "set_config(",
        ),
    ),
    ("payload", ("synthetic-forbidden", "synthetic-before-commit")),
)
_MAX_OUTPUT = 4 * 1024 * 1024


def scan_output(output):
    for category, markers in _MARKERS:
        if any(marker.casefold() in output.casefold() for marker in markers):
            return category
    if re.search(
        r"\b(?:select|update|delete\s+from|alter\s+table)\s+", output, re.IGNORECASE
    ):
        return "sql"
    return None


def main() -> int:
    tests = {
        "environment": ("tests/test_environment.py", "tests/test_health.py"),
        "pool": ("tests/core/test_database.py", "tests/test_runner.py"),
        "migrations": ("tests/test_migrations.py",),
        "isolation": ("tests/test_isolation.py",),
        "recovery": ("tests/test_recovery.py",),
    }
    if len(sys.argv) != 2 or sys.argv[1] not in (*tests, "checks"):
        print(json.dumps({"code": "FOUNDATION_GROUP_UNAVAILABLE"}))
        return 1
    group = sys.argv[1]
    commands = (
        [
            ["uv", "lock", "--check", "--offline"],
            ["uv", "pip", "check"],
            ["ruff", "check", "--no-cache", "src", "tests"],
            ["ruff", "format", "--check", "--no-cache", "src", "tests"],
            ["mypy", "--cache-dir", "/dev/null", "src", "tests"],
        ]
        if group == "checks"
        else [
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                *tests[group],
            ]
        ]
    )
    try:
        # Private tmpfs spools bound memory even when a failed child is noisy.
        with TemporaryFile() as stdout, TemporaryFile() as stderr:
            for command in commands:
                result = subprocess.run(
                    command,
                    check=False,
                    # The migration CLI matrix takes ~59 s before container overhead.
                    timeout=180 if group == "migrations" else 60,
                    stdout=stdout,
                    stderr=stderr,
                )
                if result.returncode != 0:
                    break
            if stdout.tell() + stderr.tell() > _MAX_OUTPUT:
                print(json.dumps({"code": "FOUNDATION_OUTPUT_LIMIT"}))
                return 1
            stdout.seek(0)
            stderr.seek(0)
            output = stdout.read(_MAX_OUTPUT).decode("utf-8", errors="replace")
            diagnostic = stderr.read(_MAX_OUTPUT).decode("utf-8", errors="replace")
        captured = output + diagnostic
        category = scan_output(captured)
        if category:
            print(
                json.dumps({"code": "FOUNDATION_DIAGNOSTIC_LEAK", "category": category})
            )
            return 1
        if re.search(r"\b[1-9]\d* (?:skipped|xfailed|xpassed|deselected)\b", captured):
            print(json.dumps({"code": "FOUNDATION_REQUIRED_PROOF_SKIPPED"}))
            return 1
        sys.stdout.write(output)
        sys.stderr.write(diagnostic)
        if result.returncode != 0:
            return 1
        print(json.dumps({"code": f"FOUNDATION_{group.upper()}_OK"}))
        return 0
    except OSError, subprocess.TimeoutExpired:
        print(json.dumps({"code": "FOUNDATION_RUNNER_FAILED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
