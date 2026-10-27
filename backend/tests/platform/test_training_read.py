"""Training reads through real HTTP, verified actors and PostgreSQL RLS."""

import asyncio
import json
import shutil
from pathlib import Path

import asyncpg
import pytest
from test_identity_password import PASSWORD
from test_identity_password import accounts as accounts  # noqa: PLC0414 -- pytest fixture export
from test_identity_session import A, B, wait_for_actor_locks
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server


@pytest.mark.asyncio
async def test_empty_owner_reads_null_without_creating_document(identities):
    observer, environment = identities
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/data?owner_id=A",
            headers={"Authorization": f"Bearer {B}", "X-Owner-Id": "A"},
        )
        assert response.status_code == 200
        assert response.json() == {"state": None, "rev": 0}
        assert response.headers["cache-control"] == "no-store"
        response = await client.get(
            "/api/v1/data/rev", headers={"Cookie": f"gymsid={A}"}
        )
        assert response.status_code == 200
        assert response.json() == {"rev": 0}
    assert await observer.fetchval("SELECT count(*) FROM training.documents") == 0


@pytest.mark.asyncio
async def test_login_reads_own_document_without_exposing_internal_notes(accounts):
    observer, environment = accounts
    stored = {
        "_rev": 7,
        "_wid": "write-A",
        "_wids": ["old", "write-A"],
        "_prior": {"notes": None},
        "_unstamped": True,
        "workouts": [{"id": "w1", "notes": "A only", "_f": {"notes": 4}}],
        "settings": {"nullable": None},
        "_ts": 100,
    }
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(stored),
    )
    async with server(environment) as client:
        login = await client.post(
            "/api/v1/login/password", json={"identifier": "alice", "password": PASSWORD}
        )
        assert login.status_code == 200
        response = await client.request(
            "GET",
            "/api/v1/data?owner_id=B",
            json={"owner_id": "B"},
            headers={"X-Owner-Id": "B", "Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "state": {
                "_rev": 7,
                "_wid": "write-A",
                "_wids": ["old", "write-A"],
                "workouts": [{"id": "w1", "notes": "A only", "_f": {"notes": 4}}],
                "settings": {"nullable": None},
                "_ts": 100,
            },
            "rev": 7,
        }
        assert (await client.get("/api/v1/data/rev")).json() == {
            "rev": 7,
            "wid": "write-A",
        }
        client.cookies.clear()
        for path in ("/api/v1/data", "/api/v1/data/rev"):
            response = await client.get(path, headers={"Authorization": f"Bearer {B}"})
            assert response.json() == (
                {"state": None, "rev": 0} if path == "/api/v1/data" else {"rev": 0}
            )
    row = await observer.fetchrow(
        "SELECT document, revision, write_id FROM training.documents"
    )
    assert json.loads(row["document"]) == stored
    assert (row["revision"], row["write_id"]) == (7, "write-A")


@pytest.mark.asyncio
async def test_generated_metadata_preserves_missing_null_and_safe_integer(identities):
    observer, environment = identities
    async with server(environment) as client:
        for document, revision, wid in (
            ({"settings": {}}, 0, None),
            ({"_rev": None, "_wid": None}, 0, None),
            ({"_rev": 0, "_wid": ""}, 0, ""),
            ({"_rev": 9007199254740991, "_wid": "max"}, 9007199254740991, "max"),
        ):
            await observer.execute(
                "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb) "
                "ON CONFLICT (owner_id) DO UPDATE SET document=excluded.document",
                json.dumps(document),
            )
            row = await observer.fetchrow(
                "SELECT document,revision,write_id FROM training.documents"
            )
            assert json.loads(row["document"]) == document
            assert (row["revision"], row["write_id"]) == (revision, wid)
            assert (
                await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
            ).json() == {"state": document, "rev": revision}
            assert (
                await client.get("/api/v1/data/rev", headers={"Cookie": f"gymsid={A}"})
            ).json() == {"rev": revision, **({"wid": wid} if wid else {})}


