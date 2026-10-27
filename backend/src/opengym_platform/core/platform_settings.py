"""Explicit local Compose database configuration, separate from Foundation."""

import math
import os
import re
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


def load_session_secret():
    try:
        secret = _secret("PLATFORM_SESSION_SECRET_FILE").strip()
        if len(secret) < 32:
            raise ValueError
        return secret
    except (OSError, ValueError, UnicodeError):
        raise ValueError("PLATFORM_SESSION_CONFIG_INVALID") from None


def load_public_config():
    enabled = {"1", "true", "yes", "on"}
    disabled = {"0", "false", "no", "off"}
    config: dict[str, object] = {
        "invite_only": os.environ.get("INVITE_ONLY", "").lower() in enabled,
        "allow_guest": os.environ.get("ALLOW_GUEST", "").lower() not in disabled,
    }
    if os.environ.get("PASSWORD_LOGIN", "").lower() in enabled:
        config["password_login"] = True
    language = os.environ.get("DEFAULT_LANG", "").strip()
    if re.fullmatch(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?", language):
        config["default_lang"] = language
    if os.environ.get("MEDIA_UPLOADS", "").strip().lower() not in disabled:
        media: dict[str, object] = {"workouts": True}
        for field, variable, default, minimum in (
            ("quotaMB", "MEDIA_QUOTA_MB", 200, 0),
            ("imageMB", "MEDIA_IMAGE_MAX_MB", 2, 0.001),
            ("gifMB", "MEDIA_GIF_MAX_MB", 8, 0.001),
            ("videoMB", "MEDIA_VIDEO_MAX_MB", 40, 0.001),
            ("videoSec", "MEDIA_VIDEO_MAX_SEC", 60, 1),
        ):
            raw = os.environ.get(variable, "").strip()
            value = float(default)
            if re.fullmatch(
                r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw
            ):
                value = float(raw)
            elif re.fullmatch(r"0(?:[xX][0-9a-fA-F]+|[bB][01]+|[oO][0-7]+)", raw):
                try:
                    value = float(int(raw, 0))
                except OverflowError:
                    value = float(default)
            media[field] = (
                value if math.isfinite(value) and value >= minimum else default
            )
        config["media"] = media
    return config
