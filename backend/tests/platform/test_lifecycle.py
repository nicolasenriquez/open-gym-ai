"""Real platform HTTP and restricted PostgreSQL lifecycle on disposable targets."""

import asyncio
import json
import os
import signal
import socket
import sys
from contextlib import asynccontextmanager
from tempfile import TemporaryFile

import asyncpg
import httpx
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def deployment(tmp_path):
    assert os.environ["PLATFORM_DB_NAME"] == "opengym_platform_test"
    observer = await asyncpg.connect(
        host="platform-db",
        database="opengym_platform_test",
        user="opengym_platform_bootstrap",
        password="synthetic-opengym-platform-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    await observer.execute(
        "ALTER ROLE opengym_platform_bootstrap PASSWORD 'synthetic-lifecycle-bootstrap-password-only'"
    )
    await observer.execute("CREATE DATABASE opengym_dev")
    environment = {
        **os.environ,
        "PLATFORM_ENV": "dev",
        "PLATFORM_DB_MODE": "local_compose",
        "PLATFORM_DB_HOST": "db",
        "PLATFORM_DB_NAME": "opengym_dev",
        "PLATFORM_DB_TLS": "disable",
        "MEDIA_UPLOADS": "0",
    }
    environment.pop("PLATFORM_DB_PASSWORD", None)
    for name, variable in (
        ("bootstrap", "PLATFORM_DB_PASSWORD_FILE"),
        ("migrator", "PLATFORM_MIGRATOR_PASSWORD_FILE"),
        ("runtime", "PLATFORM_RUNTIME_PASSWORD_FILE"),
    ):
        secret = tmp_path / name
        secret.write_text(f"synthetic-lifecycle-{name}-password-only")
        environment[variable] = str(secret)
    session_secret = tmp_path / "session_secret"
    session_secret.write_text("synthetic-session-signing-key-only-0123456789")
    environment["PLATFORM_SESSION_SECRET_FILE"] = str(session_secret)
    database = await asyncpg.connect(
        host="platform-db",
        database="opengym_dev",
        user="opengym_platform_bootstrap",
        password="synthetic-lifecycle-bootstrap-password-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        await migration(environment, "bootstrap")
        yield database, environment
    finally:
        await database.close(timeout=5)
        await observer.execute("DROP DATABASE opengym_dev WITH (FORCE)")
        await observer.execute(
            "DROP ROLE IF EXISTS opengym_migrator, opengym_api_runtime, "
            "opengym_schema_owner, opengym_identity_executor"
        )
        await observer.execute(
            "ALTER ROLE opengym_platform_bootstrap PASSWORD 'synthetic-opengym-platform-only'"
        )
        await observer.close(timeout=5)


async def migration(environment, action):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.platform_migrate",
        "--deployment",
        action,
        env={
            **environment,
            "PLATFORM_DB_PASSWORD_FILE": environment[
                "PLATFORM_DB_PASSWORD_FILE"
                if action == "bootstrap"
                else "PLATFORM_MIGRATOR_PASSWORD_FILE"
            ],
        },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, diagnostic = await asyncio.wait_for(process.communicate(), 35)
    assert process.returncode == 0 and diagnostic == b""
    assert json.loads(output) == {"code": f"PLATFORM_MIGRATION_{action.upper()}_OK"}


@asynccontextmanager
async def server(environment, *, factory="opengym_platform.application:create_app"):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    runtime = {
        **environment,
        "PLATFORM_DB_PASSWORD_FILE": environment["PLATFORM_RUNTIME_PASSWORD_FILE"],
    }
    runtime.pop("PLATFORM_MIGRATOR_PASSWORD_FILE", None)
    runtime.pop("PLATFORM_RUNTIME_PASSWORD_FILE", None)
    with TemporaryFile() as output:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            factory,
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
            "--no-proxy-headers",
            env=runtime,
            stdout=output,
            stderr=output,
        )
        try:
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{port}", timeout=2
            ) as client:
                async with asyncio.timeout(10):
                    while True:
                        assert process.returncode is None, (
                            "PLATFORM_HTTP_STARTUP_FAILED"
                        )
                        try:
                            await client.get("/api/v1/health/live")
                            break
                        except httpx.TransportError:
                            await asyncio.sleep(0.05)
                yield client
        finally:
            if process.returncode is None:
                process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), 15)
            except TimeoutError:
                process.kill()
                await process.wait()
                pytest.fail("PLATFORM_HTTP_SHUTDOWN_TIMEOUT")
            output.seek(0)
            diagnostic = output.read().decode()
            assert process.returncode in (0, -signal.SIGTERM)
            assert "Application shutdown complete." in diagnostic
            assert "synthetic-" not in diagnostic, "PLATFORM_HTTP_SECRET_LEAK"


