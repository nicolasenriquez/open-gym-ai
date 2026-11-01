"""Startup admission only: no lease, maintenance listener or background polling."""

import json
import os
import re
import stat
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
