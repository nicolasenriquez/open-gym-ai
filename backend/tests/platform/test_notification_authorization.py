"""Owner revalidation, migration and queue/back-off proofs for internal delivery."""

import asyncio
import shutil
from datetime import datetime
from pathlib import Path

import asyncpg
import pytest
from test_coach_jobs import runtime_connection
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration
from test_notification_delivery import NOW, STATE, runtime_environment, seed

from opengym_platform.application import create_app


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["disable", "opt_out", "unsubscribe", "delete"])
async def test_candidate_revalidates_after_owner_wait(identities, monkeypatch, change):
    observer, environment = identities
    await seed(observer)
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append(payload)
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            pending = asyncio.create_task(app.state.notifications.tick(NOW))
            async with asyncio.timeout(1.5):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if (
                        await observer.fetchval(
                            "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%notifications.lock_delivery_owner%'"
                        )
                        == 1
                    ):
                        break
                    await asyncio.sleep(0.01)
            await observer.execute(
                {
                    "disable": "UPDATE identity.users SET disabled=true WHERE id='A'",
                    "opt_out": "UPDATE training.documents SET document=jsonb_set(document,'{reminder,on}','false') WHERE owner_id='A'",
                    "unsubscribe": "DELETE FROM notifications.subscriptions WHERE owner_id='A'",
                    "delete": "DELETE FROM identity.users WHERE id='A'",
                }[change]
            )
        await pending
        assert calls == []
        assert (
            await observer.fetchval("SELECT count(*) FROM notifications.delivery_state")
            == 0
        )
        async with app.state.database.transaction() as handle:
            assert not (
                await handle.fetch(
                    "SELECT nullif(current_setting('app.owner_id',true),'') AS owner"
                )
            )[0]["owner"]


@pytest.mark.asyncio
async def test_failed_send_cannot_prune_transferred_endpoint(identities, monkeypatch):
    observer, environment = identities
    await seed(observer)
    await seed(observer, {**STATE, "reminder": {"on": False}}, "B")
    runtime_environment(monkeypatch, environment)

    async def send(subscription, payload):
        await observer.execute(
            "UPDATE notifications.subscriptions SET owner_id='B' WHERE endpoint=$1",
            subscription["endpoint"],
        )
        return 410

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        await app.state.notifications.tick(NOW)
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM notifications.subscriptions WHERE owner_id='B'"
        )
        == 2
    )


@pytest.mark.asyncio
async def test_upgrade_acl_and_rejected_owner_preserve_context(deployment, tmp_path):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p005_delivery.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_admin_users"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES('A','Alice'),('B','Bob')"
    )
    await seed(observer)
    original = await observer.fetchval("SELECT document FROM training.documents")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p005_delivery"
    )
    assert (
        await observer.fetchval("SELECT document FROM training.documents") == original
    )
    connection = await runtime_connection(environment)
    try:
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id','A',true)")
            assert not await connection.fetch(
                "SELECT * FROM notifications.lock_delivery_owner('B')"
            )
            assert (
                await connection.fetchval("SELECT current_setting('app.owner_id')")
                == "A"
            )
            assert [
                r["owner_id"]
                for r in await connection.fetch(
                    "SELECT * FROM notifications.delivery_candidates(now())"
                )
            ] == ["A"]
            assert not await connection.fetch(
                "SELECT * FROM notifications.delivery_candidates(NULL)"
            )
        assert not await connection.fetchval(
            "SELECT nullif(current_setting('app.owner_id',true),'')"
        )
        assert (
            await connection.fetch("SELECT * FROM notifications.delivery_state") == []
        )
        for statement in (
            "SET ROLE opengym_notifications_executor",
            "UPDATE identity.users SET disabled=false",
            "INSERT INTO notifications.delivery_state VALUES('A',current_date,NULL)",
        ):
            with pytest.raises(asyncpg.PostgresError):
                await connection.execute(statement)
    finally:
        await connection.close()
    functions = await observer.fetch(
        "SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,NOT EXISTS(SELECT FROM aclexplode(proacl) WHERE grantee=0) AS private FROM pg_proc WHERE pronamespace='notifications'::regnamespace AND proname IN ('delivery_candidates','lock_delivery_owner')"
    )
    assert len(functions) == 2
    assert all(
        tuple(row)
        == (
            True,
            ["search_path=pg_catalog, pg_temp"],
            "opengym_notifications_executor",
            True,
        )
        for row in functions
    )
    assert await observer.fetchval(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='notifications.delivery_state'::regclass"
    )
    async with observer.transaction():
        await observer.execute(
            "INSERT INTO notifications.delivery_state VALUES('A',current_date,NULL)"
        )
        await observer.execute("DELETE FROM identity.users WHERE id='A'")
        assert (
            await observer.fetchval("SELECT count(*) FROM notifications.delivery_state")
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("patch", "instant", "tag"),
    [
        ({"week": {"0": ["gone", "r"]}}, "2026-11-01T05:35:00+00:00", "day-reminder"),
        (
            {
                "week": {},
                "queue": {"ids": ["r"], "since": 1000, "startsOn": "2026-11-01"},
                "dayPlan": {"2026-11-02": "r"},
            },
            "2026-11-01T05:35:00+00:00",
            None,
        ),
        (
            {
                "week": {},
                "queue": {"ids": ["r"], "since": 5000, "startsOn": "2026-10-30"},
                "workouts": [
                    {
                        "routineId": "r",
                        "d": "2026-10-31",
                        "start": 1000,
                        "name": "Strength",
                    }
                ],
            },
            "2026-11-01T05:35:00+00:00",
            None,
        ),
        (
            {
                "week": {},
                "queue": {
                    "ids": ["r"],
                    "since": 5000,
                    "strict": True,
                    "startsOn": "2026-10-30",
                },
                "workouts": [
                    {
                        "routineId": "r",
                        "d": "2026-10-31",
                        "start": 1000,
                        "name": "Strength",
                    }
                ],
            },
            "2026-11-01T05:35:00+00:00",
            "day-reminder",
        ),
        (
            {
                "week": {str(d): "r" for d in range(7)},
                "workouts": [{"d": "2026-10-28"}],
                "reminder": {"on": True, "nudge": True, "time": "08:00", "tz": "UTC"},
            },
            "2026-11-01T20:00:00+00:00",
            None,
        ),
        (
            {
                "week": {str(d): "r" for d in range(7)},
                "workouts": [{"d": "2026-10-29"}],
                "reminder": {"on": True, "nudge": True, "time": "08:00", "tz": "UTC"},
            },
            "2026-11-01T21:30:00+00:00",
            "nudge",
        ),
        (
            {
                "week": {},
                "queue": {"ids": ["r"], "since": 5000, "startsOn": "2026-10-30"},
                "workouts": [{"d": "2026-10-31", "routineId": "another"}],
                "reminder": {"on": True, "nudge": True, "time": "08:00", "tz": "UTC"},
            },
            "2026-11-01T20:00:00+00:00",
            None,
        ),
        (
            {
                "week": {},
                "queue": {"ids": ["r"], "since": 5000, "startsOn": "2026-10-30"},
                "workouts": [{"d": "2026-10-30", "routineId": "another"}],
                "reminder": {"on": True, "nudge": True, "time": "08:00", "tz": "UTC"},
            },
            "2026-11-01T20:00:00+00:00",
            "nudge",
        ),
        (
            {"reminder": {"on": True, "time": "23:55", "tz": "UTC"}},
            "2026-11-02T00:05:00+00:00",
            None,
        ),
        (
            {"reminder": {"on": True, "time": "02:30", "tz": "America/New_York"}},
            "2026-03-08T07:00:00+00:00",
            None,
        ),
        (
            {
                "week": {"1": "r"},
                "reminder": {"on": True, "time": "00:30", "tz": "Pacific/Kiritimati"},
            },
            "2026-11-01T10:30:00+00:00",
            "day-reminder",
        ),
    ],
)
async def test_queue_backoff_and_date_boundary_vectors(
    identities, monkeypatch, patch, instant, tag
):
    observer, environment = identities
    await seed(observer, {**STATE, **patch})
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append(payload)
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        await app.state.notifications.tick(datetime.fromisoformat(instant))
    assert [p["tag"] for p in calls] == ([tag] if tag else [])


