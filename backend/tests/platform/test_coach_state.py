"""Q6 through real HTTP and restricted PostgreSQL, without provider credentials."""

import asyncio
import json
import shutil
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import A, B, wait_for_actor_locks
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server

OFF = {"error": "the Coach is not set up on this instance", "code": "off"}


@pytest.mark.asyncio
async def test_deferred_provider_preserves_imported_selection_without_work(identities):
    observer, environment = identities
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/coach/status", headers={"Authorization": f"Bearer {A}"}
        )
        assert response.status_code == 503
        assert response.json() == OFF
        assert "coach" not in (await client.get("/api/v1/config")).json()
        for provider, label in (
            ("claude", "Claude (Anthropic)"),
            ("codex", "Codex (OpenAI)"),
        ):
            await observer.execute(
                "INSERT INTO coach.provider_settings(provider,model,options,secret_ref,bound_owner_id) "
                "VALUES ($1,'imported-model','{}','protected-original-not-mounted','A') "
                "ON CONFLICT (provider) DO UPDATE SET model=excluded.model,options=excluded.options, "
                "secret_ref=excluded.secret_ref,bound_owner_id=excluded.bound_owner_id",
                provider,
            )
            await observer.execute(
                "UPDATE coach.settings SET enabled=true,provider=$1,auth_mode='profile',community=true",
                provider,
            )
            before = await observer.fetchrow(
                "SELECT row_to_json(s)::text AS settings, "
                "(SELECT jsonb_agg(to_jsonb(p))::text FROM coach.provider_settings p) AS providers "
                "FROM coach.settings s"
            )
            config = (await client.get("/api/v1/config")).json()["coach"]
            assert config == {
                "enabled": False,
                "provider": provider,
                "providerLabel": label,
                "authMode": "profile",
                "community": True,
            }
            for token in (A, B):
                for method, path in (
                    ("GET", "status"),
                    ("POST", "plan"),
                    ("POST", "review"),
                    ("POST", "debrief"),
                ):
                    response = await client.request(
                        method,
                        f"/api/v1/coach/{path}?owner_id=B",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    assert response.status_code == 503
                    assert response.json() == OFF
                    assert response.headers["cache-control"] == "no-store"
            after = await observer.fetchrow(
                "SELECT row_to_json(s)::text AS settings, "
                "(SELECT jsonb_agg(to_jsonb(p))::text FROM coach.provider_settings p) AS providers "
                "FROM coach.settings s"
            )
            assert after == before
            assert json.loads(after["settings"])["provider"] == provider
            assert await observer.fetchval("SELECT to_regclass('coach.jobs')") is None
            assert (
                await observer.fetchval("SELECT to_regclass('coach.daily_usage')")
                is None
            )
    async with server(environment) as client:
        assert (await client.get("/api/v1/config")).json()["coach"][
            "provider"
        ] == "codex"
        assert (
            await client.get("/api/v1/coach/status", headers={"Cookie": f"gymsid={A}"})
        ).json() == OFF


@pytest.mark.asyncio
async def test_coach_routes_revalidate_session_and_keep_csrf(identities):
    observer, environment = identities
    async with server(environment) as client:
        for method, path in (
            ("GET", "status"),
            ("POST", "plan"),
            ("POST", "review"),
            ("POST", "debrief"),
        ):
            for token in ("", "forged"):
                response = await client.request(
                    method,
                    f"/api/v1/coach/{path}",
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )
                assert response.status_code == 401
                assert response.json() == {"error": "not signed in"}
        response = await client.post(
            "/api/v1/coach/plan",
            headers={"Cookie": f"gymsid={A}", "Origin": "https://foreign.example"},
        )
        assert response.status_code == 403
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/coach/plan", headers={"Authorization": f"Bearer {A}"}
                )
            )
            await wait_for_actor_locks(observer, 1)
            await observer.execute(
                "UPDATE identity.users SET session_version=1 WHERE id='A'"
            )
        assert (await pending).status_code == 401
        assert (
            await client.get(
                "/api/v1/coach/status", headers={"Authorization": f"Bearer {B}"}
            )
        ).status_code == 503


