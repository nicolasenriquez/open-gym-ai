"""Training saves at the approved real HTTP/PostgreSQL boundary."""

import asyncio
import json
import os
import shutil
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import A, B, wait_for_actor_locks
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server


@pytest.mark.asyncio
async def test_first_save_persists_own_document_and_keeps_active_session_local(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                "state": {
                    "_ts": 100,
                    "_rev": 99,
                    "workouts": [{"id": "w1", "d": "2026-09-01"}],
                    "routines": [],
                    "active": {"id": "running"},
                },
                "baseRev": 0,
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result == {"ok": True, "ts": 100, "rev": 1, "wid": result["wid"]}
        assert isinstance(result["wid"], str) and len(result["wid"]) == 16
        assert response.headers["cache-control"] == "no-store"
        saved = await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
        assert saved.json()["rev"] == 1
        assert saved.json()["state"]["workouts"] == [{"id": "w1", "d": "2026-09-01"}]
    row = await observer.fetchrow(
        "SELECT owner_id,document,revision,write_id FROM training.documents"
    )
    assert row["owner_id"] == "A"
    document = json.loads(row["document"])
    assert document["_rev"] == row["revision"] == 1
    assert document["_wid"] == row["write_id"] == result["wid"]
    assert "active" not in document


@pytest.mark.asyncio
async def test_concurrent_first_writes_have_one_winner_and_one_conflict(identities):
    observer, environment = identities
    async with server(environment) as client:
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            requests = [
                asyncio.create_task(
                    client.put(
                        "/api/v1/data?owner_id=B",
                        headers={"Cookie": f"gymsid={A}", "X-Owner-Id": "B"},
                        json={
                            "baseRev": 0,
                            "stamped": True,
                            "owner_id": "B",
                            "state": {"workouts": [{"id": name}]},
                        },
                    )
                )
                for name in ("first", "second")
            ]
            await wait_for_actor_locks(observer, 2)
        responses = await asyncio.gather(*requests)
        assert sorted(response.status_code for response in responses) == [200, 409]
        winner = next(
            response.json() for response in responses if response.status_code == 200
        )
        conflict = next(
            response.json() for response in responses if response.status_code == 409
        )
        assert conflict["error"] == "conflict" and conflict["rev"] == 1
        own = (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
        ).json()
        assert own == {"state": conflict["state"], "rev": 1}
        assert own["state"]["_wid"] == winner["wid"]
        assert (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={B}"})
        ).json() == {"state": None, "rev": 0}
    assert await observer.fetchval("SELECT count(*) FROM training.documents") == 1
    assert (
        await observer.fetchval(
            "SELECT revision FROM training.documents WHERE owner_id='A'"
        )
        == 1
    )


@pytest.mark.asyncio
async def test_real_unknown_field_correction_is_stored_one_revision_after_reply(
    identities,
):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document) VALUES
        ('A','{"_rev":7,"workouts":[],"routines":[],"futureSetting":null,"_prior":{"private":[]}}')""")
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                "baseRev": 7,
                "state": {"_ts": 100, "workouts": [], "routines": []},
            },
        )
        assert response.status_code == 200
        assert response.json()["rev"] == 8
        saved = (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
        ).json()
        assert saved["rev"] == saved["state"]["_rev"] == 9
        assert saved["state"]["futureSetting"] is None
        assert "_prior" not in saved["state"]
        conflict = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                "baseRev": 8,
                "state": {"workouts": []},
            },
        )
        assert conflict.status_code == 409
        assert conflict.json() == {"error": "conflict", **saved}
    row = await observer.fetchrow(
        "SELECT document, revision, write_id FROM training.documents"
    )
    assert row["revision"] == 9 and row["write_id"] == response.json()["wid"]
    assert json.loads(row["document"])["_prior"] == {"private": []}


@pytest.mark.asyncio
async def test_bad_inputs_and_conflicts_never_change_stored_state(identities):
    observer, environment = identities
    async with server(environment) as client:
        good = {"baseRev": 0, "stamped": True, "state": {"workouts": [{"id": "kept"}]}}
        assert (
            await client.put(
                "/api/v1/data", headers={"Cookie": f"gymsid={A}"}, json=good
            )
        ).status_code == 200
        before = await observer.fetchval("SELECT document FROM training.documents")
        for state in (
            None,
            {},
            {"_rev": 99},
            [],
            {"workouts": "bad"},
            {"routines": False},
        ):
            response = await client.put(
                "/api/v1/data",
                headers={"Cookie": f"gymsid={A}"},
                json={"baseRev": 1, "state": state},
            )
            assert response.status_code == 400
        for base in (False, "1", 0, 1.5):
            response = await client.put(
                "/api/v1/data",
                headers={"Cookie": f"gymsid={A}"},
                json={"baseRev": base, "state": {"workouts": []}},
            )
            assert response.status_code == 409
        for raw in ("not json", '{"state":NaN}', "[]"):
            assert (
                await client.put(
                    "/api/v1/data", headers={"Cookie": f"gymsid={A}"}, content=raw
                )
            ).status_code == 400
        assert (
            await client.put(
                "/api/v1/data",
                headers={"Cookie": f"gymsid={A}"},
                content=b"x" * (5 * 1024 * 1024 + 1),
            )
        ).status_code == 413
        assert (
            await client.put(
                "/api/v1/data",
                headers={"Cookie": f"gymsid={A}", "Origin": "https://foreign.test"},
                json=good,
            )
        ).status_code == 403
        assert (
            await client.put(
                "/api/v1/data", headers={"Cookie": "gymsid=invalid"}, json=good
            )
        ).status_code == 401
        assert (
            await observer.fetchval("SELECT document FROM training.documents") == before
        )


@pytest.mark.asyncio
async def test_unicode_values_are_validated_without_rejecting_literal_escape_text(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        for text in ("\x00", "\ud800"):
            response = await client.put(
                "/api/v1/data",
                headers={"Cookie": f"gymsid={A}"},
                content=json.dumps({"baseRev": 0, "state": {"notes": text}}),
            )
            assert response.status_code == 400
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 0, "state": {"notes": r"literal \u0000"}},
        )
        assert response.status_code == 200
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))[
            "notes"
        ]
        == r"literal \u0000"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke", [False, True])
async def test_revalidation_under_account_lock_precedes_writes(identities, revoke):
    observer, environment = identities
    async with server(environment) as client:
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            pending = asyncio.create_task(
                client.put(
                    "/api/v1/data",
                    headers={"Cookie": f"gymsid={A}"},
                    json={"baseRev": 0, "state": {"workouts": []}},
                )
            )
            await wait_for_actor_locks(observer, 1)
            if revoke:
                await observer.execute(
                    "UPDATE identity.users SET session_version=1 WHERE id='A'"
                )
        response = await pending
        assert response.status_code == (401 if revoke else 200)
    assert await observer.fetchval("SELECT count(*) FROM training.documents") == (
        0 if revoke else 1
    )


def external_factory(tmp_path, environment, timeout=False):
    module = tmp_path / "external_mark.py"
    marker = tmp_path / "external-observation"
    module.write_text("""import json
