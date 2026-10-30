"""Proposal decisions and forgetting through real HTTP and restricted PostgreSQL."""

import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import pytest
from test_coach_http import REVIEW, STATE, completed, configure, provider
from test_coach_jobs import runtime_connection
from test_identity_session import SECRET, A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

from opengym_platform.coach.jobs import Jobs
from opengym_platform.coach.pipeline import Pipeline
from opengym_platform.core.database import Database
from opengym_platform.identity.sessions import verify


def wire():
    return {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }


@pytest.mark.asyncio
async def test_resolution_keeps_ready_and_decision_events_without_applying_training(
    identities,
):
    observer, environment = identities
    async with provider([(200, wire())]) as (base, calls):
        await configure(observer, base)
        async with server(environment) as client:
            headers = {"Authorization": f"Bearer {A}"}
            for dismissed in (False, True):
                assert (
                    await client.post("/api/v1/coach/review", json={}, headers=headers)
                ).status_code == 202
                result = await completed(client)
                proposal = result["pending"]
                body = {
                    "accepted": ["change"],
                    "rejected": [1, 2],
                    "dismissed": dismissed,
                }
                response = await client.post(
                    "/api/v1/coach/pending/resolve?owner_id=B",
                    json=body,
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                assert response.json() == {"ok": True}
                result = await completed(client)
                assert result["pending"] is None
                assert result["last"]["outcome"] == (
                    "dismissed" if dismissed else "applied"
                )
                assert result["last"]["id"] == proposal["id"]
                assert "accepted" not in result["last"]
                assert "rejected" not in result["last"]
                assert (
                    await client.post(
                        "/api/v1/coach/pending/resolve", json=body, headers=headers
                    )
                ).json() == {"ok": True}
            events = await observer.fetch(
                "SELECT job_id,outcome,details FROM coach.history_events ORDER BY event_id"
            )
            assert [row["outcome"] for row in events] == [
                "ready",
                "applied",
                "ready",
                "dismissed",
            ]
            assert events[0]["job_id"] == events[1]["job_id"]
            assert events[2]["job_id"] == events[3]["job_id"]
            assert json.loads(events[1]["details"]) == {"accepted": 1, "rejected": 2}
            assert (
                json.loads(
                    await observer.fetchval("SELECT document FROM training.documents")
                )
                == STATE
            )
            assert (
                await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 2
            )
            assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("read_status", [True, False])
async def test_expiry_archives_once_and_history_retains_twenty_events(
    identities, read_status
):
    observer, environment = identities
    await configure(observer, "http://private.invalid")
    await observer.execute("""INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at)
        SELECT 'A','repeat','review','ready','2000-01-01'::timestamptz+n*interval '1 second' FROM generate_series(1,20) n;
        INSERT INTO coach.pending_proposals(owner_id,document) VALUES
        ('A','{"id":"repeat","kind":"review","expiresAt":1}'),
        ('B','{"id":"foreign","kind":"review","expiresAt":1}')""")
    async with server(environment) as client:
        headers = {"Authorization": f"Bearer {A}"}
        if read_status:
            result = (await client.get("/api/v1/coach/status", headers=headers)).json()
            assert result["pending"] is None
            assert result["last"]["outcome"] == "expired"
            assert result["cap"]["used"] == 0
        for _ in range(2):
            response = await client.post(
                "/api/v1/coach/pending/resolve", json={}, headers=headers
            )
            assert response.status_code == 200
    events = await observer.fetch(
        "SELECT outcome FROM coach.history_events WHERE owner_id='A' ORDER BY event_id"
    )
    assert len(events) == 20
    assert [row["outcome"] for row in events][-1] == "expired"
    assert (
        await observer.fetchval("SELECT proposal_id FROM coach.pending_proposals")
        == "foreign"
    )


@pytest.mark.asyncio
async def test_forget_works_when_off_clears_only_own_content_and_keeps_todays_usage(
    identities,
):
    observer, environment = identities
    await configure(observer, "http://private.invalid")
    await observer.execute("""INSERT INTO coach.profile_state VALUES ('A',true,4),('B',true,9);
        INSERT INTO coach.pending_proposals(owner_id,document)
            SELECT id,jsonb_build_object('id',id,'kind','review','expiresAt',1) FROM identity.users;
        INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at)
            SELECT id,id,'review','ready',now() FROM identity.users;
        INSERT INTO coach.daily_usage SELECT id,(now() AT TIME ZONE 'UTC')::date,3 FROM identity.users;
        INSERT INTO coach.daily_usage VALUES ('A','2000-01-01',2);
        INSERT INTO coach.instance_daily_usage VALUES ((now() AT TIME ZONE 'UTC')::date,6);
        UPDATE coach.settings SET provider='claude'""")
    async with server(environment) as client:
        for _ in range(2):
            response = await client.post(
                "/api/v1/coach/forget?owner_id=B",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 200, response.text
            assert response.json() == {"ok": True}
        assert (await client.post("/api/v1/coach/forget")).status_code == 401
    assert tuple(
        await observer.fetchrow(
            "SELECT sharing,forget_generation FROM coach.profile_state WHERE owner_id='A'"
        )
    ) == (False, 6)
    for table in ("jobs", "pending_proposals", "history_events"):
        assert (
            await observer.fetchval(
                f"SELECT count(*) FROM coach.{table} WHERE owner_id='A'"
            )
            == 0
        )
    assert (
        await observer.fetchval(
            "SELECT sum(count) FROM coach.daily_usage WHERE owner_id='A'"
        )
        == 3
    )
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 6
    assert (
        await observer.fetchval(
            "SELECT sharing FROM coach.profile_state WHERE owner_id='B'"
        )
        is True
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM coach.pending_proposals WHERE owner_id='B'"
        )
        == 1
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM coach.history_events WHERE owner_id='B'"
        )
        == 1
    )
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == STATE
    )


