"""Actual import command against frozen files and a new isolated PostgreSQL target."""

import asyncio
import hashlib
import json
import os
import resource
import stat
import sys
from pathlib import Path

import asyncpg
import pytest
from import_fixtures import PASSWORD, SECRET
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server


async def command(
    tmp_path,
    environment,
    case="valid",
    *,
    target="new-a",
    source=None,
    file_limit=False,
):
    root = tmp_path / "targets"
    root.mkdir(mode=0o700, exist_ok=True)
    config = tmp_path / "import.json"
    config.write_text(
        json.dumps({"target_id": target, "target_root": str(root), "admin_uids": []})
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "opengym_platform.operations",
        "import",
        "--config",
        str(config),
        "--source",
        str(source) if source else f"/app/import-fixtures/{case}",
        "--target",
        target,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=(lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (1, 1)))
        if file_limit
        else None,
    )
    output, error = await asyncio.wait_for(process.communicate(), 35)
    assert error == b"", "IMPORT_UNSAFE_STDERR"
    assert "synthetic-import" not in output.decode()
    return process.returncode, json.loads(output)


async def prepare(observer, environment):
    await migration(environment, "up")
    await observer.execute(
        "COMMENT ON DATABASE opengym_dev IS 'opengym-import:new-a'; REVOKE CONNECT ON DATABASE opengym_dev FROM opengym_api_runtime"
    )
    await observer.close()


async def inspect():
    return await asyncpg.connect(
        host="platform-db",
        database="opengym_dev",
        user="opengym_platform_bootstrap",
        password="synthetic-lifecycle-bootstrap-password-only",
        ssl=False,
        timeout=5,
    )