@pytest.mark.asyncio
async def test_sql_rejects_invalid_projections_without_rounding_or_partial_update(
    identities,
):
    observer, _ = identities
    await observer.execute(
        'INSERT INTO training.documents(owner_id,document) VALUES (\'A\',\'{"_rev":7,"_wid":"kept"}\')'
    )
    for key, values in (
        ("_rev", [1.5, -0.1, -1, "1", "", True, [], {}, 9007199254740992, 1e50]),
        ("_wid", [0, True, [], {}]),
    ):
        for value in values:
            with pytest.raises(asyncpg.InvalidParameterValueError) as error:
                await observer.execute(
                    "UPDATE training.documents SET document=$1::jsonb",
                    json.dumps({key: value}),
                )
            assert error.value.sqlstate == "22023"
    for value in ([], None, True, 1, "bad"):
        with pytest.raises(asyncpg.CheckViolationError):
            await observer.execute(
                "UPDATE training.documents SET document=$1::jsonb", json.dumps(value)
            )
    for column, value in (("revision", "8"), ("write_id", "'forged'")):
        with pytest.raises(asyncpg.GeneratedAlwaysError):
            await observer.execute(f"UPDATE training.documents SET {column}={value}")
    row = await observer.fetchrow(
        "SELECT document,revision,write_id FROM training.documents"
    )
    assert json.loads(row["document"]) == {"_rev": 7, "_wid": "kept"}
    assert (row["revision"], row["write_id"]) == (7, "kept")


@pytest.mark.asyncio
async def test_rls_and_projection_privileges_are_restricted(identities):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A','{}')"
    )
    metadata = await observer.fetchrow("""
        SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner
        FROM pg_class WHERE oid='training.documents'::regclass
    """)
    assert tuple(metadata) == (True, True, "opengym_schema_owner")
    functions = await observer.fetch("""
        SELECT p.proname,p.provolatile::text,p.proisstrict,p.prosecdef,
            has_function_privilege('opengym_api_runtime',p.oid,'EXECUTE') AS runtime,
            EXISTS (SELECT FROM aclexplode(p.proacl) a WHERE a.grantee=0) AS public
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='training' ORDER BY p.proname
    """)
    assert [tuple(row) for row in functions] == [
        ("revision_of", "i", True, False, True, False),
        ("write_id_of", "i", True, False, True, False),
    ]
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        assert not await runtime.fetch("SELECT * FROM training.documents")
        for owner, count in (("A", 1), ("B", 0), ("", 0)):
            async with runtime.transaction():
                await runtime.execute(
                    "SELECT set_config('app.owner_id',$1,true)", owner
                )
                assert (
                    await runtime.fetchval("SELECT count(*) FROM training.documents")
                    == count
                )
            assert not await runtime.fetch("SELECT * FROM training.documents")
        for statement in (
            "UPDATE training.documents SET owner_id='forbidden'",
            "DELETE FROM training.documents",
            "CREATE TABLE training.forbidden(id text)",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(statement)
    finally:
        await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/data", "/api/v1/data/rev"])
async def test_invalid_and_revoked_session_never_reads_training(identities, path):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A','{\"private\":true}')"
    )
    async with server(environment) as client:
        for token in ("", "invalid", A[:-1] + "x"):
            response = await client.get(
                path + "?owner_id=A", headers={"Cookie": f"gymsid={token}"}
            )
            assert response.status_code == 401
            assert response.json() == {"error": "not signed in"}
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            pending = asyncio.create_task(
                client.get(path, headers={"Cookie": f"gymsid={A}"})
            )
            await wait_for_actor_locks(observer, 1)
            await observer.execute(
                "UPDATE identity.users SET session_version=1 WHERE id='A'"
            )
        response = await pending
        assert response.status_code == 401
        assert response.json() == {"error": "not signed in"}
        assert response.headers["cache-control"] == "no-store"
        assert (
            await client.get(path, headers={"Cookie": f"gymsid={B}"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_training_migration_extends_existing_identity_without_replay(
    deployment, tmp_path
):
    observer, environment = deployment
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        tmp_path / "opengym_platform",
        ignore=shutil.ignore_patterns("p002_training.py", "p002_training_write.py"),
    )
    await migration({**environment, "PYTHONPATH": str(tmp_path)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_password_login"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('historic','Preserved')"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p002_training_write"
    )
    assert tuple(
        await observer.fetchrow("SELECT id,display_name,created_at FROM identity.users")
    ) == ("historic", "Preserved", None)
