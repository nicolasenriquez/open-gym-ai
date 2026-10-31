"""Existing administration through real restricted HTTP/PostgreSQL."""

import asyncio
import json
import shutil
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server


@pytest.mark.asyncio
async def test_actor_target_projection_and_disable(identities):
    observer, environment = identities
    document = {
        "_rev": 7,
        "_ts": 1234,
        "_prior": {"secret": True},
        "unit": "lb",
        "active": {"private": True},
        "routines": [
            None,
            {"id": "r", "name": "Plan", "emoji": "X", "ex": [None, {"id": "e"}]},
        ],
        "bodyweight": [None, {"d": "2026-01-01", "v": 70}],
        "workouts": [
            None,
            {"id": "old", "d": "2026-01-01", "media": ["private.jpg"]},
            {"id": "new", "d": "2026-01-02", "ex": []},
        ],
        "photos": ["private.jpg"],
        "coach": {"chat": ["private"]},
    }
    await observer.execute(
        "INSERT INTO training.documents VALUES('A',$1::jsonb)", json.dumps(document)
    )
    await observer.execute(
        "INSERT INTO notifications.subscriptions VALUES('https://push.example/A','A','p','a',NULL,now())"
    )
    headers = {"Authorization": f"Bearer {B}"}
    async with server(environment) as client:
        response = await client.get("/api/v1/admin/users", headers=headers)
        assert response.status_code == 200
        body = response.json()
        users = {row["id"]: row for row in body["users"]}
        assert users["A"] == {
            "id": "A",
            "name": "Alice",
            "created": None,
            "disabled": False,
            "admin": False,
            "invitedBy": None,
            "workouts": 2,
            "lastWorkout": "2026-01-02",
            "lastSync": 1234,
            "hasPush": True,
            "live": None,
        }
        assert users["B"]["workouts"] == 0 and not users["B"]["hasPush"]
        response = await client.get(
            "/api/v1/admin/user?id=A&owner_id=A", headers=headers
        )
        assert response.status_code == 200
        assert response.json() == {
            "user": {
                k: users["A"][k]
                for k in ("id", "name", "created", "disabled", "admin", "invitedBy")
            },
            "unit": "lb",
            "lastSync": 1234,
            "routines": [{"id": "r", "name": "Plan", "emoji": "X", "count": 1}],
            "bodyweight": [{"d": "2026-01-01", "v": 70}],
            "workouts": [
                {"id": "new", "d": "2026-01-02", "ex": []},
                {"id": "old", "d": "2026-01-01"},
            ],
        }
        assert (await client.get("/api/v1/data", headers=headers)).json() == {
            "state": None,
            "rev": 0,
        }
        for disabled in (True, False):
            response = await client.post(
                "/api/v1/admin/user/disable",
                headers=headers,
                json={"id": "A", "disabled": disabled, "owner_id": "B"},
            )
            assert response.status_code == 200
            assert response.json() == {"ok": True, "id": "A", "disabled": disabled}
            assert (
                await client.get("/api/v1/me", headers={"Authorization": f"Bearer {A}"})
            ).status_code == (401 if disabled else 200)
        assert (
            json.loads(
                await observer.fetchval(
                    "SELECT document FROM training.documents WHERE owner_id='A'"
                )
            )
            == document
        )


