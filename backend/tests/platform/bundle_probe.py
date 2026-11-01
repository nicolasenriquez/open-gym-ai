"""Test-only faults at real CLI/file/subprocess boundaries, never shipped in ops."""

import errno
import io
import json
import runpy
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from unittest.mock import patch

root = Path("/run/maintenance")
fault = (root / "bundle-fault").read_text() if (root / "bundle-fault").exists() else ""
settings = json.loads(Path(sys.argv[-1]).read_text())
if fault == "full":
    destination = Path("/tmp/full-destination")
    destination.mkdir(mode=0o700)
    try:
        with (destination / "fill").open("wb", buffering=0) as stream:
            while True:
                stream.write(b"x" * 65536)
    except OSError as error:
        assert error.errno == errno.ENOSPC
        (root / "bundle-fault-observed").write_text("ENOSPC")
    settings["destination"] = str(destination)
    Path(sys.argv[-1]).write_text(json.dumps(settings))

if fault == "mutex":
    blocker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            """import asyncio,asyncpg
from opengym_platform.core.platform_settings import load_database
async def hold():
 d=load_database('backup')
 c=await asyncpg.connect(host=d.host,port=5432,database=d.database,user=d.user,password=d.password,ssl=False)
 await c.execute('SELECT pg_advisory_lock(728322)')
 print('locked',flush=True)
 await asyncio.sleep(60)
asyncio.run(hold())""",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert blocker.stdout is not None
    assert blocker.stdout.readline().strip() == b"locked"
    (root / "bundle-fault-observed").write_text("mutex")

spawn = subprocess.Popen
observed = False


def observe(args, *positional, **kwargs):
    global observed
    if args[0] == "age" and "--encrypt" in args and fault == "pause":
        process = spawn(args, *positional, **kwargs)
        (root / "bundle-encrypting").write_text("actual-age-process-running")
        for _ in range(600):
            if not (root / "bundle-fault").exists():
                return process
            time.sleep(0.05)
        raise TimeoutError("SYNTHETIC_ENCRYPTION_PAUSE")
    if args[0] == "age" and "--decrypt" in args and not observed:
        observed = True
        (root / "bundle-verifying").write_text("actual-age-decrypt")
        path = Path(args[-1])
        if fault in {"checksum", "duplicate", "traversal", "link"}:
            plain = subprocess.check_output(args, stderr=subprocess.DEVNULL)
            changed = io.BytesIO()
            with tarfile.open(fileobj=io.BytesIO(plain)) as source:
                members = source.getmembers()
                with tarfile.open(
                    fileobj=changed, mode="w", format=tarfile.USTAR_FORMAT
                ) as target:
                    for member in members:
                        stream = source.extractfile(member) if member.isfile() else None
                        if (
                            fault == "checksum"
                            and member.name.startswith("data/uploads/A/")
                            and member.isfile()
                        ):
                            stream = io.BytesIO(b"z" * member.size)
                        target.addfile(member, stream)
                    if fault != "checksum":
                        member = tarfile.TarInfo(
                            {
                                "duplicate": "manifest.json",
                                "traversal": "../escape",
                                "link": "link",
                            }[fault]
                        )
                        if fault == "link":
                            member.type = tarfile.SYMTYPE
                            member.linkname = "/run/bundle-key"
                        target.addfile(member)
            with path.open("wb") as output:
                subprocess.run(
                    ["age", "--encrypt", "--recipient", settings["recipient"]],
                    input=changed.getvalue(),
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            (root / "bundle-fault-observed").write_text(fault)
    process = spawn(args, *positional, **kwargs)
    if args[0] == "age" and "--decrypt" in args and fault == "post-verify":
        wait = process.wait
        altered = False

        def after_authentication(*args, **kwargs):
            nonlocal altered
            code = wait(*args, **kwargs)
            if code == 0 and not altered:
                altered = True
                path = Path(settings["destination"]) / (
                    settings["operation"] + ".age.partial"
                )
                with path.open("r+b") as stream:
                    stream.truncate(path.stat().st_size - 1)
                (root / "bundle-fault-observed").write_text("post-verify")
            return code

        patch.object(process, "wait", after_authentication).start()
    return process


copy = shutil.copyfileobj


def copy_with_truncated_authenticated_tail(source, output, length):
    copy(source, output, length)
    if fault == "truncate":
        # Corrupt before the initial hash; tar EOF remains in an authenticated chunk.
        encrypted = (
            Path(settings["staging_root"]) / settings["operation"] / "bundle.age"
        )
        plain = subprocess.check_output(
            ["age", "-d", "-i", settings["identity_file"], str(encrypted)],
            stderr=subprocess.DEVNULL,
        )
        result = subprocess.run(
            ["age", "-r", settings["recipient"]],
            input=plain + b"\0" * 131072,
            capture_output=True,
            check=True,
        )
        output.seek(0)
        output.write(result.stdout[:-1])
        output.truncate()
        output.flush()
        process = subprocess.Popen(
            ["age", "-d", "-i", settings["identity_file"], output.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert process.stdout is not None
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        while stream.read(65536):
                            pass
        while process.stdout.read(65536):
            pass
        assert process.wait() != 0, "tar EOF must precede failed age authentication"
        process.stdout.close()
        (root / "bundle-fault-observed").write_text("truncated-final-ciphertext-byte")


with (
    patch.object(subprocess, "Popen", observe),
    patch.object(shutil, "copyfileobj", copy_with_truncated_authenticated_tail),
):
    runpy.run_module("opengym_platform.operations", run_name="__main__")
