"""Current platform lockfile, lint, format and type checks inside the test image."""

import subprocess

import pytest


@pytest.mark.parametrize(
    "command",
    [
        ["uv", "lock", "--check", "--offline"],
        ["uv", "pip", "check"],
        ["ruff", "check", "--no-cache", "src", "tests"],
        # Preserve grouped except syntax without changing the Python 3.14 runtime.
        [
            "ruff",
            "format",
            "--target-version",
            "py313",
            "--check",
            "--no-cache",
            "src",
            "tests",
        ],
        ["mypy", "--cache-dir", "/dev/null", "src", "tests"],
    ],
)
def test_platform_toolchain(command):
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