@pytest.mark.asyncio
async def test_frozen_import_preserves_documents_ids_history_and_secret_references(
    deployment, tmp_path
):
    observer, environment = deployment
    await prepare(observer, environment)
    code, result = await command(tmp_path, environment)
    assert (code, result["code"]) == (0, "IMPORT_OK")
    observer = await inspect()
    try:
        assert json.loads(
            await observer.fetchval(
                "SELECT document FROM training.documents WHERE owner_id='A'"
            )
        )["_prior"] == {"notes": None}
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM training.documents WHERE owner_id='B'"
            )
            == 0
        )
        assert await observer.fetchval("SELECT max(id) FROM audit.events") == 41
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM coach.history_events WHERE job_id='job-old'"
            )
            == 2
        )
        assert await observer.fetchval("SELECT provider FROM coach.settings") == "codex"
        assert (
            await observer.fetchval(
                "SELECT secret_ref FROM coach.provider_settings WHERE provider='codex'"
            )
            is None
        )
        assert not await observer.fetchval(
            "SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"
        )
        assert not (tmp_path / "targets/new-a/data/coach-auth-A.json").exists()
        assert (
            len(list((tmp_path / "targets/new-a/data").glob("coach-key-*.json"))) == 1
        )
        assert await observer.fetchval("SELECT nextval('audit.events_id_seq')") == 42
        assert (
            await observer.fetchval(
                "SELECT nextval('coach.history_events_event_id_seq')"
            )
            == 3
        )
        assert (
            await observer.fetchval(
                "SELECT nextval('coach.instance_results_event_id_seq')"
            )
            == 2
        )
        assert await observer.fetchval("SELECT counter FROM identity.passkeys") == 17
        assert (
            await observer.fetchrow(
                "SELECT created_at,last_used_at FROM identity.passkeys"
            )
        )[:] == (None, None)
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 3
        )
        assert await observer.fetchval(
            "SELECT is_admin FROM identity.users WHERE id='A'"
        )
        assert (
            await observer.fetchval(
                "SELECT created_at FROM identity.users WHERE id='B'"
            )
            is None
        )
        assert (
            await observer.fetchval("SELECT count FROM coach.instance_daily_usage")
            == 19
        )
        assert await observer.fetchval("SELECT count FROM coach.daily_usage") == 4
        assert await observer.fetchval("SELECT consumed FROM identity.invitations")
        assert (
            await observer.fetchval("SELECT created_at FROM identity.invitations")
            is None
        )
        assert bytes(
            await observer.fetchval("SELECT code_digest FROM identity.device_links")
        ) == bytes.fromhex("cd" * 32)
        assert bytes(
            await observer.fetchval("SELECT code_digest FROM identity.password_resets")
        ) == bytes.fromhex("ab" * 32)
        assert (
            await observer.fetchval("SELECT proposal_id FROM coach.pending_proposals")
            == "proposal-old"
        )
        assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
        source = Path("/app/import-fixtures/valid")
        destination = tmp_path / "targets/new-a"
        for path in destination.rglob("*"):
            assert stat.S_IMODE(path.stat().st_mode) == (
                0o700 if path.is_dir() else 0o600
            )
        for name in ("session-secret", "coach-secret"):
            assert (destination / name).read_text() == SECRET
        for original in (source / "uploads").rglob("*"):
            if original.is_file():
                assert (
                    destination / "data" / original.relative_to(source)
                ).read_bytes() == original.read_bytes()
        # No promotion is performed by import. Opening only this disposable target is explicit test setup.
        await observer.execute(
            "GRANT CONNECT ON DATABASE opengym_dev TO opengym_api_runtime"
        )
        environment.update(
            {
                "PASSWORD_LOGIN": "1",
                "DATA_DIR": str(destination / "data"),
                "PLATFORM_SESSION_SECRET_FILE": str(destination / "session-secret"),
                "PLATFORM_COACH_SECRET_FILE": str(destination / "coach-secret"),
                "AUDIT_DAYS": "0",
                "MEDIA_UPLOADS": "1",
            }
        )
        async with server(environment) as client:
            login = await client.post(
                "/api/v1/login/password",
                json={"identifier": "alice", "password": PASSWORD},
            )
            assert login.status_code == 200
            assert login.json()["user"]["id"] == "A"
            data = await client.get("/api/v1/data")
            assert data.json()["rev"] == 7
            assert data.json()["state"]["workouts"][0]["id"] == "w-old"
            assert "_prior" not in data.json()["state"]
            assert (await client.get("/api/v1/coach/status")).json()["code"] == "off"
            assert (
                await client.post("/api/v1/coach/review", json={})
            ).status_code == 503
            assert (await client.get("/api/v1/push/status")).status_code == 200
            assert (await client.get("/api/v1/account/passkeys")).status_code == 200
            original = next((source / "uploads/A").glob("*.png"))
            download = await client.get(f"/api/v1/media/{original.stem}")
            assert download.status_code == 200
            assert download.content == original.read_bytes()
        assert await observer.fetchval("SELECT count FROM coach.daily_usage") == 4
        assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
    finally:
        await observer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "unicode",
        "nul",
        "utf16",
        "fractional",
        "orphan",
        "alias",
        "unknown",
        "log_detail",
        "bad_history",
        "bad_key",
        "bad_vapid",
        "current",
        "symlink",
    ],
)
async def test_unrepresentable_source_blocks_without_changing_source_or_new_target(
    deployment, tmp_path, case
):
    observer, environment = deployment
    await prepare(observer, environment)
    source = Path("/app/import-fixtures") / case
    before = {
        p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source.rglob("*")
        if p.is_file()
    }
    code, result = await command(tmp_path, environment, case)
    assert code == 1 and result["code"] == "IMPORT_BLOCKED"
    assert not (tmp_path / "targets/new-a").exists()
    assert before == {
        p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source.rglob("*")
        if p.is_file()
    }
    report = next((tmp_path / "targets").glob("import-report-*.json"))
    assert stat.S_IMODE(report.stat().st_mode) == 0o600
    assert "synthetic-import" not in report.read_text()
    observer = await inspect()
    try:
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0
        assert (
            await observer.fetchval("SELECT provider FROM coach.settings") == "fixture"
        )
        for sequence in (
            "audit.events_id_seq",
            "coach.history_events_event_id_seq",
            "coach.instance_results_event_id_seq",
        ):
            assert tuple(
                await observer.fetchrow(f"SELECT last_value,is_called FROM {sequence}")
            ) == (1, False)
    finally:
        await observer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        "ownership",
        "exposed",
        "populated",
        "lock",
        "existing_directory",
        "writable_source",
        "file_write",
    ],
)
async def test_wrong_or_busy_targets_and_file_failure_never_publish_or_overwrite(
    deployment, tmp_path, fault
):
    observer, environment = deployment
    await migration(environment, "up")
    await observer.execute(
        "COMMENT ON DATABASE opengym_dev IS 'opengym-import:new-a'; REVOKE CONNECT ON DATABASE opengym_dev FROM opengym_api_runtime"
    )
    if fault == "ownership":
        await observer.execute("COMMENT ON DATABASE opengym_dev IS 'foreign'")
    elif fault == "exposed":
        await observer.execute(
            "GRANT CONNECT ON DATABASE opengym_dev TO opengym_api_runtime"
        )
    elif fault == "populated":
        await observer.execute(
            "INSERT INTO identity.users(id,display_name) VALUES('sentinel','Foreign')"
        )
    elif fault == "lock":
        await observer.execute("SELECT pg_advisory_lock(728322)")
    if fault == "existing_directory":
        (tmp_path / "targets/new-a").mkdir(parents=True)
        (tmp_path / "targets/new-a/sentinel").write_text("preserved")
        os.chmod(tmp_path / "targets", 0o700)
    source = None
    if fault == "writable_source":
        import shutil

        source = tmp_path / "writable-source"
        shutil.copytree("/app/import-fixtures/valid", source)
    if fault != "lock":
        await observer.close()
    try:
        code, result = await command(
            tmp_path, environment, source=source, file_limit=fault == "file_write"
        )
        assert code == 1 and result["code"] == "IMPORT_BLOCKED"
        assert not (tmp_path / "targets/new-a/import.json").exists()
        if fault == "existing_directory":
            assert (tmp_path / "targets/new-a/sentinel").read_text() == "preserved"
    finally:
        if fault == "lock":
            await observer.close()
    observer = await inspect()
    try:
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == (
            1 if fault == "populated" else 0
        )
        assert (
            await observer.fetchval("SELECT provider FROM coach.settings") == "fixture"
        )
        for sequence in (
            "audit.events_id_seq",
            "coach.history_events_event_id_seq",
            "coach.instance_results_event_id_seq",
        ):
            assert tuple(
                await observer.fetchrow(f"SELECT last_value,is_called FROM {sequence}")
            ) == (1, False)
    finally:
        await observer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["http", "claude", "missing_null", "whole_number", "exponent_number"]
)
async def test_profile_secrets_deferred_selection_and_nulls_are_preserved(
    deployment, tmp_path, case
):
    observer, environment = deployment
    await prepare(observer, environment)
    assert await command(tmp_path, environment, case) == (0, {"code": "IMPORT_OK"})
    destination = tmp_path / "targets/new-a"
    observer = await inspect()
    try:
        if case == "http":
            assert (destination / "data/coach-auth-A.json").read_bytes() == Path(
                "/app/import-fixtures/http/coach-auth-A.json"
            ).read_bytes()
            from opengym_platform.coach.secrets import SecretFiles

            key = (destination / "coach-secret").read_text()
            assert key == SECRET
            # Reuse actual runtime credential resolution after import, with an explicit source key.
            os.environ["PLATFORM_COACH_SECRET_FILE"] = str(destination / "coach-secret")
            os.environ["DATA_DIR"] = str(destination / "data")
            try:
                resolved = SecretFiles().resolve(
                    {"provider": "openai", "auth_mode": "profile"}, "A"
                )
                assert (
                    resolved["ok"]
                    and resolved["key"] == "synthetic-import-provider-key"
                )
            finally:
                os.environ.pop("PLATFORM_COACH_SECRET_FILE")
                os.environ.pop("DATA_DIR")
        elif case == "claude":
            assert (
                await observer.fetchval("SELECT provider FROM coach.settings")
                == "claude"
            )
            assert not (destination / "data/coach-auth-A.json").exists()
        elif case == "missing_null":
            document = json.loads(
                await observer.fetchval("SELECT document FROM training.documents")
            )
            assert document == {"_rev": None, "_wid": None, "optional": None}
            assert "workouts" not in document
            assert tuple(
                await observer.fetchrow(
                    "SELECT revision,write_id FROM training.documents"
                )
            ) == (0, None)
        elif case == "whole_number":
            document = json.loads(
                await observer.fetchval("SELECT document FROM training.documents")
            )
            assert document == {"_rev": 7.0, "_wid": "whole"}
            assert (
                await observer.fetchval("SELECT revision FROM training.documents") == 7
            )
        else:
            document = json.loads(
                await observer.fetchval("SELECT document FROM training.documents")
            )
            assert document == {
                "_rev": 0,
                "number": 100000000000000000000,
                "fraction": 0.1,
                "flag": True,
                "list": [None, 1, False],
            }
            assert type(document["flag"]) is bool and type(document["list"][1]) is int
    finally:
        await observer.close()


@pytest.mark.asyncio
async def test_revoked_invitation_is_preserved_without_reopening_it(
    deployment, tmp_path
):
    observer, environment = deployment
    await prepare(observer, environment)
    assert await command(tmp_path, environment, "revoked") == (
        0,
        {"code": "IMPORT_OK"},
    )
    observer = await inspect()
    try:
        assert tuple(
            await observer.fetchrow(
                "SELECT code,consumed,revoked FROM identity.invitations"
            )
        ) == ("OLD", True, True)
    finally:
        await observer.close()


@pytest.mark.asyncio
async def test_target_id_cannot_escape_the_owned_directory(tmp_path):
    code, result = await command(tmp_path, os.environ.copy(), target="../escape")
    assert code == 2 and result == {"code": "IMPORT_BLOCKED", "reason": "TARGET_ID"}
    assert not (tmp_path / "escape").exists()
