"""Container entry point. Unimplemented proofs fail instead of being skipped."""

import json
import subprocess
import sys


def main() -> int:
    if sys.argv[1:] != ["environment"]:
        print(json.dumps({"code": "FOUNDATION_GROUP_UNAVAILABLE"}))
        return 1
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "tests/test_environment.py",
            ],
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            return 1
        print(json.dumps({"code": "FOUNDATION_ENVIRONMENT_OK"}))
        return 0
    except OSError, subprocess.TimeoutExpired:
        print(json.dumps({"code": "FOUNDATION_RUNNER_FAILED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