@asynccontextmanager
async def hanging_provider():
    started, disconnected = asyncio.Event(), asyncio.Event()

    async def answer(reader, writer):
        try:
            head = (await reader.readuntil(b"\r\n\r\n")).decode()
            size = next(
                int(line.split(":", 1)[1])
                for line in head.split("\r\n")
                if line.lower().startswith("content-length:")
            )
            await reader.readexactly(size)
            started.set()
            await reader.read()
            disconnected.set()
        finally:
            writer.close()
            await writer.wait_closed()

    listener = await asyncio.start_server(answer, "127.0.0.1", 0)
    try:
        yield (
            f"http://127.0.0.1:{listener.sockets[0].getsockname()[1]}",
            started,
            disconnected,
        )
    finally:
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["forget", "withdraw", "reset"])
async def test_forgetting_cancels_http_without_recreating_content_or_quota(
    identities, action
):
    observer, environment = identities
    async with hanging_provider() as (base, started, disconnected):
        await configure(observer, base)
        async with server(environment) as client:
            headers = {"Authorization": f"Bearer {A}"}
            assert (
                await client.post("/api/v1/coach/review", json={}, headers=headers)
            ).status_code == 202
            await asyncio.wait_for(started.wait(), 3)
            if action == "forget":
                response = await client.post("/api/v1/coach/forget", headers=headers)
            else:
                state = {
                    **STATE,
                    **(
                        {"coach": {"consent": None}}
                        if action == "withdraw"
                        else {"resetAt": 100}
                    ),
                }
                response = await client.put(
                    "/api/v1/data", json={"state": state, "baseRev": 7}, headers=headers
                )
            assert response.status_code == 200, response.text
            await asyncio.wait_for(disconnected.wait(), 3)
            # Consent can return while the old request is still completing.
            if action == "withdraw":
                state = (await client.get("/api/v1/data", headers=headers)).json()[
                    "state"
                ]
                state["coach"] = STATE["coach"]
                assert (
                    await client.put(
                        "/api/v1/data",
                        json={"state": state, "baseRev": state["_rev"]},
                        headers=headers,
                    )
                ).status_code == 200
            result = await completed(client)
            assert result["job"] is result["pending"] is result["last"] is None
            assert result["cap"]["used"] == 1
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 1
    assert (
        await observer.fetchval("SELECT forget_generation FROM coach.profile_state")
        == 1
    )


async def open_database(environment, monkeypatch):
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    return await Database.open_platform()


