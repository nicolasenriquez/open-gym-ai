"""Atomic Coach reservation and restart through restricted PostgreSQL and real HTTP."""

import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import SECRET, A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

from opengym_platform.coach.jobs import Jobs
from opengym_platform.core.database import Database
from opengym_platform.identity.sessions import verify


async def runtime_connection(environment):
    return await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"])
        .read_text()
        .rstrip("\n"),
        ssl=False,
        timeout=5,
        command_timeout=5,
    )


@pytest.mark.asyncio
async def test_recovery_without_jobs_is_idempotent_and_returns_only_count(identities):
    _, environment = identities
    runtime = await runtime_connection(environment)
    try:
        assert await runtime.fetchval("SELECT coach.fail_interrupted_jobs()") == 0
        assert await runtime.fetchval("SELECT coach.fail_interrupted_jobs()") == 0
    finally:
        await runtime.close()


async def reserve(environment, owner, job, at, generation=0):
    connection = await runtime_connection(environment)
    try:
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id',$1,true)", owner)
            return dict(
                await connection.fetchrow(
                    "SELECT * FROM coach.reserve_job($1,$2,$3,$4,'review','manual',$5,$6)",
                    owner,
                    3 if owner == "B" else 0,
                    datetime(2100, 1, 1, tzinfo=UTC),
                    job,
                    generation,
                    at,
                )
            )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_reservation_serializes_single_flight_and_both_utc_caps(identities):
    observer, environment = identities
    await observer.execute("""
        UPDATE coach.settings SET enabled=true,per_profile_daily=1,instance_daily=1;
        INSERT INTO training.documents(owner_id,document) VALUES
            ('A','{"coach":{"consent":{"agreedAt":1}}}'),
            ('B','{"coach":{"consent":{"agreedAt":1}}}');
    """)
    at = datetime(2026, 12, 1, 23, 59, 59, tzinfo=UTC)
    results = await asyncio.gather(
        reserve(environment, "A", "a1", at), reserve(environment, "A", "a2", at)
    )
    assert sorted(row["state"] for row in results) == ["busy", "queued"]
    assert (await reserve(environment, "B", "b1", at))["state"] == "cap"
    assert (
        await observer.fetchval(
            "SELECT count FROM coach.daily_usage WHERE owner_id='A'"
        )
        == 1
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM coach.daily_usage WHERE owner_id='B'"
        )
        == 0
    )
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 1
    connection = await runtime_connection(environment)
    try:
        assert await connection.fetchval("SELECT coach.fail_interrupted_jobs()") == 1
    finally:
        await connection.close()
    assert (await reserve(environment, "A", "a3", at))["state"] == "cap"
    midnight = datetime(2026, 12, 2, tzinfo=UTC)
    assert (await reserve(environment, "B", "b2", midnight))["state"] == "queued"
    assert [
        tuple(row)
        for row in await observer.fetch(
            "SELECT day::text,count FROM coach.instance_daily_usage ORDER BY day"
        )
    ] == [("2026-12-01", 1), ("2026-12-02", 1)]


