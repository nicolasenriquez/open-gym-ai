"""Startup admission only: no lease, maintenance listener or background polling."""

import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path


def check_startup():
    directory = os.environ.get("PLATFORM_MAINTENANCE_GATE_DIR")
    if directory is None:
        return
    try:
        descriptor = os.open(
            Path(directory) / "admission.json",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        )
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > 4096
            ):
                raise ValueError()
            admission = json.loads(os.read(descriptor, 4097))
        finally:
            os.close(descriptor)
        if (
            not isinstance(admission, dict)
            or set(admission) != {"instance_id", "operation", "allowed"}
            or not os.environ.get("PLATFORM_INSTANCE_ID")
            or admission["instance_id"] != os.environ["PLATFORM_INSTANCE_ID"]
            or not re.fullmatch(r"[a-f0-9]{32}", admission["operation"])
            or admission["allowed"] is not True
        ):
            raise ValueError()
    except (OSError, ValueError, TypeError):
        raise RuntimeError("PLATFORM_MAINTENANCE_BLOCKED") from None


def backup_status():
    """Last local verification evidence, not a live probe of the backup disk."""
    directory = os.environ.get("PLATFORM_MAINTENANCE_GATE_DIR")
    if directory is None:
        return {"state": "missing", "verified": False}
    try:
        descriptor = os.open(
            Path(directory) / "backup.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        )
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > 4096
            ):
                raise ValueError()
            receipt = json.loads(os.read(descriptor, 4097))
        finally:
            os.close(descriptor)
        if (
            type(receipt["version"]) is not int
            or receipt["version"] != 1
            or receipt["verified"] is not True
            or receipt["instance_id"] != os.environ.get("PLATFORM_INSTANCE_ID")
            or not re.fullmatch(r"[a-f0-9]{32}", receipt["operation"])
            or receipt["ciphertext"]["path"] != receipt["operation"] + ".age"
            or not re.fullmatch(r"[a-f0-9]{64}", receipt["ciphertext"]["sha256"])
            or type(receipt["ciphertext"]["size"]) is not int
            or receipt["ciphertext"]["size"] <= 0
        ):
            raise ValueError()
        snapshot = datetime.fromisoformat(receipt["snapshot_at"])
        verified = datetime.fromisoformat(receipt["verified_at"])
        now = datetime.now(UTC)
        if (
            snapshot.tzinfo is None
            or verified.tzinfo is None
            or not snapshot <= verified <= now
        ):
            raise ValueError()
        age = int((now - snapshot).total_seconds())
        return {
            "state": "current"
            if age < 10800
            else "overdue"
            if age <= 21600
            else "rpo_exceeded",
            "verified": True,
            "operation": receipt["operation"],
            "snapshot_at": receipt["snapshot_at"],
            "verified_at": receipt["verified_at"],
            "age_seconds": age,
        }
    except FileNotFoundError:
        return {"state": "missing", "verified": False}
    except (OSError, ValueError, KeyError, TypeError):
        return {"state": "invalid", "verified": False}
