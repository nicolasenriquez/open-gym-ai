"""Test-only pause at the real ops command boundary, never copied to ops/runtime."""

import asyncio
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path

root = Path("/run/maintenance")
proof = json.loads((root / "journal.json").read_text())
if proof["phase"] == "bundling":
    sys.argv = sys.argv[2:]
    runpy.run_path("/app/tests/platform/bundle_probe.py", run_name="__main__")
if proof["phase"] == "checking" and (root / "pause-check").is_file():
    (root / "check-paused").touch()
    for _ in range(600):
        if not (root / "pause-check").exists():
            break
        time.sleep(0.05)
    else:
        raise SystemExit(1)
if proof["phase"] == "capturing":
    for _ in range(300):
        if (root / "allow-capture").is_file():
            break
        time.sleep(0.05)
    else:
        raise SystemExit(1)
# Observe the actual subprocess boundary, without requiring an executable tmpfs.
# Only the test image can pause after pg_dump and before the file copy.
if (root / "pause-after-dump").is_file() and proof["phase"] == "capturing":
    spawn = asyncio.create_subprocess_exec

    async def observed_spawn(*args, **kwargs):
        process = await spawn(*args, **kwargs)
        if args[0] == "pg_dump":
            wait = process.wait

            async def observed_wait():
                result = await wait()
                (root / "dump-complete").touch()
                for _ in range(300):
                    if (root / "allow-dump").is_file():
                        return result
                    await asyncio.sleep(0.05)
                raise TimeoutError("SYNTHETIC_OBSERVER_TIMEOUT")

            process.wait = observed_wait
        return process

    asyncio.create_subprocess_exec = observed_spawn
    sys.argv = sys.argv[2:]
    runpy.run_module("opengym_platform.operations", run_name="__main__")
raise SystemExit(
    subprocess.run([sys.executable, *sys.argv[1:]], check=False).returncode
)