@pytest.mark.asyncio
@pytest.mark.parametrize("restart", [False, True])
async def test_worker_runs_only_two_without_holding_a_database_transaction(
    identities, monkeypatch, restart
):
    observer, environment = identities
    await observer.execute("""
        UPDATE coach.settings SET enabled=true;
        INSERT INTO identity.users(id,display_name) VALUES ('C','Carol');
        INSERT INTO training.documents(owner_id,document)
            SELECT id,'{"coach":{"consent":{"agreedAt":1}}}'::jsonb FROM identity.users;
    """)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()
    entered, release, complete = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls, active = [], set()

    async def execute(owner, job):
        active.add(owner)
        calls.append(owner)
        assert len(active) <= 2
        if len(calls) == 2:
            entered.set()
        await release.wait()
        active.remove(owner)
        if len(calls) == 3:
            complete.set()

    jobs = Jobs(database, execute)
    try:
        sessions = [
            verify("", f"Bearer {token}", False, SECRET)
            for token in (A, B, signed("C:4102444800000:0"))
        ]
        results = await asyncio.gather(
            *(jobs.enqueue(session, kind="review") for session in sessions)
        )
        assert len({job["id"] for job in results}) == 3
        await asyncio.wait_for(entered.wait(), 1)
        assert len(calls) == 2
        states = [
            row["state"]
            for row in await observer.fetch(
                "SELECT state FROM coach.jobs ORDER BY state"
            )
        ]
        assert states == ["queued", "running", "running"]
        # Every in-flight provider must be outside SQL: no idle transaction/owner locks.
        assert (
            await observer.fetchval("""SELECT count(*) FROM pg_stat_activity
            WHERE usename='opengym_api_runtime' AND state='idle in transaction'""")
            == 0
        )
        async with observer.transaction():
            assert (
                len(
                    await observer.fetch(
                        "SELECT id FROM identity.users FOR UPDATE NOWAIT"
                    )
                )
                == 3
            )
        if restart:
            await jobs.close()
            assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 3
            async with server(environment) as client:
                assert (await client.get("/api/v1/health/ready")).status_code == 200
                assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
                assert (
                    await observer.fetchval(
                        "SELECT count(*) FROM coach.history_events WHERE error_class='restart'"
                    )
                    == 3
                )
                assert len(calls) == 2
        else:
            release.set()
            await asyncio.wait_for(complete.wait(), 2)
            await asyncio.wait_for(asyncio.gather(*list(jobs.tasks)), 3)
            assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM coach.history_events WHERE outcome='nochange'"
                )
                == 3
            )
    finally:
        release.set()
        await jobs.close()
        await database.close()


@pytest.mark.asyncio
async def test_http_startup_archives_queued_and_running_without_replay_or_quota_reset(
    identities,
):
    observer, environment = identities
    await observer.execute("""
        INSERT INTO coach.jobs VALUES
            ('A','interrupted-a','review','manual','running',now(),0),
            ('B','interrupted-b','create','manual','queued',now(),0);
        INSERT INTO coach.daily_usage VALUES ('A','2026-12-01',9),('B','2026-12-01',7);
        INSERT INTO coach.instance_daily_usage VALUES ('2026-12-01',16);
        INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at)
            SELECT 'A','old-'||n,'review','nochange','2000-11-01'::timestamptz+n*interval '1 second'
            FROM generate_series(1,25) n;
    """)
    for _ in range(2):
        async with server(environment) as client:
            assert (await client.get("/api/v1/health/live")).status_code == 200
            assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM coach.history_events WHERE owner_id='A'"
                )
                == 20
            )
            assert [
                tuple(row)
                for row in await observer.fetch("""SELECT owner_id,job_id,outcome,error_class
                FROM coach.history_events WHERE error_class='restart' ORDER BY owner_id""")
            ] == [
                ("A", "interrupted-a", "failed", "restart"),
                ("B", "interrupted-b", "failed", "restart"),
            ]
            assert (
                await observer.fetchval("SELECT sum(count) FROM coach.daily_usage")
                == 16
            )
            assert (
                await observer.fetchval("SELECT count FROM coach.instance_daily_usage")
                == 16
            )
            assert (
                await client.post(
                    "/api/v1/coach/review", headers={"Authorization": f"Bearer {A}"}
                )
            ).status_code == 503


@pytest.mark.asyncio
async def test_refusals_do_not_consume_quota_and_unique_failure_rolls_back(identities):
    observer, environment = identities
    at = datetime(2026, 12, 1, tzinfo=UTC)
    assert (await reserve(environment, "A", "off", at))["state"] == "off"
    await observer.execute("UPDATE coach.settings SET enabled=true")
    assert (await reserve(environment, "A", "missing-consent", at))[
        "state"
    ] == "consent"
    for agreed in ("null", "false", "0", '""'):
        await observer.execute(
            """INSERT INTO training.documents(owner_id,document)
            VALUES ('A',jsonb_build_object('coach',jsonb_build_object('consent',jsonb_build_object('agreedAt',$1::jsonb))))
            ON CONFLICT(owner_id) DO UPDATE SET document=excluded.document""",
            agreed,
        )
        assert (await reserve(environment, "A", "no-consent", at))["state"] == "consent"
    await observer.execute("""UPDATE training.documents SET document='{"coach":{"consent":{"agreedAt":1}}}';
        INSERT INTO training.documents(owner_id,document) SELECT 'B',document FROM training.documents WHERE owner_id='A';
        INSERT INTO coach.profile_state(owner_id,forget_generation) VALUES ('A',1)""")
    assert (await reserve(environment, "A", "stale", at))["state"] == "consent"
    for provider in ("claude", "codex", "anthropic", "openai", "gemini", "compatible"):
        await observer.execute("UPDATE coach.settings SET provider=$1", provider)
        assert (await reserve(environment, "A", "unavailable", at, 1))["state"] == "off"
    assert await observer.fetchval("SELECT count(*) FROM coach.daily_usage") == 0
    await observer.execute(
        "UPDATE coach.settings SET provider='fixture',per_profile_daily=0,instance_daily=0"
    )
    assert (await reserve(environment, "A", "collision", at, 1))["state"] == "queued"
    with pytest.raises(asyncpg.UniqueViolationError):
        await reserve(environment, "B", "collision", at)
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 1
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM coach.profile_state WHERE owner_id='B'"
        )
        == 0
    )
    await observer.execute("UPDATE identity.users SET disabled=true WHERE id='B'")
    assert (await reserve(environment, "B", "disabled", at))["state"] == "unauthorized"