@pytest.mark.asyncio
async def test_configuration_constraints_and_public_sql_acl(identities):
    observer, environment = identities
    for options in (
        [],
        {"token": "not-allowed"},
        {"baseUrl": {}},
        {"headers": "not-an-object"},
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            await observer.execute(
                "UPDATE coach.provider_settings SET options=$1::jsonb WHERE provider='claude'",
                json.dumps(options),
            )
    for statement in (
        "UPDATE coach.settings SET id=2",
        "UPDATE coach.settings SET provider='unknown'",
        "UPDATE coach.settings SET auth_mode='other'",
        "UPDATE coach.settings SET per_profile_daily=-1",
        "UPDATE coach.settings SET instance_daily=5001",
        "UPDATE coach.settings SET max_message_len=199",
        "UPDATE coach.settings SET max_output_tokens=65537",
    ):
        with pytest.raises(asyncpg.IntegrityConstraintViolationError):
            await observer.execute(statement)
    assert [
        tuple(row)
        for row in await observer.fetch("""
        SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner)
        FROM pg_class WHERE oid IN ('coach.settings'::regclass,'coach.provider_settings'::regclass)
        ORDER BY relname
    """)
    ] == [
        ("provider_settings", True, True, "opengym_schema_owner"),
        ("settings", True, True, "opengym_schema_owner"),
    ]
    function = await observer.fetchrow("""
        SELECT prosecdef,pg_get_userbyid(proowner) AS owner,proconfig,
            EXISTS (SELECT FROM aclexplode(proacl) a WHERE grantee=0) AS public
        FROM pg_proc WHERE oid='coach.public_disclosure()'::regprocedure
    """)
    assert tuple(function) == (
        True,
        "opengym_coach_executor",
        ["search_path=pg_catalog, pg_temp"],
        False,
    )
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        for statement in (
            "SELECT * FROM coach.settings",
            "SELECT * FROM coach.provider_settings",
            "UPDATE coach.settings SET enabled=true",
            "SET ROLE opengym_coach_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(statement)
        assert tuple(
            await runtime.fetchrow("SELECT * FROM coach.public_disclosure()")
        ) == (False, "fixture", "instance", False)
    finally:
        await runtime.close(timeout=5)


@pytest.mark.asyncio
async def test_config_migrates_previous_head_without_replaying_or_touching_training(
    deployment, tmp_path
):
    observer, environment = deployment
    package = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        package,
        ignore=shutil.ignore_patterns("p003_coach.py"),
    )
    await migration({**environment, "PYTHONPATH": str(package.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p002_media_gc"
    )
    await observer.execute("""INSERT INTO identity.users(id,display_name) VALUES ('A','Alice');
        INSERT INTO training.documents(owner_id,document) VALUES ('A','{"_rev":7,"workouts":[]}')""")
    await observer.execute("DROP ROLE opengym_coach_executor")
    await migration(environment, "bootstrap")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p003_coach"
    )
    assert json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    ) == {"_rev": 7, "workouts": []}
    assert await observer.fetchval("SELECT count(*) FROM coach.settings") == 1


@pytest.mark.asyncio
async def test_environment_kill_switch_hides_coach_without_mutating_selection(
    identities,
):
    observer, environment = identities
    await observer.execute("UPDATE coach.settings SET enabled=true,provider='claude'")
    async with server({**environment, "COACH_DISABLED": "ON"}) as client:
        assert "coach" not in (await client.get("/api/v1/config")).json()
        assert (
            await client.post(
                "/api/v1/coach/plan", headers={"Authorization": f"Bearer {A}"}
            )
        ).json() == OFF
    assert tuple(
        await observer.fetchrow("SELECT enabled,provider FROM coach.settings")
    ) == (True, "claude")