@pytest.mark.asyncio
async def test_deleted_owner_cannot_publish_late_provider_reply_or_recreate_usage(
    identities, monkeypatch
):
    observer, environment = identities
    release = asyncio.Event()
    async with provider([(200, wire())], release) as (base, calls):
        await configure(observer, base)
        database = await open_database(environment, monkeypatch)
        jobs = Jobs(database, pipeline=Pipeline(SECRET))
        try:
            await jobs.enqueue(verify("", f"Bearer {A}", False, SECRET), kind="review")
            async with asyncio.timeout(3):
                while not calls:
                    await asyncio.sleep(0.01)
            await observer.execute("DELETE FROM identity.users WHERE id='A'")
            release.set()
            await asyncio.wait_for(asyncio.gather(*list(jobs.tasks)), 3)
            for table in (
                "jobs",
                "pending_proposals",
                "history_events",
                "profile_state",
                "daily_usage",
            ):
                assert (
                    await observer.fetchval(f"SELECT count(*) FROM coach.{table}") == 0
                )
            assert (
                await observer.fetchval("SELECT count FROM coach.instance_daily_usage")
                == 1
            )
        finally:
            release.set()
            await jobs.close()
            await database.close()


@pytest.mark.asyncio
async def test_late_completion_after_cancel_does_not_overwrite_new_generation(
    identities, monkeypatch
):
    observer, environment = identities
    await configure(observer, "http://private.invalid")
    await observer.execute("UPDATE coach.settings SET provider='fixture'")
    database = await open_database(environment, monkeypatch)
    started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def execute(owner, job):
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()

    jobs = Jobs(database, execute)
    session = verify("", f"Bearer {A}", False, SECRET)
    try:
        old = await jobs.enqueue(session, kind="review")
        await asyncio.wait_for(started.wait(), 3)
        await jobs.forget(session)
        await asyncio.wait_for(cancelled.wait(), 3)
        await jobs.enqueue(session, kind="review")
        release.set()
        await asyncio.wait_for(asyncio.gather(*list(jobs.tasks)), 3)
        assert await observer.fetchval("SELECT count(*) FROM coach.history_events") == 1
        assert (
            await observer.fetchval("SELECT job_id FROM coach.history_events")
            != old["id"]
        )
        assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 2
        assert (
            await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 2
        )
    finally:
        release.set()
        await jobs.close()
        await database.close()