@pytest.mark.asyncio
async def test_instance_cap_race_and_zero_caps_are_atomic(identities):
    observer, environment = identities
    await observer.execute("""UPDATE coach.settings SET enabled=true,per_profile_daily=0,instance_daily=1;
        INSERT INTO training.documents(owner_id,document)
        SELECT id,'{"coach":{"consent":{"agreedAt":1}}}'::jsonb FROM identity.users""")
    at = datetime.fromisoformat("2026-12-02T00:30:00+02:00")
    rows = await asyncio.gather(
        reserve(environment, "A", "a", at), reserve(environment, "B", "b", at)
    )
    assert sorted(row["state"] for row in rows) == ["cap", "queued"]
    assert (
        await observer.fetchval("SELECT day::text FROM coach.instance_daily_usage")
        == "2026-12-01"
    )
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
    await observer.execute(
        "DELETE FROM coach.jobs; UPDATE coach.settings SET instance_daily=0"
    )
    for i in range(3):
        rows = await asyncio.gather(
            reserve(environment, "A", f"a-{i}", at),
            reserve(environment, "B", f"b-{i}", at),
        )
        assert [row["state"] for row in rows] == ["queued", "queued"]
        await observer.execute("DELETE FROM coach.jobs")
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 7
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 7


@pytest.mark.asyncio
async def test_job_constraints_rls_and_exact_privileged_function_acl(identities):
    observer, environment = identities
    for table in (
        "jobs",
        "history_events",
        "profile_state",
        "daily_usage",
        "instance_daily_usage",
    ):
        assert tuple(
            await observer.fetchrow(
                """SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner)
            FROM pg_class WHERE oid=$1::regclass""",
                f"coach.{table}",
            )
        ) == (True, True, "opengym_schema_owner")
    for signature in (
        "coach.fail_interrupted_jobs()",
        "coach.reserve_job(text,bigint,timestamptz,text,text,text,bigint,timestamptz)",
    ):
        assert tuple(
            await observer.fetchrow(
                """SELECT prosecdef,pg_get_userbyid(proowner),proconfig,
            EXISTS (SELECT FROM aclexplode(proacl) WHERE grantee=0)
            FROM pg_proc WHERE oid=$1::regprocedure""",
                signature,
            )
        ) == (
            True,
            "opengym_coach_executor",
            ["search_path=pg_catalog, pg_temp"],
            False,
        )
    assert tuple(
        await observer.fetchrow("""SELECT rolcanlogin,rolbypassrls,rolsuper
        FROM pg_roles WHERE rolname='opengym_coach_executor'""")
    ) == (False, False, False)
    for column, value in (
        ("kind", "invalid"),
        ("trigger", "invalid"),
        ("state", "finished"),
        ("forget_generation", -1),
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            await observer.execute(f"""INSERT INTO coach.jobs VALUES ('A','invalid','review','manual','queued',now(),0);
                UPDATE coach.jobs SET {column}='{value}'""")
    with pytest.raises(asyncpg.CheckViolationError):
        await observer.execute(
            "INSERT INTO coach.daily_usage VALUES ('A','2026-12-01',-1)"
        )
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await observer.execute(
            "INSERT INTO coach.profile_state(owner_id) VALUES ('missing')"
        )
    await observer.execute(
        """INSERT INTO coach.jobs VALUES ('A','owned','review','manual','queued',now(),0)"""
    )
    connection = await runtime_connection(environment)
    try:
        assert await connection.fetch("SELECT * FROM coach.jobs") == []
        for statement in (
            "SELECT * FROM coach.settings",
            "SELECT * FROM coach.instance_daily_usage",
            "SET ROLE opengym_coach_executor",
            "INSERT INTO coach.jobs VALUES ('B','forged','review','manual','queued',now(),0)",
            "UPDATE coach.jobs SET forget_generation=2",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(statement)
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id','A',true)")
            assert await connection.fetchval("SELECT job_id FROM coach.jobs") == "owned"
            assert (
                await connection.fetchrow("""SELECT * FROM coach.reserve_job('B',3,'2100-01-01','forged',
                'review','manual',0,now())""")
            )["state"] == "unauthorized"
            assert (
                await connection.execute("DELETE FROM coach.jobs WHERE owner_id='B'")
                == "DELETE 0"
            )
        assert await connection.fetch("SELECT * FROM coach.jobs") == []
    finally:
        await connection.close()
    indexes = " ".join(
        row["indexdef"]
        for row in await observer.fetch(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='coach' AND tablename='jobs'"
        )
    )
    assert "UNIQUE" in indexes and "(owner_id)" in indexes and "(job_id)" in indexes


@pytest.mark.asyncio
async def test_jobs_upgrade_from_configuration_preserves_training_selection_and_secrets(
    deployment, tmp_path
):
    observer, environment = deployment
    package = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        package,
        ignore=shutil.ignore_patterns(
            "p003_coach_lifecycle.py", "p003_coach_http.py", "p003_coach_jobs.py"
        ),
    )
    await migration({**environment, "PYTHONPATH": str(package.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p003_coach"
    )
    await observer.execute("""INSERT INTO identity.users(id,display_name) VALUES ('A','Alice');
        INSERT INTO training.documents(owner_id,document) VALUES ('A','{"_rev":7,"workouts":[]}');
        UPDATE coach.settings SET enabled=true,provider='claude';
        UPDATE coach.provider_settings SET secret_ref='protected-unmounted-original',bound_owner_id='A' WHERE provider='claude'""")
    before = await observer.fetchval("SELECT document FROM training.documents")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p003_coach_lifecycle"
    )
    assert await observer.fetchval("SELECT document FROM training.documents") == before
    assert tuple(
        await observer.fetchrow("SELECT enabled,provider FROM coach.settings")
    ) == (True, "claude")
    assert tuple(
        await observer.fetchrow(
            "SELECT secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='claude'"
        )
    ) == ("protected-unmounted-original", "A")
    assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0


@pytest.mark.asyncio
async def test_http_operation_probe_uses_application_worker_and_recovers_after_shutdown(
    identities, tmp_path
):
    observer, environment = identities
    await observer.execute("""UPDATE coach.settings SET enabled=true;
        INSERT INTO identity.users(id,display_name) VALUES ('C','Carol');
        INSERT INTO training.documents(owner_id,document)
            SELECT id,'{"coach":{"consent":{"agreedAt":1}}}'::jsonb FROM identity.users""")
    markers = tmp_path / "invocations"
    # Q3 operation seam: test-only HTTP probe, not a new production Coach route.
    factory = tmp_path / "coach_probe.py"
    factory.write_text(
        """import asyncio
from pathlib import Path
from fastapi import Request
from fastapi.responses import JSONResponse
from opengym_platform.application import create_app
from opengym_platform.coach.jobs import Refused
from opengym_platform.core.platform_settings import load_session_secret
from opengym_platform.identity.sessions import verify

def build():
    async def execute(owner,job):
        with Path(MARKERS).open('a') as output:
            output.write(owner+'\\n')
        await asyncio.Event().wait()
    app = create_app(coach_execute=execute)
    @app.post('/api/v1/proof/coach')
    async def reserve(request: Request):
        session = verify('',request.headers.get('authorization',''),False,load_session_secret())
        if session is None:
            return JSONResponse({'error':'not signed in'},status_code=401)
        try:
            job = await request.app.state.coach_jobs.enqueue(session,kind='review')
        except Refused as error:
            return JSONResponse(error.body,status_code=error.status)
        return JSONResponse({'job':job},status_code=202)
    return app
""".replace("MARKERS", repr(str(markers)))
    )
    proof_environment = {
        **environment,
        "PYTHONPATH": str(tmp_path) + ":" + environment.get("PYTHONPATH", "/app/src"),
    }
    async with server(proof_environment, factory="coach_probe:build") as client:
        assert (await client.post("/api/v1/proof/coach")).status_code == 401
        responses = await asyncio.gather(
            *(
                client.post(
                    "/api/v1/proof/coach?owner_id=B",
                    headers={"Authorization": f"Bearer {A}"},
                )
                for _ in range(2)
            )
        )
        assert sorted(response.status_code for response in responses) == [202, 409]
        for token in (B, signed("C:4102444800000:0")):
            assert (
                await client.post(
                    "/api/v1/proof/coach", headers={"Authorization": f"Bearer {token}"}
                )
            ).status_code == 202
        async with asyncio.timeout(3):
            while not markers.exists() or len(markers.read_text().splitlines()) < 2:
                await asyncio.sleep(0.02)
        assert [
            row["state"]
            for row in await observer.fetch(
                "SELECT state FROM coach.jobs ORDER BY state"
            )
        ] == ["queued", "running", "running"]
        assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 3
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {A}"})
        ).json()["user"]["id"] == "A"
    assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 3
    async with server(environment) as client:
        assert (await client.get("/api/v1/health/ready")).status_code == 200
        assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM coach.history_events WHERE error_class='restart'"
            )
            == 3
        )
        assert (
            await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 3
        )
        assert len(markers.read_text().splitlines()) == 2
        assert (await client.post("/api/v1/proof/coach")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [TimeoutError, RuntimeError])