@pytest.mark.asyncio
async def test_permissions_errors_and_disabled_admin_guard(identities):
    observer, environment = identities
    async with server(environment) as client:
        for method, path, body in (
            ("GET", "/admin/users", None),
            ("GET", "/admin/user?id=A", None),
            ("POST", "/admin/user/disable", {"id": "B", "disabled": True}),
        ):
            for token, expected in ((None, 401), (A, 403), ("forged", 401)):
                response = await client.request(
                    method,
                    "/api/v1" + path,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )
                assert response.status_code == expected
                assert response.json() == {
                    "error": "forbidden" if expected == 403 else "not signed in"
                }
        headers = {"Authorization": f"Bearer {B}"}
        await observer.execute(
            "INSERT INTO identity.users(id,display_name,is_admin) VALUES('C','Other admin',true)"
        )
        for disabled in (True, False):
            other = await client.post(
                "/api/v1/admin/user/disable",
                json={"id": "C", "disabled": disabled},
                headers=headers,
            )
            assert other.status_code == 400 and other.json() == {
                "error": "cannot disable an admin"
            }
            response = await client.post(
                "/api/v1/admin/user/disable",
                json={"id": "B", "disabled": disabled},
                headers=headers,
            )
            assert response.status_code == 400
            assert response.json() == {"error": "cannot disable an admin"}
        for target in (None, "missing", 1, {}, "bad\x00id"):
            response = await client.post(
                "/api/v1/admin/user/disable",
                json={"id": target, "disabled": True},
                headers=headers,
            )
            assert response.status_code == 404
        assert (
            await client.get("/api/v1/admin/user?id=missing", headers=headers)
        ).status_code == 404
        assert (
            await client.post(
                "/api/v1/admin/user/disable", content="{", headers=headers
            )
        ).status_code == 400
        assert (
            await client.post(
                "/api/v1/admin/user/disable",
                content=b"x" * (5 * 1024 * 1024 + 1),
                headers=headers,
            )
        ).status_code == 413
        for raw in (
            "{",
            "[]",
            '{"id":"A","disabled":NaN}',
            '{"id":"A","disabled":Infinity}',
        ):
            invalid = await client.post(
                "/api/v1/admin/user/disable", content=raw, headers=headers
            )
            assert invalid.status_code == 400 and invalid.json() == {
                "error": "invalid json"
            }
        response = await client.post(
            "/api/v1/admin/user/disable",
            json={"id": "A", "disabled": True},
            headers={"Cookie": f"gymsid={B}", "Origin": "https://foreign.example"},
        )
        assert response.status_code == 403
        response = await client.get(
            "/api/v1/admin/users?owner_id=B",
            headers={"Cookie": f"gymsid={A}", **headers, "X-Owner-Id": "B"},
        )
        assert response.status_code == 403
        assert response.headers["Cache-Control"] == "no-store"
    assert not await observer.fetchval("SELECT bool_or(disabled) FROM identity.users")


@pytest.mark.asyncio
async def test_password_disclosure_pull_sync_and_device_link_revocation(identities):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute("""
        UPDATE identity.users SET last_pull_at='2026-01-01' WHERE id='A';
        INSERT INTO identity.password_credentials VALUES('A','private-hash',NULL);
        INSERT INTO identity.login_aliases VALUES('alice@example.com','A',true,false,NULL);
        INSERT INTO identity.password_resets VALUES('A',decode(repeat('ab',32),'hex'),now()+interval '1 hour','B');
        INSERT INTO identity.device_links VALUES(decode(repeat('cd',32),'hex'),'A',now(),now()+interval '10 minutes');
    """)
    async with server(environment) as client:
        headers = {"Authorization": f"Bearer {B}"}
        detail = (await client.get("/api/v1/admin/user?id=A", headers=headers)).json()
        assert detail["user"]["password"] is True
        assert detail["user"]["email"] == "alice@example.com"
        assert detail["user"]["resetUntil"] > 0
        assert detail["lastSync"] == 1767225600000
        assert detail["unit"] == "kg" and detail["workouts"] == []
        users = (await client.get("/api/v1/admin/users", headers=headers)).json()
        assert users["password_login"] is True
        assert "resetUntil" not in users["users"][0]
        assert "private-hash" not in json.dumps(users) + json.dumps(detail)
        await observer.execute(
            "UPDATE identity.password_resets SET expires_at=now()-interval '1 second'"
        )
        assert (await client.get("/api/v1/admin/user?id=A", headers=headers)).json()[
            "user"
        ]["resetUntil"] is None
        for value in ({}, [], "false"):
            response = await client.post(
                "/api/v1/admin/user/disable",
                headers=headers,
                json={"id": "A", "disabled": value},
            )
            assert response.json() == {"ok": True, "id": "A", "disabled": True}
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 0
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.password_resets")
            == 1
        )
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["users", "user", "disable"])
@pytest.mark.parametrize(
    "change", ["revoked", "demoted", "disabled", "deleted", "expiry"]
)
async def test_stale_actor_waiting_on_target_never_reads_or_mutates(
    identities, operation, change
):
    observer, environment = identities
    async with server(environment) as client:
        expiry = await observer.fetchval(
            "SELECT clock_timestamp()+interval '700 milliseconds'"
        )
        token = (
            signed(f"B:{int(expiry.timestamp() * 1000)}:3") if change == "expiry" else B
        )
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            headers = {"Authorization": f"Bearer {token}"}
            task = asyncio.create_task(
                client.post(
                    "/api/v1/admin/user/disable",
                    headers=headers,
                    json={"id": "A", "disabled": True},
                )
                if operation == "disable"
                else client.get(
                    "/api/v1/admin/"
                    + operation
                    + ("?id=A" if operation == "user" else ""),
                    headers=headers,
                )
            )
            async with asyncio.timeout(1):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%administration.%'"
                    ):
                        break
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
        response = await task
        assert response.status_code == (403 if change == "demoted" else 401)
        assert not await observer.fetchval(
            "SELECT disabled FROM identity.users WHERE id='A'"
        )


