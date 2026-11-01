"""Synthetic faults at real process/filesystem boundaries, never shipped in ops."""

import errno
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

fault = sys.argv.pop(1)
settings = json.loads(Path(sys.argv[sys.argv.index("--config") + 1]).read_text())
root = Path(settings["target_root"])
target = settings["instance_id"]
original = subprocess.Popen
calls = 0


def observe(args, *positional, **keywords):
    global calls
    if args[0] == "age" and "--decrypt" in args:
        calls += 1
        if calls == 2 and fault == "full":
            try:
                with (root / "owned-fill").open("wb", buffering=0) as output:
                    while True:
                        output.write(b"x" * 1048576)
            except OSError as error:
                assert error.errno == errno.ENOSPC
                print("SYNTHETIC_RESTORE_ENOSPC_OBSERVED", flush=True)
        if calls == 2 and fault == "post-extract":
            process = original(args, *positional, **keywords)
            wait = process.wait
            changed = False

            def mutate(*args, **kwargs):
                nonlocal changed
                result = wait(*args, **kwargs)
                if result == 0 and not changed:
                    path = root / target / "data" / "vapid.json"
                    path.write_bytes(b"z" * path.stat().st_size)
                    changed = True
                return result

            process.wait = mutate
            return process
        if calls == 2 and fault == "pause":
            process = original(args, *positional, **keywords)
            assert process.poll() is None
            (root / target / "decrypt-started").write_text("real-age-process")
            while True:
                time.sleep(1)
    return original(args, *positional, **keywords)


with patch.object(subprocess, "Popen", observe):
    try:
        runpy.run_module("opengym_platform.operations", run_name="__main__")
    except SystemExit:
        if fault == "full":
            assert not (root / target / "restore.json").exists()
            assert not json.loads((root / target / "gate/admission.json").read_text())[
                "allowed"
            ]
        raise
