"""Factory/lifespan/HTTP proofs against the disposable PostgreSQL database."""

import asyncio
import json
import os
import signal
import socket
import sys
from contextlib import asynccontextmanager, nullcontext
from tempfile import TemporaryFile

import asyncpg
import httpx
import pytest
from test_migrations import migrate

from opengym_platform.app import create_app
from opengym_platform.core.database import DatabaseError
from opengym_platform.runner import scan_output

pytest_plugins = ["test_migrations"]

RUNTIME_SETTINGS = {
    "host": "foundation-db",
    "port": 5432,
    "database": "python_foundation_test",
    "user": "python_foundation_runtime",
    "password": "synthetic-python-foundation-runtime-only",
    "tls": False,
    "min_size": 1,
    "max_size": 1,
}


@pytest.mark.asyncio
async def test_missing_schema_is_not_ready_while_process_is_live():
    assert tuple(
        os.environ.get(key)
        for key in (
            "FOUNDATION_DB_HOST",
            "FOUNDATION_DB_PORT",
            "FOUNDATION_DB_NAME",
            "FOUNDATION_DB_USER",
            "FOUNDATION_DB_PASSWORD",
        )
    ) == (
        "foundation-db",
        "5432",
        "python_foundation_test",
        "python_foundation_bootstrap",
        "synthetic-python-foundation-only",
    )
    observer = await asyncpg.connect(
        host="foundation-db",
        port=5432,
        database="python_foundation_test",
        user="python_foundation_bootstrap",
        password="synthetic-python-foundation-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        assert await observer.fetchval("SELECT 1") == 1
        assert (
            await observer.fetchval("SELECT to_regclass('public.alembic_version')")
            is None
        ), "FOUNDATION_HEALTH_FIXTURE_MUST_START_EMPTY"
        app = create_app(
            {
                "host": "foundation-db",
                "port": 5432,
                "database": "python_foundation_test",
                "user": "python_foundation_bootstrap",
                "password": "synthetic-python-foundation-only",
                "tls": False,
                "min_size": 1,
                "max_size": 1,
            }
        )
        # ASGITransport alone does not run startup/shutdown.
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://foundation"
            ) as client,
        ):
            live = await client.get("/health/live")
            ready = await client.get("/health/ready")
            assert live.status_code == 200
            assert ready.status_code == 503, "FOUNDATION_SCHEMA_READINESS_REQUIRED"
    finally:
        await observer.close(timeout=5)


@pytest.mark.asyncio
async def test_runtime_ready_survives_bootstrap_rerun(migration_database):
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    app = create_app(RUNTIME_SETTINGS)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://foundation"
        ) as client,
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"code": "FOUNDATION_READY_OK"}
        assert await migrate("bootstrap") == (
            0,
            {"code": "FOUNDATION_MIGRATION_BOOTSTRAP_OK"},
        )
        response = await client.get("/health/ready")
        assert response.status_code == 200, "FOUNDATION_BOOTSTRAP_PRESERVE_READINESS"
        assert response.json() == {"code": "FOUNDATION_READY_OK"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "incompatible",
    [[], ["synthetic-sensitive-value"], ["0002_health_readiness", "extra"]],
)
async def test_schema_incompatibility_and_recovery(migration_database, incompatible):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    app = create_app(RUNTIME_SETTINGS)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://foundation"
        ) as client,
    ):
        assert (await client.get("/health/ready")).status_code == 200
        # Deliberate corrupt history fixture, never a supported migration action.
        await observer.execute("DELETE FROM public.alembic_version")
        for revision in incompatible:
            await observer.execute(
                "INSERT INTO public.alembic_version VALUES ($1)", revision
            )
        response = await client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"code": "FOUNDATION_SCHEMA_INCOMPATIBLE"}
        assert (await client.get("/health/live")).json() == {
            "code": "FOUNDATION_LIVE_OK"
        }
        assert sorted(
            row["version_num"]
            for row in await observer.fetch(
                "SELECT version_num FROM public.alembic_version"
            )
        ) == sorted(incompatible), "FOUNDATION_HEALTH_MUST_NOT_REPAIR_HISTORY"
        await observer.execute("DELETE FROM public.alembic_version")
        await observer.execute(
            "INSERT INTO public.alembic_version VALUES ('0002_health_readiness')"
        )
        response = await client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"code": "FOUNDATION_READY_OK"}


