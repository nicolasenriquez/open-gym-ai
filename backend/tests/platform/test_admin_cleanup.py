"""External cleanup through real HTTP, restricted SQL and private operator commands."""

import asyncio
import hashlib
import json
import os
import shutil
import signal
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import server


@pytest.mark.asyncio
async def test_worker_completes_deleted_owner_only(identities, tmp_path):
    observer, environment = identities
    data = tmp_path / "data"
    environment["DATA_DIR"] = str(data)
    for owner in ("A", "B"):
        directory = data / "uploads" / owner
        directory.mkdir(parents=True)
        (directory / ("ab" * 32 + ".jpg")).write_bytes(b"private synthetic bytes")
        (directory / ".gc.json").write_text("{}")
        (data / f"coach-auth-{owner}.json").write_text("synthetic personal credential")
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/admin/user/delete",
            headers={"Authorization": f"Bearer {B}"},
            json={"id": "A"},
        )
        assert response.json() == {"ok": True, "id": "A"}
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {A}"})
        ).status_code == 401
        async with asyncio.timeout(8):
            while True:
                task = await observer.fetchrow(
                    "SELECT * FROM administration.deletion_tasks"
                )
                if task["status"] == "done":
                    break
                await asyncio.sleep(0.05)
    assert not (data / "uploads" / "A").exists()
    assert not (data / "coach-auth-A.json").exists()
    assert (
        data / "uploads" / "B" / ("ab" * 32 + ".jpg")
    ).read_bytes() == b"private synthetic bytes"
    assert (data / "coach-auth-B.json").read_text() == "synthetic personal credential"
    async with server(environment):
        await asyncio.sleep(1.2)
    assert (
        await observer.fetchval("SELECT attempts FROM administration.deletion_tasks")
        == 1
    )


@pytest.mark.asyncio
async def test_cleanup_during_real_upload_cannot_publish_or_recreate_deleted_bytes(
    identities, tmp_path
):
    observer, environment = identities
    data = tmp_path / "data"
    environment.update(DATA_DIR=str(data), MEDIA_UPLOADS="1", MEDIA_MIN_FREE_MB="0")
    payload = b"\xff\xd8\xffsynthetic-inflight-upload"
    digest = hashlib.sha256(payload).hexdigest()
    resume = asyncio.Event()

    async def stream():
        yield payload[:3]
        await resume.wait()
        yield payload[3:]

    async with server(environment) as client:
        upload = asyncio.create_task(
            client.put(
                f"/api/v1/media/{digest}",
                headers={"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"},
                content=stream(),
                timeout=10,
            )
        )
        try:
            async with asyncio.timeout(4):
                while not list((data / "uploads/A/.tmp").glob("*")):
                    await asyncio.sleep(0.02)
            response = await client.post(
                "/api/v1/admin/user/delete",
                headers={"Authorization": f"Bearer {B}"},
                json={"id": "A"},
            )
            assert response.status_code == 200
            async with asyncio.timeout(5):
                while (
                    await observer.fetchval(
                        "SELECT status FROM administration.deletion_tasks"
                    )
                    != "done"
                ):
                    await asyncio.sleep(0.05)
        finally:
            resume.set()
        assert (await upload).status_code == 401
        assert not (data / "uploads/A").exists()
        assert (
            await client.get(
                f"/api/v1/media/{digest}", headers={"Authorization": f"Bearer {B}"}
            )
        ).status_code == 404


async def cli(environment, action, task=None):
    runtime = {
        **environment,
        "PLATFORM_DB_PASSWORD_FILE": environment["PLATFORM_RUNTIME_PASSWORD_FILE"],
    }
    runtime.pop("PLATFORM_MIGRATOR_PASSWORD_FILE", None)
    runtime.pop("PLATFORM_RUNTIME_PASSWORD_FILE", None)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.administration.cleanup",
        action,
        *([str(task)] if task is not None else []),
        env=runtime,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, diagnostic = await asyncio.wait_for(process.communicate(), 15)
    assert b"synthetic-" not in output + diagnostic
    return process.returncode, json.loads(output)