import asyncio
from pathlib import Path
import asyncpg
from opengym_platform.application import create_app as application
from opengym_platform.core.platform_settings import load_database

def create_app():
    async def note(owner, document):
        target = load_database("runtime")
        connection = await asyncpg.connect(host=target.host, database=target.database,
            user=target.user, password=target.password, ssl=False)
        try:
            async with connection.transaction():
                await connection.execute("SELECT set_config('app.owner_id',$1,true)", owner)
                revision = await connection.fetchval("SELECT revision FROM training.documents")
            Path(__file__).with_name("external-observation").write_text(json.dumps({"owner": owner, "revision": revision, "document_revision": document["_rev"]}))
        finally:
            await connection.close()
        raise OSError("private external failure details")
    return application(training_note_state=note)
""")
    if timeout:
        module.write_text(
            module.read_text().replace(
                'raise OSError("private external failure details")',
                "await asyncio.sleep(10)",
            )
        )
    return {
        **environment,
        "PYTHONPATH": str(tmp_path) + os.pathsep + environment["PYTHONPATH"],
    }, marker


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [False, True])
async def test_external_mark_failure_observes_committed_document_and_keeps_success(
    identities, tmp_path, timeout
):
    observer, environment = identities
    configured, marker = external_factory(tmp_path, environment, timeout)
    async with server(configured, factory="external_mark:create_app") as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 0, "state": {"workouts": []}},
            timeout=4,
        )
        assert response.status_code == 200 and response.json()["ok"] is True
        assert json.loads(marker.read_text()) == {
            "owner": "A",
            "revision": 1,
            "document_revision": 1,
        }
        assert (
            await client.get("/api/v1/data/rev", headers={"Cookie": f"gymsid={A}"})
        ).json()["rev"] == 1
    assert await observer.fetchval("SELECT revision FROM training.documents") == 1


@pytest.mark.asyncio
async def test_sql_failure_rolls_back_without_external_mark_or_success(
    identities, tmp_path
):
    observer, environment = identities
    configured, marker = external_factory(tmp_path, environment)
    await observer.execute("""CREATE FUNCTION training.fail_write() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected write failure'; END $$;
        CREATE TRIGGER reject_write BEFORE INSERT ON training.documents
        FOR EACH ROW EXECUTE FUNCTION training.fail_write()""")
    async with server(configured, factory="external_mark:create_app") as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 0, "state": {"workouts": []}},
        )
        assert response.status_code == 500 and response.json() == {
            "error": "server error"
        }
        assert not marker.exists()
    assert await observer.fetchval("SELECT count(*) FROM training.documents") == 0


@pytest.mark.asyncio
async def test_nested_unknown_field_correction_preserves_explicit_known_removals(
    identities,
):
    observer, environment = identities
    current = {
        "_rev": 7,
        "routines": [
            {
                "id": "r",
                "futureFlag": None,
                "excludeFromProgression": True,
                "ex": [
                    {"id": "x", "pyramid": [1, 2], "note": "known removal"},
                    {"id": "y", "future": "Y"},
                ],
            }
        ],
        "workouts": [
            {
                "id": "w",
                "entries": [{"id": "x", "sets": [{"future": None, "note": "clear"}]}],
            }
        ],
    }
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(current),
    )
    sent = {
        "routines": [{"id": "r", "ex": [{"id": "y"}, {"id": "x"}]}],
        "workouts": [{"id": "w", "entries": [{"id": "x", "sets": [{}]}]}],
    }
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 7, "state": sent},
        )
        assert response.status_code == 200 and response.json()["rev"] == 8
        saved = (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
        ).json()
        assert saved["rev"] == 9
        routine = saved["state"]["routines"][0]
        stamp = routine.pop("_ts")
        assert stamp > 0
        assert routine.pop("_f") == {"ex": stamp, "excludeFromProgression": stamp}
        assert saved["state"]["routines"] == [
            {
                "id": "r",
                "futureFlag": None,
                "ex": [{"id": "y", "future": "Y"}, {"id": "x", "pyramid": [1, 2]}],
            }
        ]
        assert saved["state"]["workouts"][0]["entries"][0]["sets"] == [{"future": None}]
        modern = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                "baseRev": 9,
                "stamped": True,
                "state": {"routines": [], "workouts": []},
            },
        )
        assert modern.status_code == 200 and modern.json()["rev"] == 10
        assert (
            json.loads(
                await observer.fetchval("SELECT document FROM training.documents")
            )["routines"]
            == []
        )


@pytest.mark.asyncio
async def test_revision_margin_fails_without_modifying_imported_document(identities):
    observer, environment = identities
    original = '{"_rev":9007199254740990,"workouts":[]}'
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        original,
    )
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 9007199254740990, "state": {"workouts": []}},
        )
        assert response.status_code == 400
    assert json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    ) == json.loads(original)


@pytest.mark.asyncio
async def test_write_grants_preserve_rls_and_forbid_owner_or_metadata_updates(
    identities,
):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('B','{\"private\":true}')"
    )
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        for owner in ("", "A"):
            async with runtime.transaction():
                await runtime.execute(
                    "SELECT set_config('app.owner_id',$1,true)", owner
                )
                assert not await runtime.fetch("SELECT * FROM training.documents")
                assert (
                    await runtime.execute("UPDATE training.documents SET document='{}'")
                    == "UPDATE 0"
                )
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with runtime.transaction():
                        await runtime.execute(
                            "INSERT INTO training.documents(owner_id,document) VALUES ('B','{}')"
                        )
                for statement in (
                    "UPDATE training.documents SET owner_id='A'",
                    "UPDATE training.documents SET revision=DEFAULT",
                    "UPDATE training.documents SET write_id=DEFAULT",
                    "DELETE FROM training.documents",
                ):
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        async with runtime.transaction():
                            await runtime.execute(statement)
            assert not await runtime.fetch("SELECT * FROM training.documents")
    finally:
        await runtime.close()
    assert json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    ) == {"private": True}


@pytest.mark.asyncio
async def test_write_migration_preserves_genuine_training_document(
    deployment, tmp_path
):
    observer, environment = deployment
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        tmp_path / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p001_account.py",
            "p001_passkey.py",
            "p001_password_register.py",
            "p002_training_write.py",
        ),
    )
    await migration({**environment, "PYTHONPATH": str(tmp_path)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p002_training"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('historic','Historical')"
    )
    await observer.execute(
        'INSERT INTO training.documents(owner_id,document) VALUES (\'historic\',\'{"_rev":7,"_prior":{"x":null},"workouts":[]}\')'
    )
    before = await observer.fetchrow("SELECT * FROM training.documents")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_account"
    )
    assert await observer.fetchrow("SELECT * FROM training.documents") == before


@pytest.mark.asyncio
async def test_timestamp_echo_preserves_json_types(identities):
    _, environment = identities
    async with server(environment) as client:
        for revision, (value, expected) in enumerate(
            ((False, None), (0, None), ("", None), ([], []), ({}, {}))
        ):
            response = await client.put(
                "/api/v1/data",
                headers={"Cookie": f"gymsid={A}"},
                json={
                    "baseRev": revision,
                    "stamped": True,
                    "state": {"_ts": value, "workouts": []},
                },
            )
            assert response.status_code == 200 and response.json()["ts"] == expected


@pytest.mark.asyncio
async def test_restoring_only_bookkeeping_does_not_add_a_correction_revision(
    identities,
):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document)
        VALUES ('A','{"_rev":7,"workouts":[],"undone":{"w":42}}')""")
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 7, "state": {"workouts": []}},
        )
        assert response.status_code == 200 and response.json()["rev"] == 8
    row = await observer.fetchrow("SELECT revision,document FROM training.documents")
    assert row["revision"] == 8
    assert json.loads(row["document"])["undone"] == {"w": 42}


@pytest.mark.asyncio
async def test_repeated_exercise_ids_keep_the_first_ordered_match(identities):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document)
        VALUES ('A','{"_rev":7,"routines":[{"id":"r","ex":[
            {"id":"x","pyramid":"first"},{"id":"x","pyramid":"second"}]}]}')""")
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                "baseRev": 7,
                "state": {"routines": [{"id": "r", "ex": [{"id": "x"}]}]},
            },
        )
        assert response.status_code == 200 and response.json()["rev"] == 8
    document = json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    )
    assert document["_rev"] == 9
    assert document["routines"][0]["ex"] == [{"id": "x", "pyramid": "first"}]


@pytest.mark.asyncio
async def test_conflict_distinguishes_empty_document_from_missing_row(identities):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A','{}')"
    )
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 1, "state": {"workouts": []}},
        )
        assert response.status_code == 409
        assert response.json() == {"error": "conflict", "rev": 0, "state": {}}
    assert await observer.fetchval("SELECT document FROM training.documents") == "{}"
