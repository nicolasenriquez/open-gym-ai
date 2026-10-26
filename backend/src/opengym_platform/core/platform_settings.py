"""Explicit local Compose database configuration, separate from Foundation."""

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DatabaseTarget:
    host: str
    database: str
    user: str
    password: str = field(repr=False)
    migrator_password: str = field(default="", repr=False)
    runtime_password: str = field(default="", repr=False)


def _secret(variable):
    path = Path(os.environ.get(variable, ""))
    if not path.is_absolute():
        raise ValueError
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 32 <= info.st_size <= 4096:
            raise ValueError
        # Match PostgreSQL file_env: trailing LF is removed, CR is not normalized.
        value = os.read(descriptor, 4097).decode("utf-8").rstrip("\n")
        if (
            not 32 <= len(value) <= 4096
            or "\x00" in value
            or "\n" in value
            or "\r" in value
        ):
            raise ValueError
        return value
    finally:
        os.close(descriptor)


def load_database(role):
    try:
        environment = os.environ.get("PLATFORM_ENV")
        database = {"dev": "opengym_dev", "ops": "opengym"}.get(environment or "")
        if (
            database is None
            or os.environ.get("PLATFORM_DB_MODE") != "local_compose"
            or os.environ.get("PLATFORM_DB_HOST") != "db"
            or os.environ.get("PLATFORM_DB_PORT") != "5432"
            or os.environ.get("PLATFORM_DB_NAME") != database
            or os.environ.get("PLATFORM_DB_TLS") != "disable"
            or "PLATFORM_DB_PASSWORD" in os.environ
        ):
            raise ValueError
        user = {
            "runtime": "opengym_api_runtime",
            "migrator": "opengym_migrator",
            "bootstrap": "opengym_platform_bootstrap",
        }[role]
        password = _secret("PLATFORM_DB_PASSWORD_FILE")
        return DatabaseTarget(
            host="db",
            database=database,
            user=user,
            password=password,
            migrator_password=_secret("PLATFORM_MIGRATOR_PASSWORD_FILE")
            if role == "bootstrap"
            else "",
            runtime_password=_secret("PLATFORM_RUNTIME_PASSWORD_FILE")
            if role == "bootstrap"
            else "",
        )
    except (OSError, ValueError, KeyError, UnicodeError):
        raise ValueError("PLATFORM_DATABASE_CONFIG_INVALID") from None
