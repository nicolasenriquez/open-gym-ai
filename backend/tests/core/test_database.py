"""First Database RED: real writes must roll back together, not autocommit."""

import os
from contextlib import AsyncExitStack

import asyncpg
import pytest
import pytest_asyncio

from opengym_platform.core.database import Database


@pytest_asyncio.fixture
async def database_fixture():
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
    async with AsyncExitStack() as cleanup:
        bootstrap = await asyncpg.connect(
            host="foundation-db",
            port=5432,
            database="python_foundation_test",
            user="python_foundation_bootstrap",
            password="synthetic-python-foundation-only",
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        cleanup.push_async_callback(bootstrap.close, timeout=5)
        async with bootstrap.transaction():
            await bootstrap.execute("""
                CREATE ROLE python_foundation_pool_runtime LOGIN
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS
                    PASSWORD 'synthetic-python-foundation-pool-only';
                CREATE SCHEMA pool_fixture;
                CREATE TABLE pool_fixture.rollback_probe (id integer PRIMARY KEY);
                REVOKE ALL ON SCHEMA pool_fixture FROM PUBLIC;
                GRANT USAGE ON SCHEMA pool_fixture TO python_foundation_pool_runtime;
                GRANT SELECT, INSERT ON pool_fixture.rollback_probe
                    TO python_foundation_pool_runtime;
            """)
        cleanup.push_async_callback(
            bootstrap.execute,
            "DROP SCHEMA pool_fixture CASCADE; DROP ROLE python_foundation_pool_runtime;",
        )
        observer = await asyncpg.connect(
            host="foundation-db",
            port=5432,
            database="python_foundation_test",
            user="python_foundation_pool_runtime",
            password="synthetic-python-foundation-pool-only",
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        cleanup.push_async_callback(observer.close, timeout=5)
        database = await Database.open({"max_size": 1})
        cleanup.push_async_callback(database.close)
        yield database, observer


class CollaboratorFailure(Exception):
    pass


async def first_collaborator(handle):
    await handle.execute("INSERT INTO pool_fixture.rollback_probe VALUES ($1)", 1)


async def second_collaborator(handle):
    await handle.execute("INSERT INTO pool_fixture.rollback_probe VALUES ($1)", 2)
    raise CollaboratorFailure("FOUNDATION_EXPECTED_COLLABORATOR_FAILURE")


@pytest.mark.asyncio
async def test_failed_collaboration_rolls_back_before_same_connection_is_reused(
    database_fixture,
):
    database, observer = database_fixture
    initial = await observer.fetchval(
        "SELECT count(*) FROM pool_fixture.rollback_probe"
    )
    assert initial == 0, "FOUNDATION_FIXTURE_MUST_START_EMPTY"
    with pytest.raises(CollaboratorFailure):
        async with database.transaction(owner_id="owner-a") as handle:
            before = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
            await first_collaborator(handle)
            await second_collaborator(handle)

    after = (await database.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
    assert after == before, "FOUNDATION_MAX_ONE_MUST_REUSE_CONNECTION"
    observed = await observer.fetchval(
        "SELECT count(*) FROM pool_fixture.rollback_probe"
    )
    assert observed == 0, "DATABASE_ROLLBACK_REQUIRED"
