"""Database lifecycle and transaction proofs against disposable PostgreSQL."""

import asyncio
import os
from contextlib import AsyncExitStack

import asyncpg
import pytest
import pytest_asyncio
from _commit_relay import commit_relay

from opengym_platform.core.database import Database, DatabaseError

SETTINGS = {
    "host": "foundation-db",
    "port": 5432,
    "database": "python_foundation_test",
    "user": "python_foundation_pool_runtime",
    "password": "synthetic-python-foundation-pool-only",
    "tls": False,
    "max_size": 1,
}


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
                CREATE TABLE pool_fixture.deferred_probe (
                    id integer UNIQUE DEFERRABLE INITIALLY DEFERRED
                );
                REVOKE ALL ON SCHEMA pool_fixture FROM PUBLIC;
                GRANT USAGE ON SCHEMA pool_fixture TO python_foundation_pool_runtime;
                GRANT SELECT, INSERT ON pool_fixture.rollback_probe, pool_fixture.deferred_probe
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
        database = await Database.open(SETTINGS)
        cleanup.push_async_callback(database.close)
        yield database, observer


class CollaboratorFailure(Exception):
    pass


async def first_collaborator(handle):
    await handle.execute("INSERT INTO pool_fixture.rollback_probe VALUES ($1)", 1)


async def second_collaborator(handle):
    await handle.execute("INSERT INTO pool_fixture.rollback_probe VALUES ($1)", 2)
    raise CollaboratorFailure("FOUNDATION_EXPECTED_COLLABORATOR_FAILURE")


async def successful_second_collaborator(handle):
    await handle.execute("INSERT INTO pool_fixture.rollback_probe VALUES ($1)", 2)


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


@pytest.mark.asyncio
async def test_owner_context_is_local_and_does_not_leak_to_next_borrower(
    database_fixture,
):
    database, _ = database_fixture
    sql = "SELECT nullif(current_setting('app.owner_id', true), '') AS owner"
    for owner in ("owner-a", "owner-b", None):
        async with database.transaction(owner_id=owner) as handle:
            assert (await handle.fetch(sql))[0]["owner"] == owner, (
                "DATABASE_OWNER_REQUIRED"
            )
        assert (await database.fetch(sql))[0]["owner"] is None


@pytest.mark.asyncio
async def test_caught_sql_failure_cannot_report_success(database_fixture):
    database, observer = database_fixture
    with pytest.raises(RuntimeError, match="DATABASE_TRANSACTION_ABORTED"):
        async with database.transaction(owner_id="owner-a") as handle:
            await first_collaborator(handle)
            with pytest.raises(DatabaseError):
                await first_collaborator(handle)
            with pytest.raises(RuntimeError, match="DATABASE_TRANSACTION_ABORTED"):
                await handle.fetch("SELECT 1")
    assert (
        await observer.fetchval("SELECT count(*) FROM pool_fixture.rollback_probe") == 0
    )
    async with database.transaction() as handle:
        assert (
            await handle.fetch(
                "SELECT nullif(current_setting('app.owner_id', true), '') AS owner"
            )
        )[0]["owner"] is None


@pytest.mark.asyncio
async def test_expired_handle_cannot_change_next_borrowers_context(database_fixture):
    database, _ = database_fixture
    async with database.transaction() as previous:
        await previous.fetch("SELECT 1")
    async with database.transaction(owner_id="owner-b") as current:
        with pytest.raises(RuntimeError, match="DATABASE_HANDLE_EXPIRED"):
            await previous.execute("SELECT set_config('app.owner_id', 'stale', false)")
        assert (await current.fetch("SELECT current_setting('app.owner_id') AS owner"))[
            0
        ]["owner"] == "owner-b"


@pytest.mark.asyncio
async def test_sql_failure_exposes_only_safe_code_without_driver_chain(
    database_fixture,
):
    database, _ = database_fixture
    with pytest.raises(RuntimeError, match="DATABASE_TRANSACTION_ABORTED"):
        async with database.transaction() as handle:
            with pytest.raises(DatabaseError) as failure:
                await handle.fetch(
                    "SELECT CAST($1::text AS integer)", "synthetic-sensitive-value"
                )
            error = failure.value
            assert str(error) == "DATABASE_QUERY_FAILED", "DATABASE_SAFE_ERROR_REQUIRED"
            assert error.code == "DATABASE_QUERY_FAILED"
            assert error.__cause__ is None and error.__context__ is None


