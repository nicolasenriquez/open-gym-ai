"""Deployment migration CLI consumes private file references, never inline secrets."""

import json
import os
import subprocess
import sys

import pytest


def test_deployment_rejects_inline_password_without_leaking_it():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "opengym_platform.platform_migrate",
            "--deployment",
            "up",
        ],
        env={
            **os.environ,
            "PLATFORM_ENV": "dev",
            "PLATFORM_DB_PASSWORD": "secret-probe-never-log",
        },
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert json.loads(result.stdout) == {"code": "PLATFORM_DATABASE_CONFIG_INVALID"}


@pytest.mark.parametrize(
    "invalid",
    [
        "environment",
        "host",
        "database",
        "tls",
        "relative",
        "missing",
        "directory",
        "symlink",
        "empty",
        "oversized",
        "nul",
        "multiline",
        "crlf",
        "fifo",
    ],
)
def test_deployment_invalid_file_config_fails_closed(tmp_path, invalid):
    secret = tmp_path / "password"
    secret.write_text("synthetic-database-password-32-bytes-long", encoding="utf-8")
    environment = {
        **os.environ,
        "PLATFORM_ENV": "dev",
        "PLATFORM_DB_MODE": "local_compose",
        "PLATFORM_DB_HOST": "db",
        "PLATFORM_DB_PORT": "5432",
        "PLATFORM_DB_NAME": "opengym_dev",
        "PLATFORM_DB_TLS": "disable",
        "PLATFORM_DB_PASSWORD_FILE": str(secret),
    }
    environment.pop("PLATFORM_DB_PASSWORD", None)
    changes = {
        "environment": {"PLATFORM_ENV": "production"},
        "host": {"PLATFORM_DB_HOST": "external.invalid"},
        "database": {"PLATFORM_DB_NAME": "opengym"},
        "tls": {"PLATFORM_DB_TLS": "auto"},
        "relative": {"PLATFORM_DB_PASSWORD_FILE": "password"},
        "missing": {"PLATFORM_DB_PASSWORD_FILE": str(tmp_path / "missing")},
        "directory": {"PLATFORM_DB_PASSWORD_FILE": str(tmp_path)},
    }
    environment.update(changes.get(invalid, {}))
    if invalid == "symlink":
        link = tmp_path / "link"
        link.symlink_to(secret)
        environment["PLATFORM_DB_PASSWORD_FILE"] = str(link)
    elif invalid == "fifo":
        secret.unlink()
        os.mkfifo(secret)
    elif invalid in {"empty", "oversized", "nul", "multiline", "crlf"}:
        secret.write_text(
            {
                "empty": "",
                "oversized": "x" * 4097,
                "nul": "x" * 32 + "\x00",
                "multiline": "x" * 32 + "\ny",
                "crlf": "x" * 32 + "\r\n",
            }[invalid]
        )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "opengym_platform.platform_migrate",
            "--deployment",
            "up",
        ],
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert json.loads(result.stdout) == {"code": "PLATFORM_DATABASE_CONFIG_INVALID"}