@pytest.mark.asyncio
async def test_forget_privileges_are_owner_scoped_and_upgrade_preserves_existing_state(
    deployment, tmp_path
):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p003_coach_admin.py", "p003_coach_lifecycle.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p003_coach_http"
    )
    await observer.execute("""INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'),('B','Bob');
        INSERT INTO coach.profile_state VALUES ('A',true,4),('B',true,9);
        INSERT INTO coach.daily_usage VALUES ('B','2000-01-01',2)""")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval(
            "SELECT forget_generation FROM coach.profile_state WHERE owner_id='A'"
        )
        == 4
    )
    connection = await runtime_connection(environment)
    try:
        assert await connection.fetch("SELECT * FROM coach.profile_state") == []
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id','A',true)")
            assert (
                await connection.execute(
                    "UPDATE coach.profile_state SET sharing=false,forget_generation=5 WHERE owner_id='B'"
                )
                == "UPDATE 0"
            )
            assert (
                await connection.execute(
                    "DELETE FROM coach.daily_usage WHERE owner_id='B'"
                )
                == "DELETE 0"
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(
                    "INSERT INTO coach.profile_state VALUES ('foreign',false,1)"
                )
        for statement in (
            "SELECT * FROM coach.instance_daily_usage",
            "UPDATE coach.daily_usage SET count=0",
            "UPDATE coach.profile_state SET owner_id='B'",
            "SET ROLE opengym_coach_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(statement)
        assert await connection.fetch("SELECT * FROM coach.profile_state") == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_queued_forget_never_calls_provider_and_preserves_each_admission(
    identities, monkeypatch
):
    observer, environment = identities
    await configure(observer, "http://private.invalid")
    await observer.execute("""UPDATE coach.settings SET provider='fixture';
        INSERT INTO identity.users(id,display_name) VALUES ('C','Carol');
        INSERT INTO training.documents(owner_id,document) SELECT id,'{"coach":{"consent":{"agreedAt":1}}}'
            FROM identity.users WHERE id IN ('B','C')""")
    database = await open_database(environment, monkeypatch)
    release, started = asyncio.Event(), asyncio.Event()
    calls = []

    async def execute(owner, job):
        calls.append(owner)
        if len(calls) == 2:
            started.set()
        await release.wait()

    jobs = Jobs(database, execute)
    try:
        for token in (A, B, signed("C:4102444800000:0")):
            await jobs.enqueue(
                verify("", f"Bearer {token}", False, SECRET), kind="review"
            )
        await asyncio.wait_for(started.wait(), 3)
        assert (
            await observer.fetchval("SELECT state FROM coach.jobs WHERE owner_id='C'")
            == "queued"
        )
        await jobs.forget(
            verify("", f"Bearer {signed('C:4102444800000:0')}", False, SECRET)
        )
        release.set()
        await asyncio.wait_for(
            asyncio.gather(*list(jobs.tasks), return_exceptions=True), 3
        )
        assert sorted(calls) == ["A", "B"]
        assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
        assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 3
        assert (
            await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 3
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM coach.history_events WHERE owner_id='C'"
            )
            == 0
        )
    finally:
        release.set()
        await jobs.close()
        await database.close()


@pytest.mark.asyncio
async def test_failed_withdrawal_rolls_back_training_and_does_not_cancel_authorized_work(
    identities,
):
    observer, environment = identities
    release = asyncio.Event()
    async with provider([(200, wire())], release) as (base, calls):
        await configure(observer, base)
        await observer.execute(
            "INSERT INTO coach.profile_state(owner_id,forget_generation) VALUES ('A',9223372036854775807)"
        )
        async with server(environment) as client:
            headers = {"Authorization": f"Bearer {A}"}
            assert (
                await client.post("/api/v1/coach/review", json={}, headers=headers)
            ).status_code == 202
            async with asyncio.timeout(3):
                while not calls:
                    await asyncio.sleep(0.01)
            response = await client.put(
                "/api/v1/data",
                json={"state": {**STATE, "coach": {"consent": None}}, "baseRev": 7},
                headers=headers,
            )
            assert response.status_code == 500
            assert (
                json.loads(
                    await observer.fetchval("SELECT document FROM training.documents")
                )
                == STATE
            )
            assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 1
            release.set()
            assert (await completed(client))["last"]["outcome"] == "ready"
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1


@pytest.mark.asyncio
async def test_lifecycle_routes_enforce_csrf_and_reject_revoked_sessions(
    identities,
):
    observer, environment = identities
    await configure(observer, "http://private.invalid")
    async with server(environment) as client:
        for path in ("forget", "pending/resolve"):
            url = "/api/v1/coach/" + path
            assert (await client.post(url)).status_code == 401
            response = await client.post(
                url,
                json={},
                headers={"Cookie": f"gymsid={A}", "Origin": "https://foreign.invalid"},
            )
            assert response.status_code == 403
            assert response.headers["cache-control"] == "no-store"
        await observer.execute(
            "UPDATE identity.users SET session_version=1 WHERE id='A'"
        )
        for path in ("forget", "pending/resolve"):
            assert (
                await client.post(
                    "/api/v1/coach/" + path,
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).status_code == 401


@pytest.mark.asyncio
async def test_resolution_preserves_legacy_json_truthiness_and_array_counts(identities):
    observer, environment = identities
    await configure(observer, "http://private.invalid")
    async with server(environment) as client:
        for dismissed in ({}, []):
            await observer.execute("""INSERT INTO coach.pending_proposals(owner_id,document)
                VALUES ('A','{"id":"legacy","kind":"review","expiresAt":4102444800000}')""")
            response = await client.post(
                "/api/v1/coach/pending/resolve",
                json={"dismissed": dismissed, "accepted": "text", "rejected": {}},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 200
            result = await completed(client)
            assert result["last"]["outcome"] == "dismissed"
            assert json.loads(
                await observer.fetchval(
                    "SELECT details FROM coach.history_events ORDER BY event_id DESC LIMIT 1"
                )
            ) == {"accepted": 0, "rejected": 0}