@pytest.mark.asyncio
async def test_missing_schema_is_live_but_never_ready_or_migrated(deployment):
    observer, environment = deployment
    async with server(environment) as client:
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json() == {"code": "PLATFORM_LIVE_OK"}
        assert (await client.get("/api/v1/health/ready")).status_code == 503
        assert (
            await observer.fetchval("SELECT to_regclass('public.alembic_version')")
            is None
        )


@pytest.mark.asyncio
async def test_public_health_and_config_match_empty_node_instance(deployment):
    observer, environment = deployment
    await migration(environment, "up")
    async with server(environment) as client:
        assert (await client.get("/api/v1/health/ready")).json() == {
            "code": "PLATFORM_READY_OK"
        }
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "users": 0, "writable": True}
        assert response.headers["cache-control"] == "no-store"
        config = await client.get("/api/v1/config")
        assert config.status_code == 200
        assert config.json() == {"invite_only": False, "allow_guest": True}
        assert config.headers["cache-control"] == "no-store"
        assert (
            await observer.fetchval("SELECT version_num FROM public.alembic_version")
            == "p002_training_write"
        )


@pytest.mark.asyncio
async def test_public_config_preserves_flags_media_and_never_trusts_forged_session(
    deployment,
):
    _, environment = deployment
    environment.update(
        {
            "INVITE_ONLY": "YeS",
            "ALLOW_GUEST": "OFF",
            "PASSWORD_LOGIN": "on",
            "DEFAULT_LANG": " pt-BR ",
            "MEDIA_UPLOADS": "on",
            "MEDIA_QUOTA_MB": "0",
            "MEDIA_IMAGE_MAX_MB": "0.5",
            "MEDIA_GIF_MAX_MB": "bad",
            "MEDIA_VIDEO_MAX_MB": "0x20",
            "MEDIA_VIDEO_MAX_SEC": "0",
        }
    )
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/config",
            headers={
                "Cookie": "gymsid=forged-session",
                "Authorization": "Bearer forged-token",
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "invite_only": True,
            "allow_guest": False,
            "password_login": True,
            "default_lang": "pt-BR",
            "media": {
                "quotaMB": 0,
                "imageMB": 0.5,
                "gifMB": 8,
                "videoMB": 32,
                "videoSec": 60,
                "workouts": True,
            },
        }


@pytest.mark.asyncio
async def test_read_only_database_cannot_advertise_writable_or_ready(deployment):
    observer, environment = deployment
    await migration(environment, "up")
    await observer.execute(
        "ALTER ROLE opengym_api_runtime SET default_transaction_read_only = on"
    )
    try:
        async with server(environment) as client:
            health = await client.get("/api/v1/health")
            assert health.status_code == 503
            assert health.json() == {"ok": False, "writable": False}
            assert (await client.get("/api/v1/health/ready")).status_code == 503
            assert (await client.get("/api/v1/health/live")).status_code == 200
    finally:
        await observer.execute(
            "ALTER ROLE opengym_api_runtime RESET default_transaction_read_only"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "history",
    [
        [],
        ["unknown"],
        ["p001_password_login"],
        ["p002_training"],
        ["p002_training_write", "extra"],
    ],
)
async def test_unknown_history_is_not_ready_and_is_never_repaired(deployment, history):
    observer, environment = deployment
    await migration(environment, "up")
    await observer.execute("DELETE FROM public.alembic_version")
    for revision in history:
        await observer.execute(
            "INSERT INTO public.alembic_version VALUES ($1)", revision
        )
    async with server(environment) as client:
        for _ in range(2):
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 503
            assert response.json() == {"code": "PLATFORM_SCHEMA_INCOMPATIBLE"}
            assert (await client.get("/api/v1/health")).json() == {
                "ok": False,
                "writable": False,
            }
        assert [
            row[0]
            for row in await observer.fetch(
                "SELECT version_num FROM public.alembic_version ORDER BY 1"
            )
        ] == sorted(history)
        assert (await client.get("/api/v1/health/live")).status_code == 200
        await observer.execute("DELETE FROM public.alembic_version")
        await observer.execute(
            "INSERT INTO public.alembic_version VALUES ('p002_training_write')"
        )
        assert (await client.get("/api/v1/health/ready")).status_code == 200


@pytest.mark.asyncio
async def test_database_loss_recovers_without_restart_and_shutdown_closes_pool(
    deployment,
):
    observer, environment = deployment
    await migration(environment, "up")
    async with server(environment) as client:
        assert (await client.get("/api/v1/health/ready")).status_code == 200
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE usename = 'opengym_api_runtime'"
            )
            >= 1
        )
        await observer.execute("ALTER ROLE opengym_api_runtime NOLOGIN")
        try:
            await observer.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'opengym_api_runtime'"
            )
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 503
            assert response.json() == {"code": "PLATFORM_DATABASE_UNAVAILABLE"}
            assert (await client.get("/api/v1/health")).json() == {
                "ok": False,
                "writable": False,
            }
            assert (await client.get("/api/v1/health/live")).status_code == 200
        finally:
            await observer.execute("ALTER ROLE opengym_api_runtime LOGIN")
        assert (await client.get("/api/v1/health/ready")).status_code == 200
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE usename = 'opengym_api_runtime'"
        )
        == 0
    )


