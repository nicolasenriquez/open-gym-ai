"""Test-only pause at the real ops command boundary, never copied to ops/runtime."""

import json
import subprocess
import sys
import time
from pathlib import Path

root = Path("/run/maintenance")
proof = json.loads((root / "journal.json").read_text())
if proof["phase"] == "capturing":
    for _ in range(300):
        if (root / "allow-capture").is_file():
            break
        time.sleep(0.05)
    else:
        raise SystemExit(1)
raise SystemExit(
    subprocess.run([sys.executable, *sys.argv[1:]], check=False).returncode
)
