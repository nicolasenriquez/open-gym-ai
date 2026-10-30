"""Coach HTTP against private provider fixtures and restricted PostgreSQL."""

import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import pytest
from test_coach_jobs import runtime_connection
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

STATE = {
    "_rev": 7,
    "name": "PRIVATE-NAME",
    "push": "PRIVATE-PUSH",
    "coach": {"consent": {"agreedAt": 1}, "profile": {"daysPerWeek": 1}},
    "routines": [
        {"id": "r1", "name": "Strength", "ex": [{"id": "0001", "sets": 3, "reps": 10}]}
    ],
    "week": {"1": "r1"},
    "workouts": [],
}


REVIEW = {
    "coach_contract": 1,
    "summary": "One extra set",
    "changes": [
        {
            "type": "sets",
            "target": {"routineId": "r1", "exId": "0001"},
            "before": "untrusted",
            "after": 4,
            "why": "Consistent completed training",
        }
    ],
}


@asynccontextmanager
async def provider(replies, release=None):
    calls = []

    async def answer(reader, writer):
        try:
            head = (await reader.readuntil(b"\r\n\r\n")).decode()
            headers = dict(
                line.split(": ", 1) for line in head.split("\r\n")[1:] if ": " in line
            )
            raw = await reader.readexactly(
                int(
                    next(v for k, v in headers.items() if k.lower() == "content-length")
                )
            )
            calls.append((head, json.loads(raw)))
            if release is not None:
                await release.wait()
            status, value = replies[min(len(calls) - 1, len(replies) - 1)]
            body = json.dumps(value).encode()
            writer.write(
                f"HTTP/1.1 {status} Fixture\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
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


async def configure(observer, base, selected="compatible"):
    await observer.execute(
        "UPDATE coach.settings SET enabled=true,provider=$1", selected
    )
    await observer.execute(
        "UPDATE coach.provider_settings SET model='private-model',options=$2::jsonb WHERE provider=$1",
        selected,
        json.dumps({"baseUrl": base}),
    )
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(STATE),
    )


