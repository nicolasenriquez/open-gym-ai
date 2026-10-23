"""Container entry point. Unimplemented proofs fail instead of being skipped."""

import json
import subprocess
import sys


def main() -> int:
    tests = {
        "environment": "tests/test_environment.py",
        "pool": "tests/core/test_database.py",
    }
    if len(sys.argv) != 2 or sys.argv[1] not in tests:
        print(json.dumps({"code": "FOUNDATION_GROUP_UNAVAILABLE"}))
        return 1
    group = sys.argv[1]
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                tests[group],
            ],
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            return 1
        print(json.dumps({"code": f"FOUNDATION_{group.upper()}_OK"}))
        return 0
    except OSError, subprocess.TimeoutExpired:
        print(json.dumps({"code": "FOUNDATION_RUNNER_FAILED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
