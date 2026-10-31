"""Consented Coach collaboration through HTTP and restricted PostgreSQL."""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from test_coach_http import STATE, configure, provider
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server


@pytest.mark.asyncio
async def test_disclosure_precedes_consent_and_requires_authentication(identities):
    observer, environment = identities
    await configure(observer, "http://127.0.0.1:9")
    async with server(environment) as client:
        assert (await client.get("/api/v1/coach/disclosure")).status_code == 401
        response = await client.get(
            "/api/v1/coach/disclosure", headers={"Authorization": f"Bearer {B}"}
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "provider": "compatible",
            "providerLabel": "OpenAI-compatible endpoint",
            "categories": ["plan", "training", "bodyweight", "profile", "prefs"],
            "version": 1,
        }


@pytest.mark.asyncio
async def test_cohort_sharing_requires_consent_and_never_exposes_candidates(identities):
    observer, environment = identities
    await configure(observer, "http://127.0.0.1:9")
    await observer.execute("UPDATE coach.settings SET community=true")
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/coach/cohort/share",
            json={"share": True, "owner_id": "B"},
            headers={"Authorization": f"Bearer {A}"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "sharing": True}
        assert (
            await observer.fetchval(
                "SELECT sharing FROM coach.profile_state WHERE owner_id='A'"
            )
            is True
        )
        assert (
            await observer.fetchval(
                "SELECT sharing FROM coach.profile_state WHERE owner_id='B'"
            )
            is None
        )
        response = await client.get(
            "/api/v1/coach/cohort", headers={"Authorization": f"Bearer {A}"}
        )
        assert response.json() == {
            "ok": False,
            "enabled": True,
            "sharing": True,
            "people": 0,
            "minPeople": 3,
        }
        assert (
            await client.post(
                "/api/v1/coach/cohort/share",
                json={"share": True},
                headers={"Authorization": f"Bearer {B}"},
            )
        ).status_code == 403
        assert (
            json.loads(
                await observer.fetchval(
                    "SELECT document FROM training.documents WHERE owner_id='A'"
                )
            )
            == STATE
        )


@pytest.mark.asyncio
async def test_cohort_uses_three_finite_catalogue_participants_and_honors_opt_out(
    identities,
):
    observer, environment = identities
    await configure(observer, "http://127.0.0.1:9")
    await observer.execute(
        "UPDATE coach.settings SET community=true; INSERT INTO identity.users(id,display_name) VALUES('C','PRIVATE-C'),('D','PRIVATE-D')"
    )
    today = datetime.now(UTC).date().isoformat()
    for owner, weight in (("A", 60), ("B", 100), ("C", 140), ("D", 9000)):
        document = {
            **STATE,
            "unit": "kg",
            "workouts": [
                {
                    "d": today,
                    "entries": [
                        {
                            "id": "0001" if owner != "D" else "PRIVATE-CUSTOM",
                            "sets": [
                                {"w": weight, "r": 5, "done": True},
                                {"w": 999999, "r": 5, "done": True, "phase": "warmup"},
                            ],
                        }
                    ],
                }
            ],
        }
        await observer.execute(
            "INSERT INTO training.documents(owner_id,document) VALUES($1,$2::jsonb) ON CONFLICT(owner_id) DO UPDATE SET document=excluded.document",
            owner,
            json.dumps(document),
        )
        await observer.execute(
            "INSERT INTO coach.profile_state(owner_id,sharing) VALUES($1,true)", owner
        )
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/coach/cohort?owner_id=C", headers={"Authorization": f"Bearer {A}"}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["people"] == 4
        assert result["sessionsPerWeek"] == {"median": 0.1, "you": 0.1}
        assert len(result["exercises"]) == 1
        assert result["exercises"][0]["median"] == 116.7
        assert result["exercises"][0]["you"] == 70
        assert result["exercises"][0]["people"] == 3
        assert result["rankPct"] == 0
        assert "PRIVATE" not in response.text and today not in response.text
        assert (
            await client.post(
                "/api/v1/coach/cohort/share",
                json={"share": False},
                headers={"Authorization": f"Bearer {B}"},
            )
        ).status_code == 200
        result = (
            await client.get(
                "/api/v1/coach/cohort", headers={"Authorization": f"Bearer {A}"}
            )
        ).json()
        assert (
            result["people"] == 3
            and result["exercises"] == []
            and result["rankPct"] is None
        )