async def delete_paused(environment):
    from test_admin_delete import server as paused_server

    async with paused_server(environment) as client:
        response = await client.post(
            "/api/v1/admin/user/delete",
            headers={"Authorization": f"Bearer {B}"},
            json={"id": "A"},
        )
        assert response.json() == {"ok": True, "id": "A"}
    runtime = await runtime_connection(environment)
    try:
        async with asyncio.timeout(3):
            while not await runtime.fetchval(
                "SELECT clock_timestamp()>=(administration.cleanup_status(NULL)->0->>'next_attempt_at')::timestamptz"
            ):
                await asyncio.sleep(0.02)
    finally:
        await runtime.close()


async def runtime_connection(environment):
    return await asyncpg.connect(
        host="platform-db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )


@pytest.mark.asyncio
async def test_durable_bounded_backoff_partial_cleanup_and_operator_retry(
    identities, tmp_path
):
    observer, environment = identities
    data = tmp_path / "data"
    environment["DATA_DIR"] = str(data)
    directory = data / "uploads" / "A"
    directory.mkdir(parents=True)
    (directory / "sentinel.jpg").write_bytes(b"synthetic private bytes")
    secret = data / "coach-auth-A.json"
    secret.write_text("synthetic personal key")
    await delete_paused(environment)
    task = await observer.fetchval("SELECT id FROM administration.deletion_tasks")
    first = await observer.fetchrow(
        "SELECT created_at,next_attempt_at FROM administration.deletion_tasks"
    )
    assert (
        0.9 <= (first["next_attempt_at"] - first["created_at"]).total_seconds() <= 1.1
    )
    await observer.execute(
        "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
    )
    directory.chmod(0o500)
    try:
        for attempt, seconds in enumerate((5, 15, 60, 300, 300), 1):
            before = await observer.fetchval("SELECT clock_timestamp()")
            code, view = await cli(environment, "run", task)
            assert code == 1 and view[0]["status"] == "retry"
            row = await observer.fetchrow("SELECT * FROM administration.deletion_tasks")
            assert row["attempts"] == attempt and row["last_error_code"] == "media"
            assert (
                seconds
                <= (row["next_attempt_at"] - before).total_seconds()
                < seconds + 3
            )
            assert view[0]["operator_required"] == (attempt == 5)
            assert not secret.exists(), "partial progress is safe to repeat"
            assert (directory / "sentinel.jpg").exists()
            await observer.execute(
                "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
            )
        directory.chmod(0o700)
        assert (await cli(environment, "run", task))[0] == 1
        assert (
            await observer.fetchval(
                "SELECT attempts FROM administration.deletion_tasks"
            )
            == 5
        )
        code, view = await cli(environment, "status")
        assert code == 0 and len(view) == 1 and view[0]["operator_required"]
        assert not {"secret_refs", "token", "data"} & view[0].keys()
        assert (await cli(environment, "retry", task))[1][0]["status"] == "pending"
        await observer.execute(
            "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
        )
        code, view = await cli(environment, "run", task)
        assert code == 0 and view[0]["status"] == "done" and view[0]["attempts"] == 1
        assert not directory.exists()
        assert (await cli(environment, "retry", task))[1][0]["status"] == "done"
        assert (await cli(environment, "run", task))[1][0]["attempts"] == 1
    finally:
        if directory.exists():
            directory.chmod(0o700)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "link", ["data", "uploads", "owner", "temporary", "file", "secret"]
)
async def test_unsafe_paths_remain_pending_and_foreign_bytes_survive(
    identities, tmp_path, link
):
    observer, environment = identities
    data = tmp_path / "data"
    environment["DATA_DIR"] = str(data)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_bytes(b"foreign bytes")
    data.mkdir()
    uploads = data / "uploads"
    uploads.mkdir()
    owner = uploads / "A"
    owner.mkdir()
    if link == "data":
        owner.rmdir()
        uploads.rmdir()
        data.rmdir()
        data.symlink_to(foreign, target_is_directory=True)
    elif link == "uploads":
        owner.rmdir()
        uploads.rmdir()
        uploads.symlink_to(foreign, target_is_directory=True)
    elif link == "owner":
        owner.rmdir()
        owner.symlink_to(foreign, target_is_directory=True)
    elif link == "temporary":
        (owner / ".tmp").symlink_to(foreign, target_is_directory=True)
    elif link == "file":
        (owner / "bad.jpg").symlink_to(foreign / "sentinel")
    else:
        (data / "coach-auth-A.json").symlink_to(foreign / "sentinel")
    await delete_paused(environment)
    task = await observer.fetchval("SELECT id FROM administration.deletion_tasks")
    code, view = await cli(environment, "run", task)
    assert code == 1 and view[0]["status"] == "retry"
    assert (foreign / "sentinel").read_bytes() == b"foreign bytes"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conflict",
    [
        "shared",
        "recreated",
        "legacy_collision",
        "legacy_deleted_collision",
        "foreign_personal",
        "unknown_reference",
    ],
)
async def test_owner_and_reference_conflicts_never_delete_foreign_material(
    identities, tmp_path, conflict
):
    observer, environment = identities
    data = tmp_path / "data"
    data.mkdir()
    environment["DATA_DIR"] = str(data)
    ref = "coach-key-" + "ab" * 16 + ".json"
    if conflict == "foreign_personal":
        ref = "coach-auth-B.json"
    elif conflict == "unknown_reference":
        ref = "protected-original-reference"
    (data / ref).write_bytes(b"preserve referenced bytes")
    await observer.execute(
        "UPDATE coach.provider_settings SET bound_owner_id='A',secret_ref=$1 WHERE provider='openai'",
        ref,
    )
    await delete_paused(environment)
    if conflict == "shared":
        await observer.execute(
            "UPDATE coach.provider_settings SET bound_owner_id='B',secret_ref=$1 WHERE provider='anthropic'",
            ref,
        )
    elif conflict in {"recreated", "legacy_collision"}:
        await observer.execute(
            "INSERT INTO identity.users(id,display_name) VALUES($1,'new account')",
            "A" if conflict == "recreated" else "A!",
        )
    elif conflict == "legacy_deleted_collision":
        await observer.execute(
            """INSERT INTO administration.deletion_tasks
            (id,deleted_owner_id,created_at,status,attempts,secret_refs)
            VALUES($1,'A!',clock_timestamp(),'pending',0,'{}')""",
            uuid4(),
        )
        directory = data / "uploads/A"
        directory.mkdir(parents=True)
        (directory / "foreign.jpg").write_bytes(b"legacy foreign owner bytes")
    task = await observer.fetchval(
        "SELECT id FROM administration.deletion_tasks WHERE deleted_owner_id='A'"
    )
    code, view = await cli(environment, "run", task)
    assert code == 1 and view[0]["status"] == "retry"
    assert (data / ref).read_bytes() == b"preserve referenced bytes"
    if conflict == "legacy_deleted_collision":
        assert (
            data / "uploads/A/foreign.jpg"
        ).read_bytes() == b"legacy foreign owner bytes"