@pytest.mark.asyncio
async def test_database_access_loss_and_recovery_after_startup(migration_database):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    app = create_app(
        {**RUNTIME_SETTINGS, "connect_timeout": 0.5, "acquire_timeout": 0.5}
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://foundation"
        ) as client,
    ):
        assert (await client.get("/health/ready")).status_code == 200
        try:
            await observer.execute("ALTER ROLE python_foundation_runtime NOLOGIN")
            await observer.execute("""
                SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                WHERE usename = 'python_foundation_runtime'
                  AND datname = current_database()
            """)
            async with asyncio.timeout(3):
                while await observer.fetchval("""
                    SELECT count(*) FROM pg_stat_activity
                    WHERE usename = 'python_foundation_runtime'
                      AND datname = current_database()
                """):
                    await asyncio.sleep(0.02)
            async with asyncio.timeout(2):
                response = await client.get("/health/ready")
            assert response.status_code == 503
            assert response.json() == {"code": "FOUNDATION_DATABASE_UNAVAILABLE"}
            live = await client.get("/health/live")
            assert live.status_code == 200
            assert live.json() == {"code": "FOUNDATION_LIVE_OK"}
        finally:
            await observer.execute("ALTER ROLE python_foundation_runtime LOGIN")
        response = await client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"code": "FOUNDATION_READY_OK"}


@pytest.mark.asyncio
async def test_startup_without_database_access_fails_explicitly(migration_database):
    observer = migration_database
    await observer.execute("ALTER ROLE python_foundation_runtime NOLOGIN")
    try:
        app = create_app({**RUNTIME_SETTINGS, "connect_timeout": 0.5})
        async with asyncio.timeout(2):
            with pytest.raises(DatabaseError, match="^DATABASE_CONNECT_FAILED$"):
                async with app.router.lifespan_context(app):
                    pytest.fail("FOUNDATION_STARTUP_MUST_FAIL", pytrace=False)
        assert (
            await observer.fetchval("SELECT to_regclass('public.alembic_version')")
            is None
        )
    finally:
        await observer.execute("ALTER ROLE python_foundation_runtime LOGIN")


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_body", [False, True])
async def test_factories_own_separate_pools_and_close_on_exit(
    migration_database, fail_body
):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    first = create_app(RUNTIME_SETTINGS)
    second = create_app(RUNTIME_SETTINGS)
    count_sql = """
        SELECT count(*) FROM pg_stat_activity
        WHERE usename = 'python_foundation_runtime' AND datname = current_database()
    """
    async with (
        second.router.lifespan_context(second),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second), base_url="http://foundation"
        ) as client,
    ):
        with (
            pytest.raises(RuntimeError, match="^FOUNDATION_BODY_FAILURE$")
            if fail_body
            else nullcontext()
        ):
            async with first.router.lifespan_context(first):
                assert await observer.fetchval(count_sql) == 2
                if fail_body:
                    raise RuntimeError("FOUNDATION_BODY_FAILURE")
        async with asyncio.timeout(3):
            while await observer.fetchval(count_sql) != 1:
                await asyncio.sleep(0.02)
        assert (await client.get("/health/ready")).status_code == 200
    async with asyncio.timeout(3):
        while await observer.fetchval(count_sql) != 0:
            await asyncio.sleep(0.02)


@asynccontextmanager
async def uvicorn_process(settings):
    with TemporaryFile() as output, TemporaryFile() as diagnostic:
        # Inherit an already-bound private socket, avoiding free-port races.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(16)
            address = listener.getsockname()
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import json, sys, uvicorn; "
                "from opengym_platform.app import create_app; "
                "uvicorn.run(create_app(json.loads(sys.argv[1])), "
                "fd=int(sys.argv[2]), access_log=False, "
                "timeout_graceful_shutdown=1)",
                json.dumps(settings),
                str(listener.fileno()),
                pass_fds=(listener.fileno(),),
                stdout=output,
                stderr=diagnostic,
            )
        try:
            yield process, f"http://127.0.0.1:{address[1]}", diagnostic
        finally:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), timeout=3)
            assert os.fstat(output.fileno()).st_size == 0, (
                "FOUNDATION_UVICORN_UNEXPECTED_STDOUT"
            )
            assert os.fstat(diagnostic.fileno()).st_size <= 16384, (
                "FOUNDATION_UVICORN_OUTPUT_LIMIT"
            )
            diagnostic.seek(0)
            assert (
                scan_output(diagnostic.read(16384).decode("utf-8", errors="replace"))
                is None
            ), "FOUNDATION_UVICORN_UNSAFE_DIAGNOSTICS"