@pytest.mark.asyncio
async def test_explicit_connection_settings_are_supported(database_fixture):
    other = None
    try:
        other = await Database.open(SETTINGS)
    except ValueError:
        pass
    try:
        assert other is not None, "DATABASE_EXPLICIT_SETTINGS_REQUIRED"
        assert (await other.fetch("SELECT 1 AS value"))[0]["value"] == 1
    finally:
        if other is not None:
            await other.close()


@pytest.mark.asyncio
async def test_private_loopback_relay_accepts_synthetic_connection_only(
    database_fixture,
):
    async with commit_relay() as relay:
        other = None
        try:
            other = await Database.open(
                {**SETTINGS, "host": "127.0.0.1", "port": relay.port}
            )
        except ValueError:
            pass
        try:
            assert other is not None, "DATABASE_SYNTHETIC_RELAY_REQUIRED"
            assert (await other.fetch("SELECT 1 AS value"))[0]["value"] == 1
        finally:
            if other is not None:
                await other.close()


@pytest.mark.asyncio
async def test_saturation_returns_safe_bounded_failure_without_poisoning_owner(
    database_fixture,
):
    other = await Database.open({**SETTINGS, "acquire_timeout": 0.05})
    try:
        async with other.transaction(owner_id="owner-a") as handle:
            with pytest.raises(RuntimeError, match="DATABASE_ACQUIRE_TIMEOUT"):
                await other.fetch("SELECT 1")
            assert (
                await handle.fetch("SELECT current_setting('app.owner_id') AS owner")
            )[0]["owner"] == "owner-a"
        assert (await other.fetch("SELECT 1 AS value"))[0]["value"] == 1
    finally:
        await other.close()


@pytest.mark.asyncio
async def test_close_drains_active_transaction_but_refuses_new_work(database_fixture):
    other = await Database.open(SETTINGS)
    entered, release, closing, closing_again = (asyncio.Event() for _ in range(4))

    async def work():
        async with other.transaction() as handle:
            entered.set()
            await release.wait()
            assert (await handle.fetch("SELECT 1 AS value"))[0]["value"] == 1

    async def stop(event):
        event.set()
        await other.close()

    worker = asyncio.create_task(work())
    stopper = second_stopper = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        stopper = asyncio.create_task(stop(closing))
        await asyncio.wait_for(closing.wait(), 5)
        with pytest.raises(RuntimeError, match="DATABASE_CLOSED"):
            await other.fetch("SELECT 1")
        assert not stopper.done(), "DATABASE_MUST_DRAIN_ACTIVE_WORK"
        second_stopper = asyncio.create_task(stop(closing_again))
        await asyncio.wait_for(closing_again.wait(), 5)
        assert not second_stopper.done(), "DATABASE_CONCURRENT_CLOSE_MUST_WAIT"
        release.set()
        await asyncio.wait_for(asyncio.gather(worker, stopper, second_stopper), 5)
    finally:
        release.set()
        await asyncio.gather(
            worker,
            *(task for task in (stopper, second_stopper) if task),
            return_exceptions=True,
        )
        await other.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_commit_lost_after_visible_write_is_unknown_and_not_retried(
    database_fixture, cancel
):
    _, observer = database_fixture
    async with commit_relay() as relay:
        other = await Database.open(
            {**SETTINGS, "host": "127.0.0.1", "port": relay.port}
        )
        first_pid = None

        async def write():
            nonlocal first_pid
            async with other.transaction(owner_id="owner-a") as handle:
                first_pid = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0][
                    "pid"
                ]
                await first_collaborator(handle)

        task = asyncio.create_task(write())
        try:
            await asyncio.wait_for(relay.held.wait(), 5)
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM pool_fixture.rollback_probe"
                )
                == 1
            )
            if cancel:
                task.cancel()
            else:
                relay.release.set()
            with pytest.raises(
                asyncio.CancelledError if cancel else RuntimeError
            ) as failure:
                await asyncio.wait_for(task, 5)
            if not cancel:
                assert str(failure.value) == "DATABASE_COMMIT_OUTCOME_UNKNOWN"
            assert getattr(failure.value, "commit_outcome", None) == "unknown"
            assert failure.value.__cause__ is None and failure.value.__context__ is None
            assert relay.commits == 1
            async with other.transaction() as handle:
                row = (
                    await handle.fetch(
                        "SELECT pg_backend_pid() AS pid, nullif(current_setting('app.owner_id', true), '') AS owner"
                    )
                )[0]
                assert row["pid"] != first_pid and row["owner"] is None
        finally:
            relay.release.set()
            await asyncio.gather(task, return_exceptions=True)
            await other.close()