@pytest.mark.asyncio
async def test_claim_survives_restart_and_stale_or_concurrent_attempt_cannot_finish(
    identities, tmp_path
):
    observer, environment = identities
    environment["DATA_DIR"] = str(tmp_path / "absent")
    await delete_paused(environment)
    task = await observer.fetchval("SELECT id FROM administration.deletion_tasks")
    runtime = await runtime_connection(environment)
    try:
        claimed = await runtime.fetchrow(
            "SELECT * FROM administration.claim_cleanup($1)", task
        )
        assert claimed["attempt"] == 1
    finally:
        await runtime.close()
    await observer.execute(
        "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()+interval '1 hour'"
    )
    assert (await cli(environment, "run", task))[1][0]["attempts"] == 1
    await observer.execute(
        "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
    )
    runtime = await runtime_connection(environment)
    try:
        claimed = await runtime.fetchrow(
            "SELECT * FROM administration.claim_cleanup($1)", task
        )
        assert claimed["attempt"] == 2
        assert not await runtime.fetchval(
            "SELECT administration.finish_cleanup($1,1,NULL)", task
        )
        assert not await runtime.fetch(
            "SELECT * FROM administration.lock_cleanup($1,1)", task
        )
    finally:
        await runtime.close()
    await observer.execute(
        "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
    )
    results = await asyncio.gather(
        cli(environment, "run", task), cli(environment, "run", task)
    )
    # A SKIP LOCKED loser may observe the preceding committed attempt before the winner commits.
    assert all(view[0]["attempts"] in (2, 3) for _, view in results)
    assert (
        await observer.fetchval("SELECT status FROM administration.deletion_tasks")
        == "done"
    )
    assert (
        await observer.fetchval("SELECT attempts FROM administration.deletion_tasks")
        == 3
    )


