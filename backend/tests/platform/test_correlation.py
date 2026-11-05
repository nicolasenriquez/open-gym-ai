"""Private HTTP/DB/provider correlation without trusting or exporting trace context."""

import asyncio
import json
import re
import socket
from contextlib import suppress

import pytest
from test_coach_http import REVIEW, completed, configure, provider
from test_identity_session import A
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["ready", "auth", "timeout"])
async def test_http_database_and_async_provider_share_only_internal_context(
    identities, tmp_path, outcome
):
    observer, environment = identities
    path = tmp_path / "log.sock"
    environment["PLATFORM_LOG_SOCKET"] = str(path)
    records = []
    receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    receiver.bind(str(path))
    receiver.setblocking(False)

    async def collect():
        while True:
            raw = await asyncio.get_running_loop().sock_recv(receiver, 8192)
            records.append(json.loads(raw[raw.index(b"{") :].rstrip(b"\0")))
            assert len(records) < 16384

    collector = asyncio.create_task(collect())
    release = asyncio.Event()
    wire = {"choices": [{"message": {"content": json.dumps(REVIEW)}}]}
    try:
        if outcome == "timeout":
            environment["COACH_JOB_TIMEOUT_MS"] = "60000"
        async with provider(
            [(401, {"error": "PRIVATE-ERROR"})] if outcome == "auth" else [(200, wire)],
            release,
        ) as (base, calls):
            await configure(observer, base)
            async with server(environment) as client:
                response = await client.post(
                    "/api/v1/coach/review?PRIVATE-URL=1",
                    json={"note": "PRIVATE-NOTE"},
                    headers={
                        "Authorization": f"Bearer {A}",
                        "X-Request-ID": "f" * 32,
                        "traceparent": "PRIVATE-TRACE",
                        "baggage": "PRIVATE-BAGGAGE",
                    },
                )
                assert response.status_code == 202
                assert "x-request-id" not in response.headers
                # A second request finishes while the original job is still in flight.
                assert (await client.get("/api/v1/health/ready")).status_code == 200
                busy = await client.post(
                    "/api/v1/coach/review",
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
                assert busy.status_code == 409
                if outcome != "timeout":
                    release.set()
                result = await completed(
                    client, timeout=75 if outcome == "timeout" else 8
                )
                release.set()
                assert result["last"]["outcome"] == (
                    "ready" if outcome == "ready" else "failed"
                )
                assert result["last"]["errorClass"] == (
                    None if outcome == "ready" else outcome
                )
                assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
        await asyncio.sleep(0.05)
        assert any(r["operation"] == "/api/v1/coach/review" for r in records), records
        http = next(
            r
            for r in records
            if r["operation"] == "/api/v1/coach/review" and r["result"] == 202
        )
        request_id = http["request_id"]
        assert re.fullmatch(r"[a-f0-9]{32}", request_id) and request_id != "f" * 32
        correlated = [r for r in records if r["request_id"] == request_id]
        assert http["result"] == 202
        assert {"db.acquire", "db.query", "db.transaction", "provider.invoke"} <= {
            r["operation"] for r in correlated
        }
        execution = next(r for r in correlated if r["operation"] == "coach.execution")
        assert execution["result"] == outcome
        external = next(r for r in correlated if r["operation"] == "provider.invoke")
        assert (
            external["result"]
            == {"ready": "ok", "auth": "auth", "timeout": "cancelled"}[outcome]
        )
        assert all(
            r["result"] == "ok" for r in correlated if r["operation"].startswith("db.")
        )
        conflict = next(
            r
            for r in records
            if r["operation"] == "/api/v1/coach/review" and r["result"] == 409
        )
        assert conflict["request_id"] != request_id
        assert all(r["duration_ms"] >= 0 for r in records)
        ready = next(r for r in records if r["operation"] == "/api/v1/health/ready")
        assert ready["request_id"] != request_id
        assert all(
            r["operation"].startswith("db.") or r["operation"] == "/api/v1/health/ready"
            for r in records
            if r["request_id"] == ready["request_id"]
        )
        exported = json.dumps(calls)
        assert request_id not in exported and "PRIVATE-TRACE" not in exported
        assert "x-request-id" not in exported.lower()
        logged = json.dumps(records)
        for sensitive in (
            "PRIVATE-",
            A,
            base,
            "SELECT",
            "Alice",
            "Bob",
            "One extra set",
        ):
            assert sensitive not in logged
    finally:
        release.set()
        collector.cancel()
        with suppress(asyncio.CancelledError):
            await collector
        receiver.close()


@pytest.mark.asyncio
async def test_database_failure_is_correlated_and_recovery_has_new_context(
    identities, tmp_path
):
    observer, environment = identities
    path = tmp_path / "log.sock"
    environment["PLATFORM_LOG_SOCKET"] = str(path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
        receiver.bind(str(path))
        receiver.setblocking(False)
        async with server(environment) as client:
            await observer.execute(
                "REVOKE SELECT ON public.alembic_version FROM opengym_api_runtime"
            )
            response = await client.get("/api/v1/health/ready?PRIVATE-QUERY=1")
            assert response.status_code == 503
            assert response.json() == {"code": "PLATFORM_DATABASE_UNAVAILABLE"}
            await observer.execute(
                "GRANT SELECT ON public.alembic_version TO opengym_api_runtime"
            )
            assert (await client.get("/api/v1/health/ready")).status_code == 200
        records = []
        while True:
            try:
                raw = receiver.recv(8192)
            except BlockingIOError:
                break
            records.append(json.loads(raw[raw.index(b"{") :].rstrip(b"\0")))
    failed = next(r for r in records if r["result"] == 503)
    recovered = next(
        r
        for r in records
        if r["result"] == 200 and r["operation"] == "/api/v1/health/ready"
    )
    assert failed["request_id"] != recovered["request_id"]
    assert any(
        r["request_id"] == failed["request_id"]
        and r["operation"] == "db.query"
        and r["result"] == "failed"
        for r in records
    )
    assert all(r["duration_ms"] >= 0 for r in records)
    for sensitive in (
        "PRIVATE-",
        "permission",
        "SELECT",
        "alembic_version",
        "opengym_api_runtime",
    ):
        assert sensitive not in json.dumps(records)