@pytest.mark.asyncio
async def test_successful_collaborators_commit_together(database_fixture):
    database, observer = database_fixture
    async with database.transaction(owner_id="owner-a") as handle:
        await first_collaborator(handle)
        await successful_second_collaborator(handle)
    assert [
        row["id"]
        for row in await observer.fetch(
            "SELECT id FROM pool_fixture.rollback_probe ORDER BY id"
        )
    ] == [1, 2]
    for method in (handle.execute, handle.fetch):
        with pytest.raises(RuntimeError, match="DATABASE_HANDLE_EXPIRED"):
            await method("SELECT 1")
    assert (
        await database.fetch(
            "SELECT nullif(current_setting('app.owner_id', true), '') AS owner"
        )
    )[0]["owner"] is None
    assert await database.execute("SELECT 1") == "SELECT 1"


@pytest.mark.asyncio
async def test_cancellation_before_commit_rolls_back_and_next_owner_is_clean(
    database_fixture,
):
    database, observer = database_fixture
    entered = asyncio.Event()
    pid = None

    async def work():
        nonlocal pid
        async with database.transaction(owner_id="owner-a") as handle:
            pid = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
            await first_collaborator(handle)
            entered.set()
            await handle.fetch("SELECT pg_sleep(10)")

    task = asyncio.create_task(work())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        async with asyncio.timeout(5):
            while not await observer.fetchval(
                "SELECT EXISTS (SELECT FROM pg_stat_activity WHERE pid = $1 AND wait_event = 'PgSleep')",
                pid,
            ):
                pass
        task.cancel("synthetic-before-commit")
        with pytest.raises(asyncio.CancelledError) as failure:
            await asyncio.wait_for(task, 5)
        assert getattr(failure.value, "commit_outcome", None) is None
        assert (
            await observer.fetchval("SELECT count(*) FROM pool_fixture.rollback_probe")
            == 0
        )
        async with database.transaction(owner_id="owner-b") as handle:
            assert (
                await handle.fetch("SELECT current_setting('app.owner_id') AS owner")
            )[0]["owner"] == "owner-b"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_statement_timeout_rolls_back_before_reuse(database_fixture):
    _, observer = database_fixture
    other = await Database.open(
        {**SETTINGS, "statement_timeout": 0.05, "command_timeout": 0.5}
    )
    try:
        with pytest.raises(RuntimeError, match="DATABASE_QUERY_FAILED"):
            async with other.transaction(owner_id="owner-a") as handle:
                await first_collaborator(handle)
                await handle.fetch("SELECT pg_sleep(10)")
        assert (
            await observer.fetchval("SELECT count(*) FROM pool_fixture.rollback_probe")
            == 0
        )
        assert (
            await other.fetch(
                "SELECT nullif(current_setting('app.owner_id', true), '') AS owner"
            )
        )[0]["owner"] is None
    finally:
        await other.close()


@pytest.mark.asyncio
async def test_broken_connection_is_replaced_without_previous_context(database_fixture):
    database, observer = database_fixture
    pid = None
    with pytest.raises(RuntimeError, match="DATABASE_QUERY_FAILED"):
        async with database.transaction(owner_id="owner-a") as handle:
            pid = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
            await first_collaborator(handle)
            assert await observer.fetchval("SELECT pg_terminate_backend($1)", pid)
            await handle.fetch("SELECT 1")
    assert (
        await observer.fetchval("SELECT count(*) FROM pool_fixture.rollback_probe") == 0
    )
    row = (
        await database.fetch(
            "SELECT pg_backend_pid() AS pid, nullif(current_setting('app.owner_id', true), '') AS owner"
        )
    )[0]
    assert row["pid"] != pid and row["owner"] is None