@pytest.mark.asyncio
async def test_public_http_headers_and_unknown_routes_keep_node_contract(deployment):
    _, environment = deployment
    async with server(environment) as client:
        config = await client.get(
            "/api/v1/config", headers={"Origin": "capacitor://localhost"}
        )
        assert config.headers["content-type"] == "application/json"
        assert config.headers["access-control-allow-origin"] == "capacitor://localhost"
        assert config.headers["vary"] == "Origin"
        assert "access-control-allow-credentials" not in config.headers
        preflight = await client.options(
            "/api/v1/config",
            headers={
                "Origin": "capacitor://localhost",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        assert preflight.status_code == 204
        assert preflight.headers["access-control-allow-private-network"] == "true"
        assert (
            preflight.headers["access-control-allow-methods"]
            == "GET,POST,PUT,DELETE,OPTIONS"
        )
        assert (
            "access-control-allow-private-network"
            not in (
                await client.options(
                    "/api/v1/config",
                    headers={
                        "Origin": "https://foreign.invalid",
                        "Access-Control-Request-Private-Network": "true",
                    },
                )
            ).headers
        )
        for method, path in [
            ("POST", "/api/v1/health"),
            ("GET", "/api/v1/health/"),
            ("GET", "/docs"),
            ("GET", "/openapi.json"),
        ]:
            response = await client.request(method, path)
            assert response.status_code == 404
            assert response.json() == {"error": "not found"}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["inline", "missing", "tls", "login"])
async def test_runtime_startup_rejects_unsafe_config_or_database_access(
    deployment, failure
):
    observer, environment = deployment
    environment = {
        **environment,
        "PLATFORM_DB_PASSWORD_FILE": environment["PLATFORM_RUNTIME_PASSWORD_FILE"],
    }
    if failure == "inline":
        environment["PLATFORM_DB_PASSWORD"] = "synthetic-inline-never-log"
    elif failure == "missing":
        environment["PLATFORM_DB_PASSWORD_FILE"] += "-missing"
    elif failure == "tls":
        environment["PLATFORM_DB_TLS"] = "auto"
    else:
        await observer.execute("ALTER ROLE opengym_api_runtime NOLOGIN")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            "opengym_platform.application:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--no-access-log",
            "--no-proxy-headers",
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            output, diagnostic = await asyncio.wait_for(process.communicate(), 10)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        assert process.returncode != 0
        captured = (output + diagnostic).decode()
        expected = (
            "DATABASE_CONNECT_FAILED"
            if failure == "login"
            else "PLATFORM_DATABASE_CONFIG_INVALID"
        )
        assert expected in captured
        assert "synthetic-" not in captured
        assert environment["PLATFORM_DB_PASSWORD_FILE"] not in captured
        assert (
            await observer.fetchval("SELECT to_regclass('public.alembic_version')")
            is None
        )
    finally:
        await observer.execute("ALTER ROLE opengym_api_runtime LOGIN")


@pytest.mark.asyncio
async def test_invalid_public_settings_use_node_defaults_without_echoing_values(
    deployment,
):
    _, environment = deployment
    environment.update(
        {
            "MEDIA_UPLOADS": "",
            "DEFAULT_LANG": "not-a-language-secret",
            "PASSWORD_LOGIN": " true ",
            "MEDIA_IMAGE_MAX_MB": "1_0",
            "MEDIA_QUOTA_MB": "-1",
            "MEDIA_VIDEO_MAX_SEC": "1e400",
            "MEDIA_GIF_MAX_MB": " ",
            "MEDIA_VIDEO_MAX_MB": "0.0001",
        }
    )
    async with server(environment) as client:
        response = await client.get("/api/v1/config")
        assert response.json() == {
            "invite_only": False,
            "allow_guest": True,
            "media": {
                "quotaMB": 200,
                "imageMB": 2,
                "gifMB": 8,
                "videoMB": 40,
                "videoSec": 60,
                "workouts": True,
            },
        }


@pytest.mark.asyncio
async def test_unversioned_routes_are_removed(deployment):
    _, environment = deployment
    async with server(environment) as client:
        for method, path in [
            ("GET", "/api/health"),
            ("GET", "/api/config"),
            ("GET", "/api/me"),
            ("POST", "/api/login/password"),
            ("GET", "/api/data"),
            ("PUT", "/api/data"),
            ("GET", "/api/data/rev"),
            ("GET", "/health/live"),
            ("GET", "/health/ready"),
            ("OPTIONS", "/api/config"),
            ("GET", "/api/v2/config"),
        ]:
            response = await client.request(method, path)
            assert response.status_code == 404, (method, path)
            assert response.json() == {"error": "not found"}