@pytest.mark.asyncio
async def test_cleanup_catalog_is_restricted_and_failed_completion_can_retry(
    identities, tmp_path
):
    observer, environment = identities
    environment["DATA_DIR"] = str(tmp_path / "absent")
    await delete_paused(environment)
    task = await observer.fetchval("SELECT id FROM administration.deletion_tasks")
    runtime = await runtime_connection(environment)
    try:
        for query in (
            "SELECT * FROM administration.deletion_tasks",
            "UPDATE administration.deletion_tasks SET status='done'",
            "SET ROLE opengym_administration_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(query)
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await runtime.fetchval(
                "SELECT administration.finish_cleanup($1,1,'synthetic-secret-details')",
                task,
            )
        for name, args in (
            ("claim_cleanup", "uuid"),
            ("lock_cleanup", "uuid,integer"),
            ("finish_cleanup", "uuid,integer,text"),
            ("cleanup_status", "uuid"),
            ("retry_cleanup", "uuid"),
        ):
            row = await observer.fetchrow(
                """SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,
                has_function_privilege('opengym_api_runtime',oid,'EXECUTE') AS runtime,
                EXISTS(SELECT FROM aclexplode(proacl) WHERE grantee=0 AND privilege_type='EXECUTE') AS public
                FROM pg_proc WHERE oid=$1::regprocedure""",
                f"administration.{name}({args})",
            )
            assert row["prosecdef"] and row["runtime"] and not row["public"]
            assert row["owner"] == "opengym_administration_executor" and row[
                "proconfig"
            ] == ["search_path=pg_catalog, pg_temp"]
        assert tuple(
            await observer.fetchrow(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='administration.deletion_tasks'::regclass"
            )
        ) == (True, True)
    finally:
        await runtime.close()
    await observer.execute("""CREATE FUNCTION administration.synthetic_fail_done() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.status='done' THEN RAISE EXCEPTION 'synthetic failure'; END IF; RETURN NEW; END $$;
        CREATE TRIGGER synthetic_fail_done BEFORE UPDATE ON administration.deletion_tasks FOR EACH ROW EXECUTE FUNCTION administration.synthetic_fail_done();""")
    code, view = await cli(environment, "run", task)
    assert code == 1 and view == {"code": "PLATFORM_CLEANUP_FAILED"}
    assert (
        await observer.fetchval("SELECT attempts FROM administration.deletion_tasks")
        == 1
    )
    assert (
        await observer.fetchval("SELECT status FROM administration.deletion_tasks")
        == "retry"
    )
    await observer.execute(
        "DROP TRIGGER synthetic_fail_done ON administration.deletion_tasks; UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
    )
    assert (await cli(environment, "run", task))[1][0]["status"] == "done"


@pytest.mark.asyncio
async def test_previous_head_tasks_survive_upgrade_and_rerun(deployment, tmp_path):
    from test_lifecycle import migration

    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p004_external_cleanup.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_deletion_tasks"
    )
    task = uuid4()
    await observer.execute(
        """INSERT INTO administration.deletion_tasks
        VALUES($1,'deleted',clock_timestamp(),'retry',3,'secret',ARRAY['protected-reference'])""",
        task,
    )
    await migration(environment, "up")
    await migration(environment, "up")
    row = await observer.fetchrow("SELECT * FROM administration.deletion_tasks")
    assert row["id"] == task and row["attempts"] == 3 and row["status"] == "retry"
    assert (
        row["secret_refs"] == ["protected-reference"]
        and row["last_error_code"] == "secret"
    )
    assert row["next_attempt_at"] is not None
    environment["DATA_DIR"] = str(tmp_path / "absent")
    assert (await cli(environment, "run", task))[1][0]["status"] == "retry"
    await observer.execute("UPDATE alembic_version SET version_num='unknown'")
    assert (await cli(environment, "retry", task)) == (
        1,
        {"code": "PLATFORM_CLEANUP_FAILED"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_operator_wait_revalidates_foreign_reference_and_cancellation_preserves_attempt(
    identities, tmp_path, cancel
):
    observer, environment = identities
    data = tmp_path / "data"
    data.mkdir()
    environment["DATA_DIR"] = str(data)
    ref = "coach-key-" + "cd" * 16 + ".json"
    (data / ref).write_bytes(b"foreign-reference-sentinel")
    await observer.execute(
        "UPDATE coach.provider_settings SET secret_ref=$1,bound_owner_id='A' WHERE provider='openai'",
        ref,
    )
    await delete_paused(environment)
    task = await observer.fetchval("SELECT id FROM administration.deletion_tasks")
    await observer.execute("SELECT pg_advisory_lock(728323)")
    runtime = {
        **environment,
        "PLATFORM_DB_PASSWORD_FILE": environment["PLATFORM_RUNTIME_PASSWORD_FILE"],
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.administration.cleanup",
        "run",
        str(task),
        env=runtime,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(5):
            while not await observer.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%lock_cleanup%'"
            ):
                await asyncio.sleep(0.02)
        assert (
            await observer.fetchval(
                "SELECT attempts FROM administration.deletion_tasks"
            )
            == 1
        )
        if cancel:
            process.send_signal(signal.SIGTERM)
            await asyncio.wait_for(process.communicate(), 5)
        await observer.execute(
            "UPDATE coach.provider_settings SET secret_ref=$1,bound_owner_id='B' WHERE provider='anthropic'",
            ref,
        )
    finally:
        await observer.execute("SELECT pg_advisory_unlock(728323)")
        try:
            output, diagnostic = await asyncio.wait_for(process.communicate(), 5)
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()
    assert (data / ref).read_bytes() == b"foreign-reference-sentinel"
    await observer.execute(
        "UPDATE administration.deletion_tasks SET next_attempt_at=clock_timestamp()-interval '1 second'"
    )
    if cancel:
        code, view = await cli(environment, "run", task)
    else:
        assert b"synthetic-" not in output + diagnostic
        code, view = process.returncode, json.loads(output)
    assert code == 1 and view[0]["attempts"] == (2 if cancel else 1)
    assert view[0]["last_error_code"] == "secret"
    assert (data / ref).read_bytes() == b"foreign-reference-sentinel"


@pytest.mark.asyncio
async def test_unknown_filesystem_failure_keeps_safe_pending_status(
    identities, tmp_path, monkeypatch
):
    from opengym_platform.administration.cleanup import Cleanup
    from opengym_platform.coach.secrets import SecretFiles
    from opengym_platform.core.database import Database

    observer, environment = identities
    data = tmp_path / "data"
    data.mkdir()
    (data / "coach-auth-A.json").write_text("synthetic-private-content")
    environment["DATA_DIR"] = str(data)
    await delete_paused(environment)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()
    try:

        def broken(*args, **kwargs):
            raise RuntimeError("synthetic-private-error-details")

        with monkeypatch.context() as fault:
            fault.setattr(os, "unlink", broken)
            assert await Cleanup(database, SecretFiles()).run_one()
        row = await observer.fetchrow(
            "SELECT status,attempts,last_error_code FROM administration.deletion_tasks"
        )
        assert tuple(row) == ("retry", 1, "internal")
        assert (data / "coach-auth-A.json").read_text() == "synthetic-private-content"
        async with database.transaction() as handle:
            clean = await handle.fetch(
                "SELECT current_user,current_setting('app.owner_id',true) AS owner"
            )
            assert (
                clean[0]["current_user"] == "opengym_api_runtime"
                and not clean[0]["owner"]
            )
    finally:
        await database.close()
