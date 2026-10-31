"""Recoverable account deletion through restricted HTTP and PostgreSQL."""

import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from test_identity_session import A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration
from test_lifecycle import server as live_server


def paused_cleanup_app():
    from opengym_platform.administration.cleanup import Cleanup
    from opengym_platform.application import create_app

    async def paused(self):
        await asyncio.Event().wait()

    # Atomic-delete tests observe the commit independently of the separately tested worker.
    Cleanup.maintain = paused
    return create_app()


@asynccontextmanager
async def server(environment):
    environment = {
        **environment,
        "PYTHONPATH": str(Path(__file__).parent) + ":" + environment["PYTHONPATH"],
    }
    async with live_server(
        environment, factory="test_admin_delete:paused_cleanup_app"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_delete_denies_access_and_records_cleanup_atomically(identities):
    observer, environment = identities
    ref = "coach-key-" + "ab" * 16 + ".json"
    await observer.execute("""
        INSERT INTO identity.invitations VALUES('used','Historical','B',NULL,true,'A',NULL,false);
        UPDATE identity.users SET invited_by='used' WHERE id='A';
        INSERT INTO training.documents(owner_id,document) VALUES('A','{"_rev":7}'),('B','{"_rev":9}');
    """)
    await observer.execute(
        "UPDATE coach.provider_settings SET bound_owner_id='A',secret_ref=$1 WHERE provider='openai'",
        ref,
    )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/admin/user/delete",
            headers={"Authorization": f"Bearer {B}"},
            json={"id": "A", "owner_id": "B", "secret_refs": ["foreign"]},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "id": "A"}
        assert "no-store" == response.headers["Cache-Control"]
        for path in ("/me", "/data", "/coach/status", "/push/status"):
            denied = await client.get(
                "/api/v1" + path, headers={"Authorization": f"Bearer {A}"}
            )
            assert denied.status_code == 401, (path, denied.text)
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {B}"})
        ).status_code == 200
    assert (
        await observer.fetchval("SELECT count(*) FROM identity.users WHERE id='A'") == 0
    )
    assert json.loads(
        await observer.fetchval(
            "SELECT document FROM training.documents WHERE owner_id='B'"
        )
    ) == {"_rev": 9}
    task = await observer.fetchrow("SELECT * FROM administration.deletion_tasks")
    assert task["deleted_owner_id"] == "A" and task["secret_refs"] == [ref]
    assert (
        task["status"] == "pending"
        and task["attempts"] == 0
        and task["last_error_code"] is None
    )
    assert await observer.fetchval(
        "SELECT consumed FROM identity.invitations WHERE code='used'"
    )
    assert tuple(
        await observer.fetchrow(
            "SELECT secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='openai'"
        )
    ) == (None, None)


@pytest.mark.asyncio
async def test_guards_and_http_boundaries(identities):
    observer, environment = identities
    headers = {"Authorization": f"Bearer {B}"}
    async with server(environment) as client:
        for token, status in ((None, 401), ("forged", 401), (A, 403)):
            response = await client.post(
                "/api/v1/admin/user/delete",
                json={"id": "B"},
                headers={"Authorization": f"Bearer {token}"} if token else {},
            )
            assert response.status_code == status
        for target, status, error in (
            ("B", 400, "you cannot delete your own account"),
            ("missing", 404, "no such user"),
            (None, 404, "no such user"),
            ({}, 404, "no such user"),
            ("bad\x00id", 404, "no such user"),
        ):
            response = await client.post(
                "/api/v1/admin/user/delete", json={"id": target}, headers=headers
            )
            assert response.status_code == status and response.json() == {
                "error": error
            }
        for raw in ("{", "[]", '{"id":"A","x":NaN}'):
            assert (
                await client.post(
                    "/api/v1/admin/user/delete", content=raw, headers=headers
                )
            ).status_code == 400
        assert (
            await client.post(
                "/api/v1/admin/user/delete",
                content=b"x" * (5 * 1024 * 1024 + 1),
                headers=headers,
            )
        ).status_code == 413
        assert (
            await client.post(
                "/api/v1/admin/user/delete",
                json={"id": "A"},
                headers={"Cookie": f"gymsid={B}", "Origin": "https://foreign.example"},
            )
        ).status_code == 403
        # Another administrator may be deleted, unlike disable; the actor remains.
        await observer.execute(
            "INSERT INTO identity.users(id,display_name,is_admin) VALUES('C','Carol',true)"
        )
        response = await client.post(
            "/api/v1/admin/user/delete", json={"id": "C"}, headers=headers
        )
        assert response.json() == {"ok": True, "id": "C"}
    assert (
        await observer.fetchval("SELECT count(*) FROM administration.deletion_tasks")
        == 1
    )
    assert await observer.fetchval("SELECT count(*) FROM identity.users") == 2