async def completed(client, token=A, timeout=8):
    async with asyncio.timeout(timeout):
        while True:
            response = await client.get(
                "/api/v1/coach/status", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200, response.text
            result = response.json()
            if not result.get("job"):
                return result
            await asyncio.sleep(0.25 if timeout > 15 else 0.02)


@pytest.mark.asyncio
async def test_validated_review_is_pending_and_never_applies_training(identities):
    observer, environment = identities
    async with provider(
        [
            (
                200,
                {
                    "choices": [
                        {
                            "message": {"content": json.dumps(REVIEW)},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )
        ]
    ) as (base, calls):
        await configure(observer, base)
        async with server(environment) as client:
            response = await client.post(
                "/api/v1/coach/review?owner_id=B",
                json={"note": "Please review"},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 202, response.text
            result = await completed(client)
            assert result["pending"]["changes"][0]["before"] == 3
            assert result["pending"]["changes"][0]["after"] == 4
            assert result["last"]["outcome"] == "ready"
            assert (
                json.loads(
                    await observer.fetchval(
                        "SELECT document FROM training.documents WHERE owner_id='A'"
                    )
                )
                == STATE
            )
            assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
            assert (
                await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
            )
            assert "PRIVATE-NAME" not in json.dumps(calls)
            assert "PRIVATE-PUSH" not in json.dumps(calls)
            assert len(calls) == 1
            assert result["pending"]["planHash"]
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM coach.pending_proposals WHERE owner_id='B'"
                )
                == 0
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", ["anthropic", "openai", "gemini"])
async def test_http_provider_protocols_preserve_rules_and_credentials(
    identities, tmp_path, selected
):
    observer, environment = identities
    text = json.dumps(REVIEW)
    wire = {
        "anthropic": {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
        },
        "openai": {
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}]
        },
        "gemini": {
            "candidates": [
                {"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}
            ]
        },
    }[selected]
    factory = tmp_path / "coach_http_probe.py"
    factory.write_text(
        "from opengym_platform.application import create_app\ndef build():\n    return create_app(coach_credentials=lambda owner,provider: 'synthetic-http-key-only')\n"
    )
    async with provider([(200, wire)]) as (base, calls):
        await configure(observer, base, selected)
        async with server(
            {**environment, "PYTHONPATH": str(tmp_path) + ":/app/src"},
            factory="coach_http_probe:build",
        ) as client:
            response = await client.post(
                "/api/v1/coach/review",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 202, response.text
            result = await completed(client)
            assert result["last"]["outcome"] == "ready"
    head, body = calls[0]
    if selected == "anthropic":
        assert head.startswith("POST /v1/messages ")
        assert "x-api-key: synthetic-http-key-only" in head.lower()
        assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert "You are the openGym Coach." in body["system"][0]["text"]
    elif selected == "openai":
        assert head.startswith("POST /v1/chat/completions ")
        assert "authorization: bearer synthetic-http-key-only" in head.lower()
        assert body["max_completion_tokens"] == 16000
        assert body["response_format"]["json_schema"]["schema"]["type"] == "object"
    else:
        assert head.startswith("POST /v1beta/models/private-model:generateContent ")
        assert "x-goog-api-key: synthetic-http-key-only" in head.lower()
        assert "?key=" not in head
        assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "synthetic-http-key-only" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        "not JSON",
        {"coach_contract": 2},
        {"changes": [{"type": "delete-account", "why": "hostile"}]},
    ],
)
@pytest.mark.parametrize("repair_succeeds", [False, True])
async def test_single_repair_budget_never_applies_invalid_provider_output(
    identities, invalid, repair_succeeds
):
    observer, environment = identities

    def wire(value):
        return {
            "choices": [
                {
                    "message": {
                        "content": value
                        if isinstance(value, str)
                        else json.dumps(value)
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    async with provider(
        [(200, wire(invalid)), (200, wire(REVIEW if repair_succeeds else invalid))]
    ) as (base, calls):
        await configure(observer, base)
        async with server(environment) as client:
            assert (
                await client.post(
                    "/api/v1/coach/review",
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).status_code == 202
            result = await completed(client)
    assert len(calls) == 2
    assert result["last"]["outcome"] == ("ready" if repair_succeeds else "failed")
    assert result["last"]["errorClass"] == (None if repair_succeeds else "unusable")
    assert bool(result["pending"]) == repair_succeeds
    assert calls[0][1]["messages"][0] == calls[1][1]["messages"][0]
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == STATE
    )
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1


@pytest.mark.asyncio
async def test_creation_refinement_and_debrief_keep_proposals_separate_from_training(
    identities,
):
    observer, environment = identities
    bundle = {
        "coach_contract": 1,
        "name": "New plan",
        "week": {"1": "new"},
        "routines": [
            {
                "id": "new",
                "name": "New routine",
                "ex": [{"id": "0001", "sets": 3, "reps": 8, "weight": 999}],
            }
        ],
    }
    revision = {
        "changes": [
            {
                "type": "sets",
                "target": {"routineId": "new", "exId": "0001"},
                "after": 5,
                "why": "Requested revision",
            }
        ]
    }
    debrief = {
        "summary": "A solid session",
        "score": 8,
        "highlights": ["Completed work"],
        "nextTime": ["Rest between sets"],
    }
    replies = [
        (
            200,
            {
                "choices": [
                    {"message": {"content": json.dumps(v)}, "finish_reason": "stop"}
                ]
            },
        )
        for v in (bundle, revision, debrief)
    ]
    async with provider(replies) as (base, calls):
        await configure(observer, base)
        state = {
            **STATE,
            "workouts": [
                {
                    "id": "w1",
                    "d": "2026-10-30",
                    "name": "Strength",
                    "entries": [
                        {"id": "0001", "sets": [{"done": True, "w": 15, "r": 8}]}
                    ],
                }
            ],
        }
        await observer.execute(
            "UPDATE training.documents SET document=$1::jsonb", json.dumps(state)
        )
        async with server(environment) as client:
            headers = {"Authorization": f"Bearer {A}"}
            assert (
                await client.post("/api/v1/coach/plan", json={}, headers=headers)
            ).status_code == 202
            initial = await completed(client)
            assert initial["pending"]["bundle"]["routines"][0]["ex"][0]["weight"] == 15
            assert (
                await client.post(
                    "/api/v1/coach/plan",
                    json={"refine": "Five sets, please"},
                    headers=headers,
                )
            ).status_code == 202
            refined = await completed(client)
            assert refined["last"]["outcome"] == "ready"
            assert refined["pending"]["iteration"] == 2
            assert refined["pending"]["bundle"]["routines"][0]["ex"][0]["sets"] == 5
            assert (
                await client.post(
                    "/api/v1/coach/debrief", json={"workoutId": "w1"}, headers=headers
                )
            ).status_code == 202
            result = await completed(client)
            assert result["pending"]["score"] == 8
            assert result["pending"]["workout"]["id"] == "w1"
            assert result["pending"]["workout"]["vol"] == 120
    assert len(calls) == 3
    assert "refine" in calls[1][1]["messages"][1]["content"]
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == state
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["versionless", "json_mode", "transient"])
async def test_compatible_endpoint_fallbacks_and_retry_budget(identities, fallback):
    observer, environment = identities
    answer = {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }
    first = {
        "versionless": (404, {"error": "not found"}),
        "json_mode": (
            400,
            {"error": {"message": "response_format json_schema unsupported"}},
        ),
        "transient": (503, {"error": "PRIVATE-ERROR"}),
    }[fallback]
    async with provider([first, (200, answer)]) as (base, calls):
        await configure(observer, base)
        await observer.execute(
            "UPDATE coach.provider_settings SET options=$1::jsonb WHERE provider='compatible'",
            json.dumps(
                {
                    "baseUrl": base + "/openai",
                    "headers": {
                        "X-Title": "fixture-routing",
                        "Host": "hostile",
                        "authorization": "hostile",
                        "Cookie": "hostile",
                    },
                }
            ),
        )
        async with server(environment) as client:
            assert (
                await client.post(
                    "/api/v1/coach/review",
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).status_code == 202
            result = await completed(client)
    assert result["last"]["outcome"] == "ready"
    assert len(calls) == 2
    assert "x-title: fixture-routing" in calls[0][0].lower()
    assert "hostile" not in calls[0][0]
    if fallback == "versionless":
        assert calls[0][0].startswith("POST /openai/v1/chat/completions ")
        assert calls[1][0].startswith("POST /openai/chat/completions ")
    elif fallback == "json_mode":
        assert calls[1][1]["response_format"] == {"type": "json_object"}
    else:
        assert calls[0][1] == calls[1][1]
    assert "PRIVATE-ERROR" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("consent", [None, False, 0, ""])
async def test_no_consent_never_enqueues_counts_or_calls_a_provider(
    identities, consent
):
    observer, environment = identities
    async with provider([(500, {})]) as (base, calls):
        await configure(observer, base)
        state = {**STATE, "coach": {"consent": {"agreedAt": consent}}}
        await observer.execute(
            "UPDATE training.documents SET document=$1::jsonb", json.dumps(state)
        )
        async with server(environment) as client:
            response = await client.post(
                "/api/v1/coach/review",
                json={},
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == 403
            assert response.json()["code"] == "consent"
    for table in ("jobs", "pending_proposals", "daily_usage", "instance_daily_usage"):
        assert await observer.fetchval(f"SELECT count(*) FROM coach.{table}") == 0
    assert calls == []


@pytest.mark.asyncio
async def test_actor_settings_and_pending_proposals_are_restricted_and_upgrade_is_forward_only(
    deployment, tmp_path
):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p003_coach_http.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p003_coach_jobs"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'),('B','Bob')"
    )
    await configure(observer, "http://private.invalid")
    await observer.execute(
        "UPDATE coach.provider_settings SET secret_ref='protected-not-mounted' WHERE provider='compatible'"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p003_coach_http"
    )
    assert (
        await observer.fetchval(
            "SELECT secret_ref FROM coach.provider_settings WHERE provider='compatible'"
        )
        == "protected-not-mounted"
    )
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == STATE
    )
    assert tuple(
        await observer.fetchrow(
            "SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE oid='coach.pending_proposals'::regclass"
        )
    ) == (True, True, "opengym_schema_owner")
    assert tuple(
        await observer.fetchrow(
            "SELECT prosecdef,pg_get_userbyid(proowner),proconfig,EXISTS(SELECT FROM aclexplode(proacl) WHERE grantee=0) FROM pg_proc WHERE oid='coach.execution_config(text,bigint,timestamptz)'::regprocedure"
        )
    ) == (True, "opengym_coach_executor", ["search_path=pg_catalog, pg_temp"], False)
    connection = await runtime_connection(environment)
    try:
        for sql in (
            "SELECT model FROM coach.provider_settings",
            "SELECT max_message_len FROM coach.settings",
            "SET ROLE opengym_coach_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(sql)
        assert (
            await connection.fetch(
                "SELECT * FROM coach.execution_config('A',0,'2100-01-01')"
            )
            == []
        )
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.owner_id','A',true)")
            config = dict(
                await connection.fetchrow(
                    "SELECT * FROM coach.execution_config('A',0,'2100-01-01')"
                )
            )
            assert config["model"] == "private-model"
            assert "secret_ref" not in config
            assert (
                await connection.fetch(
                    "SELECT * FROM coach.execution_config('B',0,'2100-01-01')"
                )
                == []
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(
                    'INSERT INTO coach.pending_proposals(owner_id,document) VALUES (\'B\',\'{"id":"p","kind":"review","expiresAt":1}\')'
                )
        assert await connection.fetch("SELECT * FROM coach.pending_proposals") == []
    finally:
        await connection.close()
    for expiry in (True, "12", 12.5, None):
        with pytest.raises(asyncpg.IntegrityConstraintViolationError):
            await observer.execute(
                "INSERT INTO coach.pending_proposals(owner_id,document) VALUES ('A',$1::jsonb)",
                json.dumps({"id": "p", "kind": "review", "expiresAt": expiry}),
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["auth", "truncated", "empty", "exhausted"])
async def test_provider_failures_are_classified_without_sensitive_details(
    identities, failure
):
    observer, environment = identities
    status, wire = {
        "auth": (401, {"error": {"message": "PRIVATE-ERROR-KEY"}}),
        "truncated": (
            200,
            {
                "choices": [
                    {
                        "message": {"content": json.dumps(REVIEW)},
                        "finish_reason": "length",
                    }
                ]
            },
        ),
        "empty": (200, {"unexpected": "PRIVATE-ERROR-KEY"}),
        "exhausted": (503, {"error": "PRIVATE-ERROR-KEY"}),
    }[failure]
    async with provider([(status, wire)]) as (base, calls):
        await configure(observer, base)
        async with server(environment) as client:
            assert (
                await client.post(
                    "/api/v1/coach/review",
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).status_code == 202
            result = await completed(client, timeout=15)
    assert len(calls) == (3 if failure == "exhausted" else 1)
    assert result["last"]["outcome"] == "failed"
    assert result["last"]["errorClass"] == ("auth" if failure == "auth" else "provider")
    assert result["pending"] is None
    assert "PRIVATE-ERROR-KEY" not in json.dumps(result)
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == STATE
    )


@pytest.mark.asyncio
async def test_no_owner_lock_is_held_during_provider_io_and_withdrawal_blocks_completion(
    identities,
):
    observer, environment = identities
    release = asyncio.Event()
    answer = {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }
    async with provider([(200, answer)], release) as (base, calls):
        await configure(observer, base)
        await observer.execute(
            "INSERT INTO training.documents(owner_id,document) VALUES ('B',$1::jsonb)",
            json.dumps({"coach": {"consent": {"agreedAt": 1}}}),
        )
        async with server(environment) as client:
            assert (
                await client.post(
                    "/api/v1/coach/review",
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).status_code == 202
            async with asyncio.timeout(3):
                while not calls:
                    await asyncio.sleep(0.02)
            assert (await completed(client, B))["pending"] is None
            async with observer.transaction():
                await observer.execute(
                    "SELECT id FROM identity.users WHERE id='A' FOR UPDATE NOWAIT"
                )
                assert (
                    await observer.fetchval(
                        "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND state='idle in transaction'"
                    )
                    == 0
                )
                await observer.execute(
                    "UPDATE training.documents SET document=jsonb_set(document,'{coach,consent,agreedAt}','false') WHERE owner_id='A'"
                )
            release.set()
            async with asyncio.timeout(3):
                while await observer.fetchval("SELECT count(*) FROM coach.jobs"):
                    await asyncio.sleep(0.02)
            assert (
                await observer.fetchval("SELECT count(*) FROM coach.pending_proposals")
                == 0
            )
            assert (
                await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
            )


@pytest.mark.asyncio
async def test_invalid_or_oversized_request_never_reaches_provider_and_off_precedes_parsing(
    identities,
):
    observer, environment = identities
    async with provider([(500, {})]) as (base, calls):
        await configure(observer, base)
        async with server(environment) as client:
            headers = {
                "Authorization": f"Bearer {A}",
                "Content-Type": "application/json",
            }
            for raw, status in (
                (b"{", 400),
                (b'{"note":NaN}', 400),
                (b"x" * (5 * 1024 * 1024 + 1), 413),
            ):
                response = await client.post(
                    "/api/v1/coach/review", content=raw, headers=headers
                )
                assert response.status_code == status
            await observer.execute("UPDATE coach.settings SET provider='claude'")
            assert (
                await client.post("/api/v1/coach/review", content=b"{", headers=headers)
            ).status_code == 503
    assert calls == []
    assert await observer.fetchval("SELECT count(*) FROM coach.jobs") == 0
    assert await observer.fetchval("SELECT count(*) FROM coach.daily_usage") == 0


@pytest.mark.asyncio
async def test_real_provider_timeout_is_distinct_and_retains_the_single_spending_record(
    identities,
):
    observer, environment = identities
    release = asyncio.Event()
    answer = {
        "choices": [
            {"message": {"content": json.dumps(REVIEW)}, "finish_reason": "stop"}
        ]
    }
    async with provider([(200, answer)], release) as (base, calls):
        await configure(observer, base)
        async with server({**environment, "COACH_JOB_TIMEOUT_MS": "60000"}) as client:
            assert (
                await client.post(
                    "/api/v1/coach/review",
                    json={},
                    headers={"Authorization": f"Bearer {A}"},
                )
            ).status_code == 202
            result = await completed(client, timeout=75)
            release.set()
    assert result["last"]["errorClass"] == "timeout"
    assert result["last"]["outcome"] == "failed"
    assert result["pending"] is None
    assert len(calls) == 1
    assert await observer.fetchval("SELECT sum(count) FROM coach.daily_usage") == 1
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == STATE
    )
