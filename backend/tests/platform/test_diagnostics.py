"""Private diagnostic failures must be bounded and never disclose configuration."""

import asyncio
import json
import socket
import time

import pytest
from test_identity_session import B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server

from opengym_platform.operations import diagnose


def test_missing_socket_is_degraded_without_private_configuration(tmp_path):
    config = tmp_path / "operator.json"
    config.write_text(
        json.dumps({"diagnostic_socket": "/tmp/private-not-present.sock"})
    )
    code, result = diagnose(config)
    assert code == 1
    assert result == {"code": "DIAGNOSTIC_UNAVAILABLE"}


def test_arbitrary_configuration_is_refused(tmp_path):
    config = tmp_path / "operator.json"
    config.write_text(
        json.dumps({"diagnostic_socket": "/tmp/a", "password": "private-marker"})
    )
    assert diagnose(config) == (2, {"code": "DIAGNOSTIC_CONFIG_INVALID"})


def test_invalid_json_configuration_returns_usage_error(tmp_path):
    config = tmp_path / "operator.json"
    config.write_text("private-invalid-marker")
    assert diagnose(config) == (2, {"code": "DIAGNOSTIC_CONFIG_INVALID"})


@pytest.mark.asyncio
async def test_live_private_diagnose_does_not_claim_missing_backup_is_healthy(
    identities, tmp_path
):
    _, environment = identities
    path = tmp_path / "diag.sock"
    environment["PLATFORM_DIAGNOSTIC_SOCKET"] = str(path)
    config = tmp_path / "operator.json"
    config.write_text(json.dumps({"diagnostic_socket": str(path)}))
    async with server(environment) as client:
        assert (await client.get("/api/v1/health/ready")).status_code == 200
        code, result = await asyncio.to_thread(diagnose, config)
        assert code == 1
        assert result["database"] == "writable"
        assert result["schema"] == "current"
        assert result["backup"] == {"state": "missing", "verified": False}
        assert result["audit_degraded"] is False
        assert path.stat().st_mode & 0o777 == 0o600
        assert (await client.get("/api/v1/diagnose")).status_code == 404
    assert not path.exists()


@pytest.mark.asyncio
async def test_http_and_diagnose_with_over_quota_log_directory(identities, tmp_path):
    _, environment = identities
    logs = tmp_path / "logs"
    logs.mkdir()
    with (logs / "api.log").open("wb") as stream:
        stream.truncate(256 * 1024 * 1024 + 1)
    environment["PLATFORM_LOG_DIRECTORY"] = str(logs)
    environment["PLATFORM_DIAGNOSTIC_SOCKET"] = str(tmp_path / "diag.sock")
    config = tmp_path / "operator.json"
    config.write_text(
        json.dumps({"diagnostic_socket": environment["PLATFORM_DIAGNOSTIC_SOCKET"]})
    )
    async with server(environment) as client:
        assert (await client.get("/api/v1/health/ready")).status_code == 200
        code, result = await asyncio.to_thread(diagnose, config)
        assert code == 1 and result["logging"]["sink"] == "full"
        assert result["logging"]["degraded"]
        (logs / "api.log").unlink()
        (logs / "foreign-file").write_text("private-marker")
        code, result = await asyncio.to_thread(diagnose, config)
        assert code == 1 and result["logging"]["sink"] == "unavailable"
        assert "private-marker" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("sink", ["missing", "full", "receiving"])
async def test_http_commit_survives_logging_sink_failure(identities, tmp_path, sink):
    observer, environment = identities
    path = tmp_path / "log.sock"
    environment["PLATFORM_LOG_SOCKET"] = str(path)
    environment["PLATFORM_DIAGNOSTIC_SOCKET"] = str(tmp_path / "diag.sock")
    config = tmp_path / "operator.json"
    config.write_text(
        json.dumps({"diagnostic_socket": environment["PLATFORM_DIAGNOSTIC_SOCKET"]})
    )
    receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        if sink != "missing":
            receiver.bind(str(path))
            receiver.setblocking(False)
        async with server(environment) as client:
            start = time.monotonic()
            for _ in range(20 if sink == "full" else 1):
                assert (
                    await client.get("/api/v1/health/live?private-url-marker=1")
                ).status_code == 200
            response = await client.post(
                "/api/v1/admin/invites/new",
                headers={"Authorization": f"Bearer {B}"},
                json={"note": "private-note-marker"},
            )
            assert response.status_code == 200
            assert time.monotonic() - start < 4
            assert (
                await observer.fetchval("SELECT count(*) FROM identity.invitations")
                == 1
            )
            _, result = await asyncio.to_thread(diagnose, config)
            assert result["pool"]["size"] <= result["pool"]["maximum"]
            if sink != "receiving":
                assert result["logging"]["degraded"]
                assert result["logging"]["failures"] > 0
            else:
                data = receiver.recv(8192).decode()
                assert "opengym-api" in data
                assert "private-" not in data and B not in data
    finally:
        receiver.close()