async def test_execution_failure_is_safe_and_keeps_spending_record(
    identities, monkeypatch, failure
):
    observer, environment = identities
    await observer.execute("""UPDATE coach.settings SET enabled=true;
        INSERT INTO training.documents(owner_id,document) VALUES ('A','{"coach":{"consent":{"agreedAt":1}}}');
        INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at)
            SELECT 'A','old-'||n,'review','nochange','2000-11-01'::timestamptz+n*interval '1 second'
            FROM generate_series(1,25) n""")
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()

    async def execute(owner, job):
        raise failure("provider-sensitive-marker-not-for-history")

    jobs = Jobs(database, execute)
    try:
        session = verify("", f"Bearer {A}", False, SECRET)
        await jobs.enqueue(session, kind="review")
        await asyncio.wait_for(asyncio.gather(*list(jobs.tasks)), 3)
        assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
        assert (
            await observer.fetchval("SELECT count(*) FROM coach.history_events") == 20
        )
        assert tuple(
            await observer.fetchrow("""SELECT outcome,error_class,details::text FROM coach.history_events
            ORDER BY occurred_at DESC,event_id DESC LIMIT 1""")
        ) == ("failed", "timeout" if failure is TimeoutError else "internal", "{}")
        assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
        assert (
            await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 1
        )
    finally:
        await jobs.close()
        await database.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "UPDATE identity.users SET session_version=1 WHERE id='A'",
        "UPDATE identity.users SET disabled=true WHERE id='A'",
        "DELETE FROM identity.users WHERE id='A'",
    ],
)
async def test_reservation_revalidates_actor_after_lock_wait_without_spending(
    identities, change
):
    observer, environment = identities
    await observer.execute("""UPDATE coach.settings SET enabled=true;
        INSERT INTO training.documents(owner_id,document) VALUES ('A','{"coach":{"consent":{"agreedAt":1}}}')""")
    async with observer.transaction():
        await observer.execute("SELECT id FROM identity.users WHERE id='A' FOR UPDATE")
        pending = asyncio.create_task(
            reserve(environment, "A", "waiting", datetime.now(UTC))
        )
        async with asyncio.timeout(3):
            while True:
                await observer.execute("SELECT pg_stat_clear_snapshot()")
                if await observer.fetchval("""SELECT count(*) FROM pg_stat_activity WHERE
                    usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%coach.reserve_job%'"""):
                    break
                await asyncio.sleep(0.01)
        await observer.execute(change)
    assert (await pending)["state"] == "unauthorized"
    for table in ("jobs", "daily_usage", "instance_daily_usage", "profile_state"):
        assert await observer.fetchval(f"SELECT count(*) FROM coach.{table}") == 0
