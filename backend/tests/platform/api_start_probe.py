"""Test-only API startup failure; otherwise run the real Uvicorn/factory."""

import runpy
from pathlib import Path

if Path("/run/maintenance-gate/fail-start").exists():
    raise SystemExit("SYNTHETIC_START_FAILURE")
runpy.run_module("uvicorn", run_name="__main__")
