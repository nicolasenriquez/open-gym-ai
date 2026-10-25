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


@pytest.mark.parametrize("outcome", ["skipped", "xfailed", "xpassed", "deselected"])
def test_runner_refuses_skipped_required_proofs(tmp_path, outcome):
    result = run_fixture(tmp_path, f"print('1 passed, 1 {outcome} in 0.01s')\n")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"code": "FOUNDATION_REQUIRED_PROOF_SKIPPED"}
    assert not result.stderr


@pytest.mark.parametrize("failure", ["lock", "lint", "format", "typing"])
def test_checks_reject_invalid_fixture_without_crediting_success(tmp_path, failure):
    project = Path(__file__).resolve().parents[1]
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_bytes((project / name).read_bytes())
    (tmp_path / ".venv").symlink_to(project / ".venv", target_is_directory=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "probe.py").write_text("# Synthetic fixture.\n")
    code = "def value() -> int:\n    return 1\n"
    if failure == "lock":
        manifest = tmp_path / "pyproject.toml"
        manifest.write_text(
            manifest.read_text().replace('version = "0.0.0"', 'version = "0.0.1"')
        )
    elif failure == "lint":
        code = "import math\n"
    elif failure == "format":
        code = "def value()->int:\n return 1\n"
    else:
        code = 'def value() -> int:\n    return "bad"\n'
    (tmp_path / "src" / "typed.py").write_text(code)
    result = subprocess.run(
        [sys.executable, "-m", "opengym_platform.runner", "checks"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(project / "src")},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 1
    assert "FOUNDATION_CHECKS_OK" not in result.stdout
    diagnostic = result.stdout + result.stderr
    assert {
        "lock": "No solution found",
        "lint": "F401",
        "format": "would be reformatted",
        "typing": "Incompatible return value type",
    }[failure] in diagnostic
    assert (tmp_path / "uv.lock").read_bytes() == (project / "uv.lock").read_bytes()


def test_runner_refuses_oversized_output_without_replaying_it(tmp_path):
    result = run_fixture(tmp_path, "print('x' * (4 * 1024 * 1024 + 1))\n")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"code": "FOUNDATION_OUTPUT_LIMIT"}
    assert not result.stderr