@pytest.mark.asyncio
async def test_upgrade_sql_privileges_and_projection_permissions(deployment, tmp_path):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p004_admin_users.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p005_subscriptions"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name,is_admin) VALUES('A','Alice',false),('B','Bob',true)"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        for statement in (
            "SET ROLE opengym_administration_executor",
            "UPDATE identity.users SET disabled=true WHERE id='A'",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(statement)
        assert await runtime.fetch("SELECT * FROM training.documents") == []
        assert await runtime.fetch("SELECT * FROM identity.password_credentials") == []
        for function in (
            "administration.inspect_user",
            "training.read_admin_summary",
            "training.read_admin_detail",
        ):
            assert (
                json.loads(
                    await runtime.fetchval(
                        f"SELECT {function}('A',0,now()+interval '1 day','B')"
                    )
                )
                == {}
            )
            assert (
                await runtime.fetchval(
                    f"SELECT {function}('B',999,now()+interval '1 day','A')"
                )
                is None
            )
        assert (
            json.loads(
                await runtime.fetchval(
                    "SELECT administration.list_users('B',0,now()+interval '1 day',1,NULL)"
                )
            )[0]["id"]
            == "A"
        )
        assert (
            json.loads(
                await runtime.fetchval(
                    "SELECT administration.list_users('B',0,now()+interval '1 day',1,'A')"
                )
            )[0]["id"]
            == "B"
        )
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await runtime.fetchval(
                "SELECT administration.list_users('B',0,now()+interval '1 day',501,NULL)"
            )
    finally:
        await runtime.close()
    functions = await observer.fetch(
        "SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,NOT EXISTS(SELECT FROM aclexplode(proacl) WHERE grantee=0) AS private FROM pg_proc WHERE pronamespace IN ('administration'::regnamespace,'training'::regnamespace) AND prosecdef"
    )
    assert len(functions) == 5
    assert all(
        tuple(row)
        == (
            True,
            ["search_path=pg_catalog, pg_temp"],
            "opengym_administration_executor",
            True,
        )
        for row in functions
    )
    assert not await observer.fetchval(
        "SELECT rolcanlogin OR rolsuper OR rolbypassrls FROM pg_roles WHERE rolname='opengym_administration_executor'"
    )


@pytest.mark.asyncio
async def test_disable_rollback_and_best_effort_pull_bookkeeping(identities):
    observer, environment = identities
    await observer.execute("""
        INSERT INTO identity.device_links VALUES(decode(repeat('ab',32),'hex'),'A',now(),now()+interval '10 minutes');
        CREATE FUNCTION public.fail_link_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'synthetic-injected-failure'; END $$;
        CREATE TRIGGER fail_link BEFORE DELETE ON identity.device_links FOR EACH ROW EXECUTE FUNCTION public.fail_link_delete();
    """)
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/admin/user/disable",
            headers={"Authorization": f"Bearer {B}"},
            json={"id": "A", "disabled": True},
        )
        assert response.status_code == 500 and response.json() == {
            "error": "server error"
        }
        assert not await observer.fetchval(
            "SELECT disabled FROM identity.users WHERE id='A'"
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        await observer.execute(
            "REVOKE UPDATE(last_pull_at) ON identity.users FROM opengym_api_runtime"
        )
        response = await client.get(
            "/api/v1/data", headers={"Authorization": f"Bearer {A}"}
        )
        assert response.status_code == 200 and response.json() == {
            "state": None,
            "rev": 0,
        }
        assert (
            await observer.fetchval(
                "SELECT last_pull_at FROM identity.users WHERE id='A'"
            )
            is None
        )


@pytest.mark.asyncio
async def test_authorized_operation_holds_both_owners_until_commit(identities):
    observer, environment = identities
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        async with runtime.transaction():
            assert json.loads(
                await runtime.fetchval(
                    "SELECT administration.set_disabled('B',3,now()+interval '1 day','A',true)"
                )
            )["ok"]
            revoked = asyncio.create_task(
                observer.execute(
                    "UPDATE identity.users SET session_version=4 WHERE id='B'"
                )
            )
            async with asyncio.timeout(1):
                while not await runtime.fetchval(
                    "SELECT cardinality(pg_blocking_pids($1))",
                    observer.get_server_pid(),
                ):
                    await runtime.execute("SELECT pg_stat_clear_snapshot()")
                    await asyncio.sleep(0.01)
            assert not revoked.done()
        await revoked
        assert await observer.fetchval(
            "SELECT disabled FROM identity.users WHERE id='A'"
        )
        async with server(environment) as client:
            assert (
                await client.get(
                    "/api/v1/admin/users", headers={"Authorization": f"Bearer {B}"}
                )
            ).status_code == 401
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_whole_instance_list_keeps_internal_paging_private(identities):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) SELECT 'u'||lpad(n::text,4,'0'),'Profile' FROM generate_series(1,501) n"
    )
    async with server(environment) as client:
        response = await client.get(
            "/api/v1/admin/users", headers={"Authorization": f"Bearer {B}"}, timeout=10
        )
        assert response.status_code == 200
        assert len(response.json()["users"]) == 503
        assert len({row["id"] for row in response.json()["users"]}) == 503