@pytest.mark.asyncio
async def test_uvicorn_sigterm_closes_pool_within_deadline(migration_database, capsys):
    observer = migration_database
    assert await migrate("up") == (0, {"code": "FOUNDATION_MIGRATION_UP_OK"})
    count_sql = """
        SELECT count(*) FROM pg_stat_activity
        WHERE usename = 'python_foundation_runtime' AND datname = current_database()
    """
    async with uvicorn_process({**RUNTIME_SETTINGS, "close_timeout": 1}) as (
        process,
        base_url,
        diagnostic,
    ):
        async with httpx.AsyncClient(
            base_url=base_url, timeout=0.2, trust_env=False
        ) as client:
            async with asyncio.timeout(8):
                while True:
                    assert process.returncode is None, "FOUNDATION_UVICORN_EARLY_EXIT"
                    try:
                        response = await client.get("/health/ready")
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.02)
            assert response.json() == {"code": "FOUNDATION_READY_OK"}
            live = await client.get("/health/live")
            assert live.status_code == 200
            assert live.json() == {"code": "FOUNDATION_LIVE_OK"}
            assert await observer.fetchval(count_sql) == 1
            started = asyncio.get_running_loop().time()
            process.send_signal(signal.SIGTERM)
            async with asyncio.timeout(3):
                await process.wait()
                while await observer.fetchval(count_sql):
                    await asyncio.sleep(0.02)
            elapsed = asyncio.get_running_loop().time() - started
        assert process.returncode in (0, -signal.SIGTERM)
        diagnostic.seek(0)
        logs = diagnostic.read(16384)
        assert b"Application startup complete." in logs
        assert b"Application shutdown complete." in logs
        assert b"ERROR" not in logs
        with capsys.disabled():
            print(
                json.dumps(
                    {
                        "code": "FOUNDATION_UVICORN_STOP_OK",
                        "seconds": round(elapsed, 3),
                        "exit": process.returncode,
                    }
                )
            )


@pytest.mark.asyncio
async def test_uvicorn_startup_refuses_unavailable_database_access(
    migration_database, capsys
):
    observer = migration_database
    await observer.execute("ALTER ROLE python_foundation_runtime NOLOGIN")
    try:
        started = asyncio.get_running_loop().time()
        async with uvicorn_process(
            {**RUNTIME_SETTINGS, "connect_timeout": 0.5, "close_timeout": 1}
        ) as (process, _, diagnostic):
            await asyncio.wait_for(process.wait(), timeout=4)
            elapsed = asyncio.get_running_loop().time() - started
            assert process.returncode == 3, "FOUNDATION_UVICORN_STARTUP_MUST_FAIL"
            diagnostic.seek(0)
            logs = diagnostic.read(16384)
            assert b"DATABASE_CONNECT_FAILED" in logs
            assert b"Application startup failed. Exiting." in logs
            assert b"Application startup complete." not in logs
        assert (
            await observer.fetchval("SELECT to_regclass('public.alembic_version')")
            is None
        )
        assert (
            await observer.fetchval("""
            SELECT count(*) FROM pg_stat_activity
            WHERE usename = 'python_foundation_runtime' AND datname = current_database()
        """)
            == 0
        )
        with capsys.disabled():
            print(
                json.dumps(
                    {
                        "code": "FOUNDATION_UVICORN_STARTUP_REJECTED",
                        "seconds": round(elapsed, 3),
                        "exit": process.returncode,
                    }
                )
            )
    finally:
        await observer.execute("ALTER ROLE python_foundation_runtime LOGIN")