@pytest.mark.asyncio
async def test_scheduled_review_runs_without_a_session_and_does_not_replay_on_restart(
    identities,
):
    observer, environment = identities
    wire = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "coach_contract": 1,
                            "nochange": True,
                            "reading": "Schedule checked",
                            "changes": [],
                        }
                    )
                },
                "finish_reason": "stop",
            }
        ]
    }
    async with provider([(200, wire)]) as (base, calls):
        await configure(observer, base)
        document = {
            **STATE,
            "coach": {**STATE["coach"], "cadence": {"everyWorkouts": 1}},
            "workouts": [
                {
                    "id": "w1",
                    "d": datetime.now(UTC).date().isoformat(),
                    "end": int(datetime.now(UTC).timestamp() * 1000) - 1000,
                    "entries": [],
                }
            ],
        }
        await observer.execute(
            "UPDATE training.documents SET document=$1::jsonb WHERE owner_id='A'",
            json.dumps(document),
        )
        for attempt in range(2):
            async with server(environment):
                async with asyncio.timeout(8):
                    while not await observer.fetchval(
                        "SELECT count(*) FROM coach.history_events WHERE owner_id='A' AND outcome='nochange'"
                    ):
                        await asyncio.sleep(0.05)
                assert len(calls) == 1
                assert (
                    await observer.fetchval(
                        "SELECT count FROM coach.daily_usage WHERE owner_id='A'"
                    )
                    == 1
                )
                assert (
                    await observer.fetchval(
                        "SELECT trigger FROM coach.instance_results"
                    )
                    == "scheduled"
                )
        assert len(calls) == 1


@pytest.mark.parametrize(
    ("cadence", "last", "instant", "expected"),
    [
        ({"everyWorkouts": 2}, 0, "2026-10-30T12:00:00+00:00", False),
        ({"everyWorkouts": 1}, 0, "2026-10-30T12:00:00+00:00", True),
        ({"everyWorkouts": 1}, 1793361600000, "2026-10-30T12:00:00+00:00", False),
        (
            {"weekly": {"day": 0, "time": "18:00"}},
            1792965600000,
            "2026-10-30T12:00:00+00:00",
            False,
        ),
        (
            {"weekly": {"day": 0, "time": "18:00"}},
            1792965600000,
            "2026-11-01T22:00:00+00:00",
            False,
        ),
        (
            {"weekly": {"day": 0, "time": "18:00"}},
            1792965600000,
            "2026-11-01T23:00:00+00:00",
            True,
        ),
        ({"weekly": {"day": 0, "time": "bad"}}, 0, "2026-10-30T12:00:00+00:00", False),
        ({"everyWorkouts": "invalid"}, 0, "2026-10-30T12:00:00+00:00", False),
    ],
)
def test_cadence_independent_workout_and_new_york_fall_back_vectors(
    cadence, last, instant, expected
):
    from opengym_platform.coach.cadence import due

    state = {
        "coach": {"cadence": cadence},
        "reminder": {"tz": "America/New_York"},
        "workouts": [{"d": "2026-10-30"}],
    }
    assert due(state, last, datetime.fromisoformat(instant)) is expected