@pytest.mark.asyncio
async def test_pull_only_profile_updates_admin_sync_and_throttles(identities):
    observer, environment = identities
    async with server(environment) as client:
        headers = {"Authorization": f"Bearer {B}"}
        assert (await client.get("/api/v1/admin/user?id=A", headers=headers)).json()[
            "lastSync"
        ] is None
        await client.get("/api/v1/data/rev", headers={"Authorization": f"Bearer {A}"})
        assert (
            await observer.fetchval(
                "SELECT last_pull_at FROM identity.users WHERE id='A'"
            )
            is None
        )
        await client.get("/api/v1/data", headers={"Authorization": f"Bearer {A}"})
        pulled = await observer.fetchval(
            "SELECT last_pull_at FROM identity.users WHERE id='A'"
        )
        assert pulled is not None
        await client.get("/api/v1/data", headers={"Authorization": f"Bearer {A}"})
        assert (
            await observer.fetchval(
                "SELECT last_pull_at FROM identity.users WHERE id='A'"
            )
            == pulled
        )
    async with server(environment) as client:
        assert (await client.get("/api/v1/admin/user?id=A", headers=headers)).json()[
            "lastSync"
        ] == int(pulled.timestamp() * 1000)


@pytest.mark.asyncio
async def test_invalid_sync_metadata_does_not_break_admin_projection(identities):
    observer, environment = identities
    async with server(environment) as client:
        for value, expected in (
            ("1e999999", None),
            ("not a number", None),
            ("  ", None),
            ("42", 42),
            (True, 1),
            (False, None),
            ({}, None),
            ([], None),
            ([42], 42),
            ([[42]], 42),
            ([True], None),
        ):
            await observer.execute(
                "INSERT INTO training.documents(owner_id,document) VALUES('A',$1::jsonb) ON CONFLICT(owner_id) DO UPDATE SET document=excluded.document",
                json.dumps({"_ts": value}),
            )
            for path in ("/api/v1/admin/users", "/api/v1/admin/user?id=A"):
                response = await client.get(
                    path, headers={"Authorization": f"Bearer {B}"}
                )
                if response.status_code != 200:
                    await observer.fetchval(
                        "SELECT training.read_admin_summary('B',3,now()+interval '1 day','A')"
                    )
                assert response.status_code == 200, (value, response.text)
                result = response.json()
                result = (
                    next(row for row in result["users"] if row["id"] == "A")
                    if "users" in result
                    else result
                )
                assert result["lastSync"] == expected
        await observer.execute(
            'UPDATE training.documents SET document=\'{"workouts":[{}],"routines":[{"ex":"bad"}],"bodyweight":{}}\''
        )
        listed = (
            await client.get(
                "/api/v1/admin/users", headers={"Authorization": f"Bearer {B}"}
            )
        ).json()["users"][0]
        assert listed["workouts"] == 1 and "lastWorkout" not in listed
        detail = (
            await client.get(
                "/api/v1/admin/user?id=A", headers={"Authorization": f"Bearer {B}"}
            )
        ).json()
        assert (
            detail["routines"] == [{"count": 0}]
            and detail["workouts"] == [{}]
            and detail["bodyweight"] == []
        )
