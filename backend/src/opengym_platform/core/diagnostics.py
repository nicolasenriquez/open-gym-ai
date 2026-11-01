"""Bounded best-effort standard logging to a private local syslog socket."""

import json
import logging
import logging.handlers
import os
import re
import socket
import time


class LocalSysLogHandler(logging.handlers.SysLogHandler):
    def _connect_unixsocket(self, address):
        # SysLogHandler's Unix reconnect ignores its timeout argument in Python 3.14.
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        try:
            self.socket.connect(address)
        except OSError:
            self.socket.close()
            raise


class Diagnostics:
    def __init__(self):
        self.path = os.environ.get("PLATFORM_LOG_SOCKET")
        self.directory = os.environ.get("PLATFORM_LOG_DIRECTORY")
        revision = os.environ.get("PLATFORM_REVISION", "unknown")
        self.revision = (
            revision if re.fullmatch(r"[a-f0-9]{7,40}", revision) else "unknown"
        )
        self.failures = 0
        self.degraded = False
        # A factory-local logger avoids retaining handlers from other app instances.
        self.logger = logging.Logger("opengym.diagnostic", logging.INFO)  # noqa: LOG001
        self.handler = None

    def emit(self, operation, result, duration):
        if not self.path:
            return
        try:
            if self.handler is None:
                self.handler = LocalSysLogHandler(
                    address=self.path, socktype=socket.SOCK_DGRAM, timeout=0
                )
                self.handler.ident = "opengym-api: "
                self.handler.handleError = self.failed
                self.logger.addHandler(self.handler)
            record = json.dumps(
                {
                    "service": "api",
                    "revision": self.revision,
                    "severity": "INFO",
                    "operation": operation,
                    "result": result,
                    "duration_ms": round(duration * 1000, 2),
                    "time": int(time.time()),
                },
                separators=(",", ":"),
            )
            self.logger.info(record)
        except (OSError, ValueError):
            self.failed(None)

    def failed(self, record):
        self.failures += 1
        self.degraded = True

    def close(self):
        if self.handler is not None:
            self.handler.close()

    def state(self):
        result = {
            "configured": bool(self.path),
            "degraded": self.degraded,
            "failures": self.failures,
            "delivery": "unconfirmed",
            "sink": "unknown",
        }
        if self.directory:
            try:
                size = 0
                with os.scandir(self.directory) as entries:
                    for count, entry in enumerate(entries, 1):
                        if (
                            count > 676
                            or not entry.is_file(follow_symlinks=False)
                            or not re.fullmatch(
                                r"(?:api|nginx|postgres|ops)\.log(?:\.(?:[1-9][0-9]?|1[0-5][0-9]|16[0-8]))?",
                                entry.name,
                            )
                        ):
                            raise ValueError
                        size += entry.stat(follow_symlinks=False).st_size
                result["bytes"] = size
                full = (
                    os.statvfs(self.directory).f_bavail == 0 or size > 256 * 1024 * 1024
                )
                result["sink"] = "full" if full else "space_available"
                result["degraded"] = self.degraded or full
            except (OSError, ValueError):
                result.update(sink="unavailable", degraded=True)
        return result
