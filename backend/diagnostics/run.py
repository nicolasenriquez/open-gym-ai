"""Supervise standard syslog and serialize standard retention commands."""

import fcntl
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path


def retain():
    with Path("/state/retention.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 3
        for name in ("api", "nginx", "postgres", "ops"):
            # Keep active inodes attached to the writer; expired archives may be removed.
            subprocess.run(
                [
                    "find",
                    "/logs",
                    "-maxdepth",
                    "1",
                    "-type",
                    "f",
                    "-name",
                    name + ".log",
                    "-mmin",
                    "+8640",
                    "-exec",
                    "truncate",
                    "-s",
                    "0",
                    "{}",
                    ";",
                ],
                check=True,
                timeout=5,
            )
            subprocess.run(
                [
                    "find",
                    "/logs",
                    "-maxdepth",
                    "1",
                    "-type",
                    "f",
                    "-regextype",
                    "posix-extended",
                    "-regex",
                    rf"/logs/{name}\.log\.([1-9]|[1-9][0-9]|1[0-5][0-9]|16[0-8])",
                    "-mmin",
                    "+8640",
                    "-delete",
                ],
                check=True,
                timeout=5,
            )
        subprocess.run(
            [
                "logrotate",
                "--force",
                "--state",
                "/state/logrotate.state",
                "/etc/opengym/logrotate.conf",
            ],
            check=True,
            timeout=5,
        )
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--retain"]:
        raise SystemExit(retain())
    if sys.argv[1:]:
        raise SystemExit(2)
    # Keep the singleton lock for the entire process lifetime.
    owner = Path("/run/diagnostics/collector.lock").open("a")  # noqa: SIM115
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = Path("/run/diagnostics/log")
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise SystemExit("DIAGNOSTIC_SOCKET_FOREIGN")
        path.unlink()
    if retain() != 0:
        raise SystemExit(1)
    child = subprocess.Popen(
        [
            "rsyslogd",
            "-n",
            "-i",
            "/state/rsyslog.pid",
            "-f",
            "/etc/opengym/rsyslog.conf",
        ]
    )
    signal.signal(signal.SIGTERM, lambda *_: child.terminate())
    signal.signal(signal.SIGINT, lambda *_: child.terminate())
    deadline = time.monotonic() + 3600
    ready = Path("/state/ready")
    try:
        while child.poll() is None:
            if path.is_socket() and not ready.exists():
                ready.touch(mode=0o600)
            if time.monotonic() >= deadline:
                if retain() != 0:
                    raise SystemExit(1)
                deadline = time.monotonic() + 3600
            time.sleep(0.2)
    finally:
        ready.unlink(missing_ok=True)
        child.terminate()
        try:
            child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    raise SystemExit(child.returncode)