@pytest.mark.asyncio
async def test_cascades_preserve_history_foreign_bytes_and_restart(
    identities, tmp_path
):
    observer, environment = identities
    data = tmp_path / "data"
    data.mkdir()
    environment["DATA_DIR"] = str(data)
    refs = ["coach-key-" + "ab" * 16 + ".json", "protected-original-reference"]
    for name in (*refs, "coach-auth-A.json", "coach-auth-B.json"):
        (data / name).write_text("synthetic-external-sentinel")
    await observer.execute("""
        INSERT INTO identity.invitations VALUES('used','Keep','B',NULL,true,'A',NULL,false);
        UPDATE identity.users SET invited_by='used' WHERE id='A';
        INSERT INTO identity.password_credentials VALUES('A','private-hash',NULL);
        INSERT INTO identity.login_aliases VALUES('alice','A',false,true,NULL);
        INSERT INTO identity.passkeys VALUES('credential','A','key',0,'{}',NULL,NULL,NULL);
        INSERT INTO identity.password_resets VALUES('A',decode(repeat('ab',32),'hex'),now()+interval '1 hour','B');
        INSERT INTO identity.device_links VALUES(decode(repeat('cd',32),'hex'),'A',now(),now()+interval '10 minutes');
        INSERT INTO training.documents VALUES('A','{"_rev":7}');
        INSERT INTO notifications.subscriptions VALUES('https://push.example/A','A','p','a',NULL,now());
        INSERT INTO notifications.delivery_state(owner_id) VALUES('A');
        INSERT INTO coach.profile_state(owner_id) VALUES('A');
        INSERT INTO coach.daily_usage VALUES('A',current_date,1);
        INSERT INTO coach.instance_daily_usage VALUES(current_date,1);
        INSERT INTO coach.pending_proposals(owner_id,document) VALUES('A','{"id":"p","kind":"review","expiresAt":12345}');
        INSERT INTO coach.history_events(owner_id,kind,outcome,occurred_at) VALUES('A','review','ready',now());
        CREATE SCHEMA audit;
        CREATE TABLE audit.events(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, actor_id text, target_id text);
        INSERT INTO audit.events(actor_id,target_id) VALUES('B','A');
    """)
    for provider, ref in zip(("openai", "codex"), refs, strict=True):
        await observer.execute(
            "UPDATE coach.provider_settings SET bound_owner_id='A',secret_ref=$1 WHERE provider=$2",
            ref,
            provider,
        )
    await observer.execute(
        "UPDATE coach.provider_settings SET bound_owner_id='B',secret_ref='foreign-secret' WHERE provider='gemini'"
    )
    async with server(environment) as client:
        # Insert after startup, which correctly retires preexisting interrupted jobs.
        await observer.execute(
            "INSERT INTO coach.jobs VALUES('A','old-job','review','manual','running',now(),0)"
        )
        assert (
            await client.post(
                "/api/v1/activity",
                json={"active": True},
                headers={"Authorization": f"Bearer {A}"},
            )
        ).status_code == 200
        response = await client.post(
            "/api/v1/admin/user/delete",
            json={"id": "A"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200
        assert [
            row["id"]
            for row in (
                await client.get(
                    "/api/v1/admin/users", headers={"Authorization": f"Bearer {B}"}
                )
            ).json()["users"]
        ] == ["B"]
    for table in (
        "identity.password_credentials",
        "identity.login_aliases",
        "identity.passkeys",
        "identity.password_resets",
        "identity.device_links",
        "training.documents",
        "notifications.subscriptions",
        "notifications.delivery_state",
        "coach.jobs",
        "coach.history_events",
        "coach.pending_proposals",
        "coach.profile_state",
        "coach.daily_usage",
    ):
        assert (
            await observer.fetchval(f"SELECT count(*) FROM {table} WHERE owner_id='A'")
            == 0
        )
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 1
    assert tuple(
        await observer.fetchrow("SELECT consumed,used_by FROM identity.invitations")
    ) == (True, "A")
    assert tuple(
        await observer.fetchrow("SELECT actor_id,target_id FROM audit.events")
    ) == ("B", "A")
    assert tuple(
        await observer.fetchrow(
            "SELECT secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='gemini'"
        )
    ) == ("foreign-secret", "B")
    assert await observer.fetchval(
        "SELECT secret_refs FROM administration.deletion_tasks"
    ) == sorted(refs)
    # 6.2 never unlinks external files; the durable pending task survives restart.
    async with server(environment) as client:
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {A}"})
        ).status_code == 401
    assert (
        await observer.fetchval("SELECT status FROM administration.deletion_tasks")
        == "pending"
    )
    assert all(
        path.read_text() == "synthetic-external-sentinel" for path in data.iterdir()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["task", "cascade"])
async def test_failure_rolls_back_disconnect_task_and_sql_then_retry(
    identities, failure
):
    observer, environment = identities
    await observer.execute(
        "UPDATE coach.provider_settings SET bound_owner_id='A',secret_ref='keep-reference' WHERE provider='openai'"
    )
    await observer.execute(
        "INSERT INTO training.documents VALUES('A','{" + '"_rev":7' + "}')"
    )
    table, event = (
        ("administration.deletion_tasks", "INSERT")
        if failure == "task"
        else ("training.documents", "DELETE")
    )
    await observer.execute(f"""CREATE FUNCTION public.fail_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'synthetic-failure'; END $$;
        CREATE TRIGGER injected BEFORE {event} ON {table} FOR EACH ROW EXECUTE FUNCTION public.fail_delete();""")
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/admin/user/delete",
            json={"id": "A"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 500 and response.json() == {
            "error": "server error"
        }
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM administration.deletion_tasks"
            )
            == 0
        )
        assert await observer.fetchval("SELECT count(*) FROM training.documents") == 1
        assert tuple(
            await observer.fetchrow(
                "SELECT secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='openai'"
            )
        ) == ("keep-reference", "A")
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {A}"})
        ).status_code == 200
        await observer.execute(f"DROP TRIGGER injected ON {table}")
        response = await client.post(
            "/api/v1/admin/user/delete",
            json={"id": "A"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200
    assert (
        await observer.fetchval("SELECT count(*) FROM administration.deletion_tasks")
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["revoked", "demoted", "disabled", "deleted", "expiry"]
)
async def test_stale_admin_waiting_on_target_cannot_delete(identities, change):
    observer, environment = identities
    async with server(environment) as client:
        expiry = await observer.fetchval(
            "SELECT clock_timestamp()+interval '0.5 seconds'"
        )
        token = (
            signed(f"B:{int(expiry.timestamp() * 1000)}:3") if change == "expiry" else B
        )
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            request = asyncio.create_task(
                client.post(
                    "/api/v1/admin/user/delete",
                    json={"id": "A"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            )
            async with asyncio.timeout(1):
                while not await observer.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%administration.%'"
                ):
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    await asyncio.sleep(0.01)
            if change == "expiry":
                await observer.execute(
                    "SELECT pg_sleep(greatest(0,extract(epoch FROM ($1::timestamptz-clock_timestamp()))))",
                    expiry,
                )
            elif change == "deleted":
                await observer.execute("DELETE FROM identity.users WHERE id='B'")
            else:
                assignment = {
                    "revoked": "session_version=4",
                    "demoted": "is_admin=false",
                    "disabled": "disabled=true",
                }[change]
                await observer.execute(
                    f"UPDATE identity.users SET {assignment} WHERE id='B'"
                )
        response = await request
        assert response.status_code == (403 if change == "demoted" else 401)
    assert (
        await observer.fetchval("SELECT count(*) FROM identity.users WHERE id='A'") == 1
    )
    assert (
        await observer.fetchval("SELECT count(*) FROM administration.deletion_tasks")
        == 0
    )


@pytest.mark.asyncio
async def test_concurrent_delete_creates_one_task(identities):
    observer, environment = identities
    async with server(environment) as client:
        responses = await asyncio.gather(
            *(
                client.post(
                    "/api/v1/admin/user/delete",
                    json={"id": "A"},
                    headers={"Authorization": f"Bearer {B}"},
                )
                for _ in range(2)
            )
        )
        assert sorted(response.status_code for response in responses) == [200, 404]
    assert (
        await observer.fetchval("SELECT count(*) FROM administration.deletion_tasks")
        == 1
    )


@pytest.mark.asyncio
async def test_upgrade_privileges_and_transaction_local_cleanup(deployment, tmp_path):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns(
            "p004_external_cleanup.py", "p004_deletion_tasks.py"
        ),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p005_delivery"
    )
    await observer.execute("""
        INSERT INTO identity.users(id,display_name,is_admin) VALUES('A','Alice',false),('B','Bob',true);
        UPDATE coach.provider_settings SET secret_ref='retained',bound_owner_id='A' WHERE provider='codex';
    """)
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_external_cleanup"
    )
    assert tuple(
        await observer.fetchrow(
            "SELECT secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='codex'"
        )
    ) == ("retained", "A")
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        for sql in (
            "SELECT * FROM administration.deletion_tasks",
            "DELETE FROM identity.users WHERE id='A'",
            "SET ROLE opengym_administration_executor",
            "SET ROLE opengym_coach_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(sql)
        assert (
            json.loads(
                await runtime.fetchval(
                    "SELECT coach.disconnect_owner('A',0,now()+interval '1 day','B')"
                )
            )
            == {}
        )
        assert (
            await runtime.fetchval(
                "SELECT coach.disconnect_owner('B',99,now()+interval '1 day','A')"
            )
            is None
        )
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await runtime.fetchval(
                "SELECT administration.delete_user('B',0,now()+interval '1 day','A',$1)",
                uuid4(),
            )
        # A disconnection rolled back cannot leak its cleanup references to the next borrower.
        transaction = runtime.transaction()
        await transaction.start()
        await runtime.execute(
            "SELECT coach.disconnect_owner('B',0,now()+interval '1 day','A')"
        )
        assert json.loads(
            await runtime.fetchval("SELECT current_setting('app.deletion_cleanup')")
        )["refs"] == ["retained"]
        await transaction.rollback()
        assert await runtime.fetchval(
            "SELECT current_setting('app.deletion_cleanup',true)"
        ) in (None, "")
        assert json.loads(
            await runtime.fetchval(
                "SELECT administration.delete_user('B',0,now()+interval '1 day','B',$1)",
                uuid4(),
            )
        ) == {"error": "you cannot delete your own account"}
        async with runtime.transaction():
            await runtime.execute(
                "SELECT coach.disconnect_owner('B',0,now()+interval '1 day','A')"
            )
            result = await runtime.fetchval(
                "SELECT administration.delete_user('B',0,now()+interval '1 day','A',$1)",
                uuid4(),
            )
            assert json.loads(result) == {"ok": True, "id": "A"}
            assert (
                await runtime.fetchval(
                    "SELECT current_setting('app.deletion_cleanup',true)"
                )
                == ""
            )
        assert await runtime.fetchval(
            "SELECT current_setting('app.deletion_cleanup',true)"
        ) in (None, "")
    finally:
        await runtime.close()
    assert tuple(
        await observer.fetchrow(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='administration.deletion_tasks'::regclass"
        )
    ) == (True, True)
    for signature, owner in (
        (
            "coach.disconnect_owner(text,bigint,timestamptz,text)",
            "opengym_coach_executor",
        ),
        (
            "administration.delete_user(text,bigint,timestamptz,text,uuid)",
            "opengym_administration_executor",
        ),
    ):
        row = await observer.fetchrow(
            """SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,
            NOT EXISTS(SELECT FROM aclexplode(proacl) WHERE grantee=0) AS private,
            has_function_privilege('opengym_api_runtime',oid,'EXECUTE') AS executable
            FROM pg_proc WHERE oid=$1::regprocedure""",
            signature,
        )
        assert tuple(row) == (
            True,
            ["search_path=pg_catalog, pg_temp"],
            owner,
            True,
            True,
        )
    assert await observer.fetchval(
        "SELECT secret_refs FROM administration.deletion_tasks"
    ) == ["retained"]


@pytest.mark.asyncio
async def test_expiry_after_coach_lock_wait_rolls_back(identities):
    observer, environment = identities
    await observer.execute(
        "UPDATE coach.provider_settings SET secret_ref='keep',bound_owner_id='A' WHERE provider='openai'"
    )
    async with server(environment) as client:
        expiry = await observer.fetchval(
            "SELECT clock_timestamp()+interval '0.7 seconds'"
        )
        token = signed(f"B:{int(expiry.timestamp() * 1000)}:3")
        async with observer.transaction():
            await observer.execute("SELECT 1 FROM coach.settings FOR UPDATE")
            request = asyncio.create_task(
                client.post(
                    "/api/v1/admin/user/delete",
                    json={"id": "A"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            )
            async with asyncio.timeout(1):
                while not await observer.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%coach.disconnect_owner%'"
                ):
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    await asyncio.sleep(0.01)
            await observer.execute(
                "SELECT pg_sleep(greatest(0,extract(epoch FROM ($1::timestamptz-clock_timestamp()))))",
                expiry,
            )
        response = await request
        assert response.status_code == 401
    assert (
        await observer.fetchval("SELECT count(*) FROM administration.deletion_tasks")
        == 0
    )
    assert tuple(
        await observer.fetchrow(
            "SELECT secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='openai'"
        )
    ) == ("keep", "A")