@pytest.mark.asyncio
async def test_refused_internal_owner_never_installs_foreign_training_context(
    identities,
):
    from test_coach_jobs import runtime_connection

    observer, environment = identities
    await configure(observer, "http://127.0.0.1:9")
    connection = await runtime_connection(environment)
    try:
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id','A',true)")
            assert not await connection.fetch(
                "SELECT * FROM coach.lock_scheduled_owner('B')"
            )
            assert (
                await connection.fetchval("SELECT current_setting('app.owner_id')")
                == "A"
            )
            assert [
                row["owner_id"]
                for row in await connection.fetch(
                    "SELECT owner_id FROM training.documents"
                )
            ] == ["A"]
    finally:
        await connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "setting", ["enabled=true", "enabled=false", "provider='codex'"]
)
async def test_turning_cadence_off_allows_the_existing_scheduled_review_to_finish(
    identities,
    setting,
):
    from test_coach_jobs import runtime_connection

    observer, environment = identities
    await configure(observer, "http://127.0.0.1:9")
    await observer.execute(
        "UPDATE training.documents SET document=jsonb_set(document,'{coach,cadence}','{}') WHERE owner_id='A'"
    )
    connection = await runtime_connection(environment)
    try:
        async with connection.transaction():
            result = await connection.fetchrow(
                "SELECT * FROM coach.reserve_scheduled_job('A','existing',0,clock_timestamp())"
            )
            assert result["state"] == "queued"
        await observer.execute(
            "UPDATE training.documents SET document=jsonb_set(document,'{coach,cadence}','\"off\"') WHERE owner_id='A'"
        )
        await observer.execute("UPDATE coach.settings SET " + setting)
        async with connection.transaction():
            assert await connection.fetch(
                "SELECT * FROM coach.lock_scheduled_owner('A')"
            )
            assert not await connection.fetch(
                "SELECT * FROM coach.scheduled_candidates(clock_timestamp())"
            )
    finally:
        await connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("weight", [100, 1e308])
async def test_provider_receives_only_consented_coarse_cohort_not_client_injection(
    identities, weight
):
    from test_coach_http import completed

    observer, environment = identities
    wire = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "coach_contract": 1,
                            "nochange": True,
                            "reading": "Coarse only",
                            "changes": [],
                        }
                    )
                },
                "finish_reason": "stop",
            }
        ]
    }
    async with provider([(200, wire), (200, wire)]) as (base, calls):
        await configure(observer, base)
        await observer.execute(
            "UPDATE coach.settings SET community=true; INSERT INTO identity.users(id,display_name) VALUES('C','PRIVATE-OTHER')"
        )
        today = datetime.now(UTC).date().isoformat()
        for owner in ("A", "B", "C"):
            doc = {
                **STATE,
                "workouts": [
                    {
                        "d": today,
                        "entries": [
                            {
                                "id": "0001",
                                "sets": [{"w": weight, "r": 5, "done": True}],
                            }
                        ],
                    }
                ],
            }
            await observer.execute(
                "INSERT INTO training.documents(owner_id,document) VALUES($1,$2::jsonb) ON CONFLICT(owner_id) DO UPDATE SET document=excluded.document",
                owner,
                json.dumps(doc),
            )
            await observer.execute(
                "INSERT INTO coach.profile_state(owner_id,sharing) VALUES($1,true)",
                owner,
            )
        async with server(environment) as client:
            for sharing in (True, False):
                if not sharing:
                    assert (
                        await client.post(
                            "/api/v1/coach/cohort/share",
                            json={"share": False},
                            headers={"Authorization": f"Bearer {A}"},
                        )
                    ).status_code == 200
                assert (
                    await client.post(
                        "/api/v1/coach/review",
                        json={"cohort": {"people": 999, "private": "CLIENT-INJECTION"}},
                        headers={"Authorization": f"Bearer {A}"},
                    )
                ).status_code == 202
                assert (await completed(client))["last"]["outcome"] == "nochange"
        payloads = [
            json.loads(
                call[1]["messages"][1]["content"]
                .split("```json\n")[1]
                .split("\n```")[0]
            )
            for call in calls
        ]
        assert payloads[0]["cohort"]["people"] == 3
        assert payloads[0]["cohort"]["unit"] == "kg"
        assert len(payloads[0]["cohort"]["exercises"]) == 1
        assert "cohort" not in payloads[1]
        assert "PRIVATE" not in json.dumps(payloads[0]["cohort"])
        assert "CLIENT-INJECTION" not in json.dumps(payloads)


