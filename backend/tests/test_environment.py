"""Toolchain/package and disposable DB smoke, not pool/health/role proof."""

import importlib.metadata
import json
import os
import platform
import re
import sys
import sysconfig
from pathlib import Path

import asyncpg
import pytest


def test_pinned_toolchain_and_package() -> None:
    importlib.import_module("fastapi")
    importlib.import_module("opengym_platform")
    assert platform.python_implementation() == "CPython"
    assert sys.version_info[:3] == (3, 14, 9)
    assert not sysconfig.get_config_var("Py_GIL_DISABLED")
    inventory = json.loads(Path("dependency-licenses.json").read_text())
    expected = {
        item["name"]: item["version"]
        for item in inventory
        if item["installedLinuxAmd64"]
    }
    observed = {
        re.sub(
            r"[-_.]+", "-", distribution.metadata["Name"]
        ).lower(): distribution.version
        for distribution in importlib.metadata.distributions()
    }
    assert observed == expected


@pytest.mark.asyncio
async def test_disposable_database() -> None:
    # No arbitrary DSN, libpq service or real destination can enter this probe.
    assert (
        os.environ.get("FOUNDATION_DB_HOST"),
        os.environ.get("FOUNDATION_DB_PORT"),
        os.environ.get("FOUNDATION_DB_NAME"),
        os.environ.get("FOUNDATION_DB_USER"),
        os.environ.get("FOUNDATION_DB_PASSWORD"),
    ) == (
        "foundation-db",
        "5432",
        "python_foundation_test",
        "python_foundation_bootstrap",
        "synthetic-python-foundation-only",
    )
    connection = None
    try:
        connection = await asyncpg.connect(
            host="foundation-db",
            port=5432,
            database="python_foundation_test",
            user="python_foundation_bootstrap",
            password="synthetic-python-foundation-only",
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        assert await connection.fetchval("SELECT 1") == 1
        assert await connection.fetchval("SHOW server_version_num") == "180006"
    except asyncpg.PostgresError, asyncpg.InterfaceError, OSError:
        pytest.fail("FOUNDATION_DATABASE_PROBE_FAILED", pytrace=False)
    finally:
        if connection is not None:
            try:
                await connection.close(timeout=5)
            except asyncpg.PostgresError, asyncpg.InterfaceError, OSError:
                connection.terminate()
                pytest.fail("FOUNDATION_DATABASE_CLOSE_FAILED", pytrace=False)