@pytest.mark.asyncio
async def test_lifespan_runs_periodic_tick_without_http_trigger(
    identities, monkeypatch
):
    from opengym_platform.notifications import scheduler

    observer, environment = identities
    await seed(observer)
    runtime_environment(monkeypatch, environment)

    class Clock:
        @staticmethod
        def now(zone):
            return NOW

    monkeypatch.setattr(scheduler, "datetime", Clock)
    delivered = asyncio.Event()

    async def send(subscription, payload):
        delivered.set()
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with asyncio.timeout(14):
            await delivered.wait()
    assert (
        str(
            await observer.fetchval(
                "SELECT last_reminder_date FROM notifications.delivery_state WHERE owner_id='A'"
            )
        )
        == "2026-11-01"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lang", "tone", "time", "expected"),
    [
        (
            "pt-BR",
            "friendly",
            "01:35",
            {
                "title": "{name} Name {emoji} hoje",
                "body": "Está no seu plano. Bora treinar 💪",
                "tag": "day-reminder",
            },
        ),
        (
            "de-CH",
            "drill",
            "20:00",
            {
                "title": "Achtung, Rekrut!",
                "body": "Ausreden stemmen keine Gewichte. Morgen trittst du zu Name {emoji} an!",
                "tag": "nudge",
            },
        ),
    ],
)
async def test_copy_preserves_literal_routine_names_and_node_locales(
    identities, monkeypatch, lang, tone, time, expected
):
    observer, environment = identities
    await seed(
        observer,
        {
            **STATE,
            "lang": lang,
            "routines": [{"id": "r", "name": "Name {emoji}", "emoji": "{name}"}],
            "reminder": {
                "on": True,
                "nudge": True,
                "tone": tone,
                "time": "01:30",
                "tz": "UTC",
            },
        },
    )
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append(payload)
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        await app.state.notifications.tick(
            datetime.fromisoformat(f"2026-11-01T{time}:00+00:00")
        )
    assert calls == [expected]


@pytest.mark.asyncio
async def test_failed_prune_does_not_leave_sibling_sends_running_after_tick(
    identities, monkeypatch
):
    observer, environment = identities
    await seed(observer)
    await observer.execute(
        "INSERT INTO notifications.subscriptions VALUES('https://push.example/slow','A','p','a',NULL,now())"
    )
    runtime_environment(monkeypatch, environment)
    finished = asyncio.Event()

    async def send(subscription, payload):
        if subscription["endpoint"].endswith("/A"):
            await observer.execute(
                "REVOKE DELETE ON notifications.subscriptions FROM opengym_api_runtime"
            )
            return 410
        await asyncio.sleep(0.15)
        finished.set()
        return 201

    app = create_app()
    try:
        async with app.router.lifespan_context(app):
            app.state.notifications.send = send
            await app.state.notifications.tick(NOW)
            assert finished.is_set(), (
                "A failed pruning transaction must not abandon sibling sends"
            )
    finally:
        await observer.execute(
            "GRANT DELETE ON notifications.subscriptions TO opengym_api_runtime"
        )