@pytest.mark.asyncio
async def test_configuration_rejects_unsafe_options_and_tls_bypass(
    database_fixture, monkeypatch
):
    for override in (
        {"max_size": True},
        {"min_size": 2},
        {"max_size": 0},
        {"max_size": 17},
        {"connect_timeout": 0},
        {"acquire_timeout": -1},
        {"command_timeout": float("nan")},
        {"close_timeout": 31},
        {"port": "5432"},
        {"dsn": "synthetic-secret-dsn"},
        {"server_settings": {"role": "synthetic-forbidden"}},
        {"ssl": False},
        {"host": "outside.invalid"},
        {"database": "foreign"},
        {"ca_file": "synthetic-missing.pem"},
    ):
        with pytest.raises(ValueError, match="^DATABASE_CONFIG_INVALID$") as failure:
            await Database.open({**SETTINGS, **override})
        assert failure.value.__cause__ is None and failure.value.__context__ is None
    monkeypatch.delenv("FOUNDATION_DB_HOST")
    with pytest.raises(ValueError, match="^DATABASE_CONFIG_INVALID$"):
        await Database.open(SETTINGS)


@pytest.mark.asyncio
async def test_verified_tls_is_default_and_never_falls_back_to_plaintext(
    database_fixture,
):
    settings = {key: value for key, value in SETTINGS.items() if key != "tls"}
    with pytest.raises(RuntimeError, match="^DATABASE_CONNECT_FAILED$") as failure:
        await Database.open(settings)
    assert failure.value.__cause__ is None and failure.value.__context__ is None


@pytest.mark.asyncio
async def test_close_deadline_terminates_only_its_held_connection(database_fixture):
    _, observer = database_fixture
    other = await Database.open({**SETTINGS, "close_timeout": 0.05})
    entered, release = asyncio.Event(), asyncio.Event()
    pid = None

    async def work():
        nonlocal pid
        with pytest.raises(RuntimeError, match="DATABASE_QUERY_FAILED"):
            async with other.transaction(owner_id="owner-a") as handle:
                pid = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0]["pid"]
                entered.set()
                await release.wait()
                await handle.fetch("SELECT 1")

    worker = asyncio.create_task(work())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(RuntimeError, match="DATABASE_CLOSE_TIMEOUT"):
            await asyncio.wait_for(other.close(), 1)
        with pytest.raises(RuntimeError, match="DATABASE_CLOSED"):
            await other.fetch("SELECT 1")
        async with asyncio.timeout(5):
            while await observer.fetchval(
                "SELECT EXISTS (SELECT FROM pg_stat_activity WHERE pid = $1)", pid
            ):
                pass
        release.set()
        await asyncio.wait_for(worker, 5)
    finally:
        release.set()
        await asyncio.gather(worker, return_exceptions=True)
        await other.close()


@pytest.mark.asyncio
async def test_server_rejected_commit_is_not_an_unknown_outcome(database_fixture):
    database, observer = database_fixture
    with pytest.raises(RuntimeError, match="DATABASE_TRANSACTION_ABORTED") as failure:
        async with database.transaction() as handle:
            await handle.execute(
                "INSERT INTO pool_fixture.deferred_probe VALUES ($1), ($1)", 1
            )
    assert getattr(failure.value, "commit_outcome", None) is None
    assert failure.value.__cause__ is None and failure.value.__context__ is None
    assert (
        await observer.fetchval("SELECT count(*) FROM pool_fixture.deferred_probe") == 0
    )
    assert (await database.fetch("SELECT 1 AS value"))[0]["value"] == 1


@pytest.mark.asyncio
async def test_reset_failure_does_not_undo_acknowledged_commit(database_fixture):
    _, observer = database_fixture
    async with commit_relay(cut_reset=True) as relay:
        other = await Database.open(
            {**SETTINGS, "host": "127.0.0.1", "port": relay.port}
        )
        try:
            async with other.transaction() as handle:
                before = (await handle.fetch("SELECT pg_backend_pid() AS pid"))[0][
                    "pid"
                ]
                await first_collaborator(handle)
            assert relay.reset_dropped and relay.commits == 1
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM pool_fixture.rollback_probe"
                )
                == 1
            )
            assert (await other.fetch("SELECT pg_backend_pid() AS pid"))[0][
                "pid"
            ] != before
        finally:
            await other.close()
