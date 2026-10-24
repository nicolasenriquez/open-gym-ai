"""Diagnostic scanner tests for the Foundation runner."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from opengym_platform.runner import scan_output


@pytest.mark.parametrize(
    ("output", "category"),
    [
        ("synthetic-python-foundation-pool-only", "secret"),
        ("synthetic-sensitive-value", "secret"),
        ("synthetic-secret-dsn", "secret"),
        ("INSERT INTO pool_fixture.rollback_probe", "sql"),
        ("select 'synthetic-row'", "sql"),
        ("CREATE ROLE python_foundation_pool_runtime", "sql"),
        ("SELECT set_config('app.owner_id', 'owner-a', true)", "sql"),
        ("synthetic-forbidden", "payload"),
        ("synthetic-before-commit", "payload"),
    ],
)
def test_scan_output_rejects_synthetic_leaks(output, category):
    assert scan_output(output) == category


def test_scan_output_accepts_clean_summary():
    assert scan_output(".................... [100%]\n20 passed in 1.30s\n") is None


def run_fixture(tmp_path, body):
    (tmp_path / "pytest.py").write_text(body)
    return subprocess.run(
        [sys.executable, "-m", "opengym_platform.runner", "pool"],
        cwd=tmp_path,
        env={
            "PYTHONPATH": os.pathsep.join(
                (str(tmp_path), str(Path(__file__).resolve().parents[1] / "src"))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.parametrize(
    ("marker", "category"),
    [
        ("synthetic-python-foundation-pool-only", "secret"),
        ("SELECT 'private'", "sql"),
        ("synthetic-forbidden", "payload"),
    ],
)
def test_runner_rejects_leaks_before_emitting_child_output(
    tmp_path, stream, marker, category
):
    result = run_fixture(
        tmp_path,
        f"import sys\nprint({marker!r}, file=sys.{stream})\n",
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "code": "FOUNDATION_DIAGNOSTIC_LEAK",
        "category": category,
    }
    assert marker not in result.stdout + result.stderr
    assert not result.stderr
    assert "FOUNDATION_POOL_OK" not in result.stdout


@pytest.mark.parametrize("status", [0, 23])
def test_runner_preserves_clean_output_and_test_failure(tmp_path, status):
    result = run_fixture(
        tmp_path,
        f"import sys\nprint('clean summary')\nprint('clean diagnostic', file=sys.stderr)\nsys.exit({status})\n",
    )
    assert result.returncode == (0 if status == 0 else 1)
    assert "clean summary" in result.stdout
    assert result.stderr == "clean diagnostic\n"
    assert ("FOUNDATION_POOL_OK" in result.stdout) == (status == 0)


def test_runner_refuses_oversized_output_without_replaying_it(tmp_path):
    result = run_fixture(tmp_path, "print('x' * (4 * 1024 * 1024 + 1))\n")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"code": "FOUNDATION_OUTPUT_LIMIT"}
    assert not result.stderr