@pytest.mark.parametrize(
    "instant", ["2026-11-01T06:15:00+00:00", "2026-11-01T06:45:00+00:00"]
)
def test_weekly_repeated_hour_cannot_repeat_a_finished_review(instant):
    from opengym_platform.coach.cadence import due

    state = {
        "coach": {"cadence": {"weekly": {"day": 0, "time": "01:30"}}},
        "reminder": {"tz": "America/New_York"},
        "workouts": [
            {
                "d": "2026-11-01",
                "end": int(
                    datetime.fromisoformat("2026-11-01T06:10:00+00:00").timestamp()
                    * 1000
                ),
            }
        ],
    }
    reviewed = int(
        datetime.fromisoformat("2026-11-01T05:45:00+00:00").timestamp() * 1000
    )
    assert due(state, reviewed, datetime.fromisoformat(instant)) is False


def test_malformed_weekly_time_does_not_stop_scheduled_processing():
    from opengym_platform.coach.cadence import due

    assert (
        due(
            {
                "coach": {"cadence": {"weekly": {"time": 18}}},
                "workouts": [{"d": "2026-10-30"}],
            },
            0,
            datetime(2026, 10, 30, tzinfo=UTC),
        )
        is False
    )


def test_weekly_repeated_hour_still_catches_up_after_first_slot_passed():
    from opengym_platform.coach.cadence import due

    now = datetime.fromisoformat("2026-11-01T06:15:00+00:00")
    previous = int(
        datetime.fromisoformat("2026-10-25T06:00:00+00:00").timestamp() * 1000
    )
    state = {
        "coach": {"cadence": {"weekly": {"day": 0, "time": "01:30"}}},
        "reminder": {"tz": "America/New_York"},
        "workouts": [{"d": "2026-11-01"}],
    }
    assert due(state, previous, now) is True


@pytest.mark.asyncio
async def test_client_upgrade_keeps_deferred_configuration_and_has_bounded_function_grants(
    deployment, tmp_path
):
    import shutil
    from pathlib import Path

    from test_lifecycle import migration

    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns(
            "p004_admin_users.py", "p005_subscriptions.py", "p003_coach_client.py"
        ),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p003_coach_admin"
    )
    await observer.execute(
        "UPDATE coach.settings SET enabled=true,provider='codex'; UPDATE coach.provider_settings SET model='preserved-model' WHERE provider='codex'"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_admin_users"
    )
    assert await observer.fetchval("SELECT provider FROM coach.settings") == "codex"
    assert (
        await observer.fetchval(
            "SELECT model FROM coach.provider_settings WHERE provider='codex'"
        )
        == "preserved-model"
    )
    for signature in (
        "cohort_candidates(text,bigint,timestamptz)",
        "lock_cohort_owner(text,bigint,timestamptz,text)",
        "scheduled_candidates(timestamptz)",
        "lock_scheduled_owner(text)",
        "reserve_scheduled_job(text,text,bigint,timestamptz)",
    ):
        row = await observer.fetchrow(
            "SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,NOT EXISTS(SELECT FROM aclexplode(proacl) a WHERE a.grantee=0) AS private,has_function_privilege('opengym_api_runtime',oid,'EXECUTE') AS runtime FROM pg_proc WHERE oid=$1::regprocedure",
            "coach." + signature,
        )
        assert row["prosecdef"] and row["private"] and row["runtime"]
        assert row["owner"] == "opengym_coach_executor"
        assert row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
    assert tuple(
        await observer.fetchrow(
            "SELECT rolcanlogin,rolsuper,rolbypassrls FROM pg_roles WHERE rolname='opengym_coach_executor'"
        )
    ) == (False, False, False)
