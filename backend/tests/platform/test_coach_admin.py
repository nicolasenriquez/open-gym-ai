"""Coach administration through HTTP and least-privilege PostgreSQL."""

import asyncio
import base64
import hashlib
import hmac
import json
import shutil
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import asyncpg
import pytest
from test_coach_http import REVIEW, STATE, completed, provider
from test_coach_jobs import runtime_connection
from test_identity_session import SECRET, A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server


def test_blank_coach_key_is_rejected_before_application_startup(monkeypatch, tmp_path):
    from opengym_platform.application import create_app

    session = tmp_path / "session"
    session.write_text(SECRET)
    key = tmp_path / "coach_secret"
    key.write_text(" " * 32)
    monkeypatch.setenv("PLATFORM_SESSION_SECRET_FILE", str(session))
    monkeypatch.setenv("PLATFORM_COACH_SECRET_FILE", str(key))
    with pytest.raises(ValueError):
        create_app()


@pytest.mark.asyncio
async def test_admin_configuration_is_authorized_and_preserves_provider_settings(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        for token, status in ((None, 401), (A, 403), (B, 200)):
            response = await client.get(
                "/api/v1/admin/coach",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            )
            assert response.status_code == status, response.text
        response = await client.post(
            "/api/v1/admin/coach/config",
            json={
                "provider": "compatible",
                "model": "private-model",
                "baseUrl": "http://127.0.0.1:9/v1/",
                "headers": {"X-Title": "gym"},
                "enabled": True,
                "maxMessageLen": 5000,
            },
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True}
        response = await client.post(
            "/api/v1/admin/coach/config",
            json={"provider": "openai", "model": "another-model"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200, response.text
        response = await client.post(
            "/api/v1/admin/coach/config",
            json={"provider": "compatible"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200, response.text
        view = (
            await client.get(
                "/api/v1/admin/coach", headers={"Authorization": f"Bearer {B}"}
            )
        ).json()
        assert view["model"] == "private-model"
        assert view["models"]["openai"] == "another-model"
        assert view["headers"] == {"x-title": "gym"}
        assert view["baseUrl"] == "http://127.0.0.1:9/v1"
        assert view["maxMessageLen"] == 4000
        assert view["enabled"] is True
    assert json.loads(
        await observer.fetchval(
            "SELECT options FROM coach.provider_settings WHERE provider='compatible'"
        )
    ) == {"baseUrl": "http://127.0.0.1:9/v1", "headers": {"x-title": "gym"}}


@pytest.mark.asyncio
async def test_connected_key_is_external_encrypted_and_used_only_by_authorized_jobs(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    directory = tmp_path / "coach_data"
    directory.mkdir()
    environment.update(DATA_DIR=str(directory), PLATFORM_COACH_SECRET_FILE=str(secret))
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(STATE),
    )
    wire = {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }
    async with provider([(200, wire)]) as (base, calls):
        await observer.execute(
            "UPDATE coach.settings SET enabled=true,provider='openai'"
        )
        await observer.execute(
            "UPDATE coach.provider_settings SET model='private-model',options=$1::jsonb WHERE provider='openai'",
            json.dumps({"baseUrl": base}),
        )
        async with server(environment) as client:
            response = await client.post(
                "/api/v1/admin/coach/connect",
                json={
                    "type": "apikey",
                    "token": "synthetic-admin-key-only",
                    "account": "Metered account",
                },
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.status_code == 200, response.text
            ref = await observer.fetchval(
                "SELECT secret_ref FROM coach.provider_settings WHERE provider='openai'"
            )
            record = (directory / ref).read_text()
            assert "synthetic-admin-key-only" not in record
            assert (directory / ref).stat().st_mode & 0o777 == 0o600
            account = (
                await client.get(
                    "/api/v1/coach/account?owner_id=B",
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).json()
            assert account == {
                "mode": "instance",
                "provider": "openai",
                "providerLabel": "OpenAI API",
                "account": "Metered account",
                "connected": True,
                "reason": None,
                "message": None,
            }
            result = await client.post(
                "/api/v1/coach/review",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert result.status_code == 202, result.text
            result = await completed(client)
            assert result["last"]["outcome"] == "ready"
            assert (
                "authorization: bearer synthetic-admin-key-only" in calls[0][0].lower()
            )
            assert "synthetic-admin-key-only" not in json.dumps(result)
            await observer.execute(
                "UPDATE coach.provider_settings SET secret_ref=$1,bound_owner_id='B' WHERE provider='gemini'",
                ref,
            )
            response = await client.post(
                "/api/v1/admin/coach/disconnect",
                json={},
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.json() == {"ok": True}
            assert (directory / ref).exists(), (
                "Another provider still references this key"
            )
            assert (
                await observer.fetchval(
                    "SELECT bound_owner_id FROM coach.provider_settings WHERE provider='gemini'"
                )
                == "B"
            )
            response = await client.post(
                "/api/v1/admin/coach/disconnect",
                json={"provider": "gemini"},
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.json() == {"ok": True}
            assert not (directory / ref).exists()
            assert (
                await observer.fetchval(
                    "SELECT secret_ref FROM coach.provider_settings WHERE provider='openai'"
                )
                is None
            )
            response = await client.post(
                "/api/v1/coach/review",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 503
            assert (
                await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
            )


@pytest.mark.asyncio
async def test_corrupt_credential_is_unreadable_and_never_becomes_optional(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    directory = tmp_path / "coach_data"
    directory.mkdir()
    environment.update(DATA_DIR=str(directory), PLATFORM_COACH_SECRET_FILE=str(secret))
    await observer.execute(
        "UPDATE coach.settings SET enabled=true,provider='compatible'"
    )
    await observer.execute(
        "UPDATE coach.provider_settings SET model='m',options='{\"baseUrl\":\"http://127.0.0.1:9\"}',secret_ref='coach-key-00000000000000000000000000000000.json' WHERE provider='compatible'"
    )
    (directory / "coach-key-00000000000000000000000000000000.json").write_text(
        json.dumps({"type": "apikey", "data": "tampered"})
    )
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES('A',$1::jsonb)",
        json.dumps(STATE),
    )
    async with server(environment) as client:
        view = (
            await client.get(
                "/api/v1/admin/coach", headers={"Authorization": f"Bearer {B}"}
            )
        ).json()
        assert view["auth"]["state"] == "unreadable"
        account = (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {A}"}
            )
        ).json()
        assert account["connected"] is False
        assert account["reason"] == "no-credential"
        result = await client.post(
            "/api/v1/coach/review", json={}, headers={"Authorization": f"Bearer {A}"}
        )
        assert result.status_code == 503
        assert await observer.fetchval("SELECT count(*) FROM coach.daily_usage") == 0


@pytest.mark.asyncio
async def test_imported_profile_credentials_use_own_legacy_ciphertext(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    directory = tmp_path / "coach_data"
    directory.mkdir()
    environment.update(DATA_DIR=str(directory), PLATFORM_COACH_SECRET_FILE=str(secret))
    # Independent Node crypto.hkdfSync/createCipheriv vectors, fixed IV 07 x 12.
    ciphertext = {
        "A": "BwcHBwcHBwcHBwcHsou/oioQm85a/dKQr1C3nVDMRwtw280pV354qGiMSnJIgzVtKlUtKQdQGDJe+pEJIQAxuw==",
        "B": "BwcHBwcHBwcHBwcH3Q0YoSJ6Or/8MWagPzo9DFDMRwtw280pV354qGiMSnJIgzVtKlUtKQdQGDJd+pEJIQAxuw==",
    }
    for owner, blob in ciphertext.items():
        (directory / f"coach-auth-{owner}.json").write_text(
            json.dumps({"type": "apikey", "account": owner + " personal", "data": blob})
        )
        await observer.execute(
            "INSERT INTO training.documents(owner_id,document) VALUES($1,$2::jsonb)",
            owner,
            json.dumps(STATE),
        )
    wire = {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }
    async with provider([(200, wire)]) as (base, calls):
        await observer.execute(
            "UPDATE coach.settings SET enabled=true,provider='openai',auth_mode='profile'"
        )
        await observer.execute(
            "UPDATE coach.provider_settings SET model='m',options=$1::jsonb WHERE provider='openai'",
            json.dumps({"baseUrl": base}),
        )
        async with server(environment) as client:
            for token, owner in ((A, "A"), (B, "B")):
                account = (
                    await client.get(
                        "/api/v1/coach/account?owner_id="
                        + ("B" if owner == "A" else "A"),
                        headers={"Authorization": f"Bearer {token}"},
                    )
                ).json()
                assert account["account"] == owner + " personal"
                response = await client.post(
                    "/api/v1/coach/review",
                    json={"owner_id": "B"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 202, response.text
                assert (await completed(client, token))["last"]["outcome"] == "ready"
            assert (
                "authorization: bearer synthetic-profile-a-only" in calls[0][0].lower()
            )
            assert (
                "authorization: bearer synthetic-profile-b-only" in calls[1][0].lower()
            )
            response = await client.post(
                "/api/v1/admin/coach/test",
                json={},
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.json()["ok"] is False
            assert len(calls) == 2
    assert len(list(directory.iterdir())) == 2


@asynccontextmanager
async def admin_provider(selected, status=200, release=None):
    calls = []

    async def answer(reader, writer):
        try:
            head = (await reader.readuntil(b"\r\n\r\n")).decode()
            size = next(
                (
                    int(line.split(":", 1)[1])
                    for line in head.split("\r\n")
                    if line.lower().startswith("content-length:")
                ),
                0,
            )
            body = await reader.readexactly(size)
            calls.append((head, body))
            if release is not None:
                await release.wait()
            if head.startswith("GET"):
                value = (
                    {
                        "models": [
                            {
                                "name": "models/z",
                                "supportedGenerationMethods": ["generateContent"],
                            },
                            {
                                "name": "models/embedding",
                                "supportedGenerationMethods": ["embedContent"],
                            },
                            {"name": "models/a"},
                        ]
                    }
                    if selected == "gemini"
                    else {"data": [{"id": "z"}, {"id": "a"}]}
                )
            else:
                text = '{"coach_contract":1,"ok":true}'
                value = (
                    {"content": [{"type": "text", "text": text}]}
                    if selected == "anthropic"
                    else {"candidates": [{"content": {"parts": [{"text": text}]}}]}
                    if selected == "gemini"
                    else {"choices": [{"message": {"content": text}}]}
                )
            if status != 200:
                value = {
                    "error": {"message": "synthetic-model-key-only PRIVATE-DETAIL"}
                }
            raw = json.dumps(value).encode()
            writer.write(
                f"HTTP/1.1 {status} Fixture\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode()
                + raw
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    listener = await asyncio.start_server(answer, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{listener.sockets[0].getsockname()[1]}", calls
    finally:
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", ["anthropic", "openai", "gemini", "compatible"])
async def test_admin_models_and_test_use_real_private_http_without_training_or_quota(
    identities, tmp_path, selected
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    environment.update(
        DATA_DIR=str(tmp_path / "coach_data"), PLATFORM_COACH_SECRET_FILE=str(secret)
    )
    async with admin_provider(selected) as (base, calls):
        await observer.execute("UPDATE coach.settings SET provider=$1", selected)
        await observer.execute(
            "UPDATE coach.provider_settings SET model='m',options=$2::jsonb WHERE provider=$1",
            selected,
            json.dumps({"baseUrl": base}),
        )
        async with server(environment) as client:
            headers = {"Authorization": f"Bearer {B}"}
            response = await client.post(
                "/api/v1/admin/coach/connect",
                json={"type": "apikey", "token": "synthetic-model-key-only"},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            response = await client.post(
                "/api/v1/admin/coach/models", json={}, headers=headers
            )
            assert response.status_code == 200, response.text
            assert response.json() == {"ok": True, "models": ["a", "z"]}
            response = await client.post(
                "/api/v1/admin/coach/test", json={}, headers=headers
            )
            assert response.json()["ok"] is True, response.text
            view = (await client.get("/api/v1/admin/coach", headers=headers)).json()
            assert view["knownModels"] == ["a", "z"]
            assert view["runtime"]["ok"] is True
            assert view["auth"]["state"] == "connected"
            assert "synthetic-model-key-only" not in json.dumps(view)
        get_head = calls[0][0].lower()
        assert get_head.startswith(
            "get /v1beta/models?pagesize=200 "
            if selected == "gemini"
            else "get /v1/models "
        )
        assert "synthetic-model-key-only" in get_head
        assert sum(head.startswith("POST") for head, _ in calls) == 1
    assert await observer.fetchval("SELECT count(*) FROM coach.daily_usage") == 0
    assert await observer.fetchval("SELECT count(*) FROM training.documents") == 0


@pytest.mark.asyncio
async def test_admin_result_summary_uses_real_usage_and_bounded_anonymous_outcomes(
    identities,
):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO coach.instance_daily_usage VALUES ((clock_timestamp() AT TIME ZONE 'UTC')::date,7)"
    )
    await observer.execute("INSERT INTO coach.profile_state(owner_id) VALUES('A')")
    await observer.execute(
        "INSERT INTO coach.jobs VALUES('A','job-1','review','manual','running',clock_timestamp(),0)"
    )
    await observer.execute(
        "INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at,details) SELECT 'A','job-1','review','ready',clock_timestamp(),'{\"reading\":\"PRIVATE-READING\"}' FROM generate_series(1,105)"
    )
    async with server(environment) as client:
        view = (
            await client.get(
                "/api/v1/admin/coach", headers={"Authorization": f"Bearer {B}"}
            )
        ).json()
        assert view["jobsToday"] == 7
        assert len(view["recent"]) == 20
        assert view["lastSuccess"]["outcome"] == "ready"
        assert view["lastError"] is not None
        assert view["lastError"]["errorClass"] == "restart"
        assert "PRIVATE-READING" not in json.dumps(view)
        assert "job-1" not in json.dumps(view)
    assert await observer.fetchval("SELECT count(*) FROM coach.instance_results") == 100


@pytest.mark.asyncio
async def test_admin_authentication_precedes_parsing_and_config_errors_are_atomic(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        for action in ("config", "connect", "disconnect", "test", "models"):
            response = await client.post(
                "/api/v1/admin/coach/" + action,
                content="{",
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 403, response.text
            response = await client.post(
                "/api/v1/admin/coach/" + action,
                content="{}",
                headers={"Cookie": f"gymsid={B}", "Origin": "https://foreign.example"},
            )
            assert response.status_code == 403
        before = await observer.fetchval(
            "SELECT row_to_json(s)::text FROM coach.settings s"
        )
        for body in (
            {"provider": "unknown"},
            {"provider": "openai", "baseUrl": "http://localhost:9"},
            {"provider": "compatible", "baseUrl": "https://user:password@example.test"},
            {"provider": "compatible", "headers": {"Authorization": "secret"}},
            {"provider": "compatible", "headers": {"X-Title": "one\r\ntwo"}},
        ):
            response = await client.post(
                "/api/v1/admin/coach/config",
                json={**body, "enabled": True},
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.status_code == 400, response.text
            assert (
                await observer.fetchval(
                    "SELECT row_to_json(s)::text FROM coach.settings s"
                )
                == before
            )
        await observer.execute(
            "UPDATE identity.users SET session_version=session_version+1 WHERE id='B'"
        )
        assert (
            await client.get(
                "/api/v1/admin/coach", headers={"Authorization": f"Bearer {B}"}
            )
        ).status_code == 401


@pytest.mark.asyncio
async def test_credential_sql_catalog_is_bounded_and_pool_context_does_not_leak(
    identities,
):
    observer, environment = identities
    connection = await runtime_connection(environment)
    try:
        assert (
            await connection.fetch(
                "SELECT * FROM coach.credential_context($1,0,now()+interval '1 hour')",
                "A",
            )
            == []
        )
        for table in ("settings", "provider_settings", "instance_results"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.fetch("SELECT * FROM coach." + table)
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id','A',true)")
            assert (
                len(
                    await connection.fetch(
                        "SELECT * FROM coach.credential_context($1,0,now()+interval '1 hour')",
                        "A",
                    )
                )
                == 1
            )
            assert (
                await connection.fetch(
                    "SELECT * FROM coach.credential_context($1,3,now()+interval '1 hour')",
                    "B",
                )
                == []
            )
            assert (
                await connection.fetchval(
                    "SELECT coach.read_instance($1,0,now()+interval '1 hour')", "A"
                )
                == "{}"
            )
        assert (
            await connection.fetch(
                "SELECT * FROM coach.credential_context($1,0,now()+interval '1 hour')",
                "A",
            )
            == []
        )
        for signature in (
            "read_instance(text,bigint,timestamptz)",
            "write_instance(text,bigint,timestamptz,jsonb,jsonb)",
            "credential_context(text,bigint,timestamptz)",
            "read_results(text,bigint,timestamptz)",
        ):
            row = await observer.fetchrow(
                "SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,NOT EXISTS(SELECT FROM aclexplode(proacl) a WHERE a.grantee=0) AS private FROM pg_proc WHERE oid=$1::regprocedure",
                "coach." + signature,
            )
            assert row["prosecdef"] and row["private"]
            assert row["owner"] == "opengym_coach_executor"
            assert row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
    finally:
        await connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", ["claude", "codex"])
@pytest.mark.parametrize("mode", ["instance", "profile"])
async def test_deferred_provider_never_connects_tests_or_spends_a_personal_binding(
    identities, tmp_path, selected, mode
):
    observer, environment = identities
    environment["DATA_DIR"] = str(tmp_path)
    sentinel = tmp_path / "protected-original"
    sentinel.write_text("PRIVATE-ORIGINAL")
    await observer.execute(
        "UPDATE coach.settings SET enabled=true,provider=$1", selected
    )
    await observer.execute("UPDATE coach.settings SET auth_mode=$1", mode)
    await observer.execute(
        "UPDATE coach.provider_settings SET model='retained-model',secret_ref='protected-original',bound_owner_id='A' WHERE provider=$1",
        selected,
    )
    async with server(environment) as client:
        for action in ("connect", "test", "models"):
            response = await client.post(
                "/api/v1/admin/coach/" + action,
                json={"type": "apikey", "token": "synthetic-must-not-store"},
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.status_code == 503, response.text
            assert response.json()["code"] == "off"
        view = (
            await client.get(
                "/api/v1/admin/coach", headers={"Authorization": f"Bearer {B}"}
            )
        ).json()
        assert view["provider"] == selected and view["model"] == "retained-model"
        assert view["runtime"]["ok"] is False
        account = (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {A}"}
            )
        ).json()
        assert account["connected"] is False
        assert (
            await client.post(
                "/api/v1/coach/review",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
        ).status_code == 503
    assert await observer.fetchval("SELECT count(*) FROM coach.daily_usage") == 0
    assert sentinel.read_text() == "PRIVATE-ORIGINAL"


@pytest.mark.asyncio
async def test_default_http_model_is_executable_without_an_explicit_model(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    environment.update(
        DATA_DIR=str(tmp_path / "data"), PLATFORM_COACH_SECRET_FILE=str(secret)
    )
    wire = {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }
    async with provider([(200, wire)]) as (base, calls):
        await observer.execute(
            "UPDATE coach.settings SET enabled=true,provider='openai'"
        )
        await observer.execute(
            "UPDATE coach.provider_settings SET options=$1::jsonb WHERE provider='openai'",
            json.dumps({"baseUrl": base}),
        )
        await observer.execute(
            "INSERT INTO training.documents(owner_id,document) VALUES('A',$1::jsonb)",
            json.dumps(STATE),
        )
        async with server(environment) as client:
            assert (
                await client.post(
                    "/api/v1/admin/coach/connect",
                    json={"type": "apikey", "token": "synthetic-default-key-only"},
                    headers={"Authorization": f"Bearer {B}"},
                )
            ).status_code == 200
            response = await client.post(
                "/api/v1/coach/review",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 202, response.text
            assert (await completed(client))["last"]["outcome"] == "ready"
            assert calls[0][1]["model"] == "gpt-5.6"


@pytest.mark.asyncio
async def test_environment_switch_keeps_admin_view_readable_without_provider_io(
    identities,
):
    observer, environment = identities
    environment["COACH_DISABLED"] = "1"
    async with admin_provider("compatible") as (base, calls):
        await observer.execute(
            "UPDATE coach.settings SET provider='compatible',enabled=true"
        )
        await observer.execute(
            "UPDATE coach.provider_settings SET options=$1::jsonb WHERE provider='compatible'",
            json.dumps({"baseUrl": base}),
        )
        async with server(environment) as client:
            response = await client.get(
                "/api/v1/admin/coach", headers={"Authorization": f"Bearer {B}"}
            )
            assert response.status_code == 200, response.text
            assert response.json()["disabledByEnv"] is True
            assert response.json()["runtime"]["ok"] is False
            assert calls == []


@pytest.mark.asyncio
async def test_instance_reference_cannot_spend_or_remove_another_profiles_file(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    directory = tmp_path / "data"
    directory.mkdir()
    environment.update(DATA_DIR=str(directory), PLATFORM_COACH_SECRET_FILE=str(secret))
    filename = directory / "coach-auth-B.json"
    blob = "BwcHBwcHBwcHBwcH3Q0YoSJ6Or/8MWagPzo9DFDMRwtw280pV354qGiMSnJIgzVtKlUtKQdQGDJd+pEJIQAxuw=="
    original = json.dumps({"type": "apikey", "account": "B personal", "data": blob})
    filename.write_text(original)
    await observer.execute("UPDATE coach.settings SET provider='openai'")
    await observer.execute(
        "UPDATE coach.provider_settings SET secret_ref='coach-auth-B.json' WHERE provider='openai'"
    )
    async with server(environment) as client:
        account = (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {A}"}
            )
        ).json()
        assert account["connected"] is False
        response = await client.post(
            "/api/v1/admin/coach/connect",
            json={"type": "apikey", "token": "synthetic-replacement-key-only"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200, response.text
    assert filename.read_text() == original


@pytest.mark.asyncio
async def test_failed_sql_connect_does_not_publish_a_key_or_leave_a_candidate_file(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    directory = tmp_path / "data"
    directory.mkdir()
    environment.update(DATA_DIR=str(directory), PLATFORM_COACH_SECRET_FILE=str(secret))
    await observer.execute("UPDATE coach.settings SET provider='openai'")
    await observer.execute(
        "ALTER TABLE coach.provider_settings ADD CONSTRAINT refuse_key CHECK(secret_ref IS NULL)"
    )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/admin/coach/connect",
            json={"type": "apikey", "token": "synthetic-rollback-key-only"},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 500, response.text
        assert response.json() == {"error": "server error"}
    assert list(directory.iterdir()) == []
    assert (
        await observer.fetchval(
            "SELECT secret_ref FROM coach.provider_settings WHERE provider='openai'"
        )
        is None
    )


@pytest.mark.asyncio
async def test_personal_instance_binding_refuses_other_owner_before_quota(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    environment.update(
        DATA_DIR=str(tmp_path / "data"), PLATFORM_COACH_SECRET_FILE=str(secret)
    )
    await observer.execute("UPDATE coach.settings SET enabled=true,provider='openai'")
    await observer.execute(
        "UPDATE coach.provider_settings SET model='m' WHERE provider='openai'"
    )
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES('B',$1::jsonb)",
        json.dumps(STATE),
    )
    async with server(environment) as client:
        headers = {"Authorization": f"Bearer {B}"}
        assert (
            await client.post(
                "/api/v1/admin/coach/connect",
                json={"type": "apikey", "token": "synthetic-bound-key-only"},
                headers=headers,
            )
        ).status_code == 200
        await observer.execute(
            "UPDATE coach.provider_settings SET bound_owner_id='A' WHERE provider='openai'"
        )
        response = await client.post("/api/v1/coach/review", json={}, headers=headers)
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "shared"
        account = (await client.get("/api/v1/coach/account", headers=headers)).json()
        assert account["connected"] is False and account["reason"] == "shared-account"
        assert (
            await client.post(
                "/api/v1/admin/coach/disconnect", json={}, headers=headers
            )
        ).status_code == 200
        assert (
            await observer.fetchval(
                "SELECT bound_owner_id FROM coach.provider_settings WHERE provider='openai'"
            )
            is None
        )
    assert await observer.fetchval("SELECT count(*) FROM coach.daily_usage") == 0


@pytest.mark.asyncio
async def test_provider_io_releases_sql_and_revoked_admin_cannot_read_late_result(
    identities,
):
    observer, environment = identities
    release = asyncio.Event()
    async with admin_provider("compatible", release=release) as (base, calls):
        await observer.execute("UPDATE coach.settings SET provider='compatible'")
        await observer.execute(
            "UPDATE coach.provider_settings SET options=$1::jsonb WHERE provider='compatible'",
            json.dumps({"baseUrl": base}),
        )
        async with server(environment) as client:
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/admin/coach/models",
                    json={},
                    headers={"Authorization": f"Bearer {B}"},
                    timeout=8,
                )
            )
            try:
                async with asyncio.timeout(4):
                    while not calls:
                        await asyncio.sleep(0.01)
                async with asyncio.timeout(2):
                    await observer.execute(
                        "UPDATE identity.users SET session_version=session_version+1 WHERE id='B'"
                    )
                release.set()
                response = await pending
                assert response.status_code == 401, response.text
            finally:
                release.set()
                await pending


@pytest.mark.asyncio
async def test_model_failure_does_not_expose_provider_detail_or_key(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    environment.update(
        DATA_DIR=str(tmp_path / "data"), PLATFORM_COACH_SECRET_FILE=str(secret)
    )
    async with admin_provider("openai", 401) as (base, calls):
        await observer.execute("UPDATE coach.settings SET provider='openai'")
        await observer.execute(
            "UPDATE coach.provider_settings SET model='m',options=$1::jsonb WHERE provider='openai'",
            json.dumps({"baseUrl": base}),
        )
        async with server(environment) as client:
            headers = {"Authorization": f"Bearer {B}"}
            assert (
                await client.post(
                    "/api/v1/admin/coach/connect",
                    json={"type": "apikey", "token": "synthetic-model-key-only"},
                    headers=headers,
                )
            ).status_code == 200
            for action in ("models", "test"):
                response = await client.post(
                    "/api/v1/admin/coach/" + action, json={}, headers=headers
                )
                assert response.status_code == 200, response.text
                assert response.json()["ok"] is False
                assert "PRIVATE-DETAIL" not in response.text
                assert "synthetic-model-key-only" not in response.text
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_configuration_numeric_coercion_preserves_valid_legacy_bounds(identities):
    _, environment = identities
    async with server(environment) as client:
        headers = {"Authorization": f"Bearer {B}"}
        response = await client.post(
            "/api/v1/admin/coach/config",
            json={
                "maxOutputTokens": [2048],
                "caps": {"perProfileDaily": "0x10", "instanceDaily": "0b10"},
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        view = (await client.get("/api/v1/admin/coach", headers=headers)).json()
        assert view["maxOutputTokens"] == 2048
        assert view["caps"] == {"perProfileDaily": 16, "instanceDaily": 2}
        response = await client.post(
            "/api/v1/admin/coach/config",
            content='{"maxMessageLen":-1e400}',
            headers=headers,
        )
        assert response.status_code == 200, response.text
        view = (await client.get("/api/v1/admin/coach", headers=headers)).json()
        assert view["maxMessageLen"] == 200


@pytest.mark.asyncio
async def test_account_expiry_during_singleton_wait_rejects_without_disclosure(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        async with observer.transaction():
            await observer.execute("SELECT 1 FROM coach.settings FOR UPDATE")
            expiry = await observer.fetchval(
                "SELECT clock_timestamp()+interval '1.2 seconds'"
            )
            token = signed(f"A:{int(expiry.timestamp() * 1000)}:0")
            pending = asyncio.create_task(
                client.get(
                    "/api/v1/coach/account",
                    headers={"Authorization": f"Bearer {token}"},
                )
            )
            async with asyncio.timeout(1):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%coach.credential_context%'"
                    ):
                        break
                    await asyncio.sleep(0.01)
            await observer.execute(
                "SELECT pg_sleep(greatest(0,extract(epoch FROM ($1::timestamptz-clock_timestamp()))))",
                expiry + timedelta(milliseconds=10),
            )
        response = await pending
        assert response.status_code == 401, response.text
        assert (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {A}"}
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_session_key_rotation_preserves_coach_decryption_and_wrong_decrypt_key_fails(
    identities, tmp_path
):
    observer, environment = identities
    keyfile = tmp_path / "coach_secret"
    keyfile.write_text(SECRET)
    environment.update(
        DATA_DIR=str(tmp_path / "data"), PLATFORM_COACH_SECRET_FILE=str(keyfile)
    )
    await observer.execute("UPDATE coach.settings SET provider='openai'")
    async with server(environment) as client:
        assert (
            await client.post(
                "/api/v1/admin/coach/connect",
                json={
                    "type": "apikey",
                    "token": "synthetic-rotation-key-only",
                    "account": "retained account",
                },
                headers={"Authorization": f"Bearer {B}"},
            )
        ).status_code == 200
    new_secret = "synthetic-rotated-session-key-only-0123456789"
    Path(environment["PLATFORM_SESSION_SECRET_FILE"]).write_text(new_secret)
    payload = A.rsplit(".", 1)[0]
    mac = (
        base64.urlsafe_b64encode(
            hmac.digest(new_secret.encode(), payload.encode(), hashlib.sha256)
        )
        .decode()
        .rstrip("=")
    )
    rotated = payload + "." + mac
    async with server(environment) as client:
        assert (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {A}"}
            )
        ).status_code == 401
        account = (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {rotated}"}
            )
        ).json()
        assert account["connected"] is True and account["account"] == "retained account"
    keyfile.write_text("synthetic-wrong-decryption-key-only-0123456789")
    async with server(environment) as client:
        account = (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {rotated}"}
            )
        ).json()
        assert account["connected"] is False
    assert len(list((tmp_path / "data").iterdir())) == 1


@pytest.mark.asyncio
async def test_symlinked_personal_record_is_not_read_and_failed_file_write_keeps_sql(
    identities, tmp_path
):
    observer, environment = identities
    secret = tmp_path / "coach_secret"
    secret.write_text(SECRET)
    directory = tmp_path / "data"
    directory.mkdir()
    environment.update(DATA_DIR=str(directory), PLATFORM_COACH_SECRET_FILE=str(secret))
    sentinel = tmp_path / "foreign"
    sentinel.write_text("PRIVATE-SENTINEL")
    (directory / "coach-auth-A.json").symlink_to(sentinel)
    await observer.execute(
        "UPDATE coach.settings SET provider='openai',auth_mode='profile'"
    )
    async with server(environment) as client:
        account = (
            await client.get(
                "/api/v1/coach/account", headers={"Authorization": f"Bearer {A}"}
            )
        ).json()
        assert account["connected"] is False
        directory.chmod(0o500)
        try:
            response = await client.post(
                "/api/v1/admin/coach/connect",
                json={"type": "apikey", "token": "synthetic-file-failure-key-only"},
                headers={"Authorization": f"Bearer {B}"},
            )
            assert response.status_code == 500, response.text
        finally:
            directory.chmod(0o700)
    assert sentinel.read_text() == "PRIVATE-SENTINEL"
    assert (
        await observer.fetchval(
            "SELECT secret_ref FROM coach.provider_settings WHERE provider='openai'"
        )
        is None
    )


@pytest.mark.asyncio
async def test_upgrade_preserves_configuration_references_and_usage(
    deployment, tmp_path
):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns(
            "p005_delivery.py",
            "p004_admin_users.py",
            "p005_subscriptions.py",
            "p003_coach_client.py",
            "p003_coach_admin.py",
        ),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p003_coach_lifecycle"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name,is_admin) VALUES('A','Alice',true); UPDATE coach.settings SET enabled=true,provider='codex'; UPDATE coach.provider_settings SET model='retained',secret_ref='protected-reference',bound_owner_id='A' WHERE provider='codex'; INSERT INTO coach.instance_daily_usage VALUES ('2000-01-01',9)"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p005_delivery"
    )
    assert tuple(
        await observer.fetchrow(
            "SELECT model,secret_ref,bound_owner_id FROM coach.provider_settings WHERE provider='codex'"
        )
    ) == ("retained", "protected-reference", "A")
    assert await observer.fetchval("SELECT count FROM coach.instance_daily_usage") == 9
    assert await observer.fetchval(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='coach.instance_results'::regclass"
    )
