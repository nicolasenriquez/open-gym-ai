"""Administrative invitations and reset issuance through restricted HTTP/SQL."""

import asyncio
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

HEADERS = {"Authorization": f"Bearer {B}"}
ROOT = "/api/v1/admin/invites"
RESET = "/api/v1/admin/user/password-reset"


@pytest.mark.asyncio
async def test_invitation_create_consume_delete_never_reopens_history(identities):
    observer, environment = identities
    environment.update(PASSWORD_LOGIN="1", INVITE_ONLY="1")
    async with server(environment) as client:
        response = await client.post(
            ROOT + "/new", headers=HEADERS, json={"note": "friend", "createdBy": "A"}
        )
        assert response.status_code == 200, response.text
        invite = response.json()["invite"]
        assert re.fullmatch("[0-9A-F]{16}", invite["code"])
        assert invite["note"] == "friend" and invite["createdBy"] == "B"
        assert set(invite) == {"code", "note", "createdBy", "created"}
        listed = (await client.get(ROOT, headers=HEADERS)).json()
        assert listed == {
            "invites": [{**invite, "usedByName": None}],
            "invite_only": True,
        }
        response = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Visitor",
                "password": "violet river stones",
                "code": invite["code"],
            },
        )
        assert response.status_code == 200, response.text
        target = response.json()["user"]["id"]
        # Clear signup cookie so the independently signed admin bearer is selected.
        client.cookies.clear()
        used = (await client.get(ROOT, headers=HEADERS)).json()["invites"][0]
        assert used["usedBy"] == target and used["usedByName"] == "Visitor"
        assert used["usedAt"]
        response = await client.post(
            "/api/v1/admin/user/delete", headers=HEADERS, json={"id": target}
        )
        assert response.status_code == 200, response.text
        after = (await client.get(ROOT, headers=HEADERS)).json()["invites"][0]
        assert after == {**used, "usedByName": None}
        response = await client.post(
            ROOT + "/revoke", headers=HEADERS, json={"code": invite["code"].lower()}
        )
        assert response.status_code == 400
        assert response.json() == {"error": "already used, cannot revoke"}
        response = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Another",
                "password": "violet river stones",
                "code": invite["code"],
            },
        )
        assert response.status_code == 403 and response.json()["code"] == "invite"
    assert await observer.fetchval(
        "SELECT consumed FROM identity.invitations WHERE code=$1", invite["code"]
    )


@pytest.mark.asyncio
async def test_admin_reset_replaces_code_revokes_access_and_redeems_once(identities):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute("""
        INSERT INTO identity.password_credentials VALUES('A','old-hash',NULL);
        INSERT INTO identity.login_aliases VALUES('alice','A',false,true,NULL),('a@example.test','A',true,false,NULL);
        INSERT INTO identity.device_links VALUES(decode(repeat('ab',32),'hex'),'A',now(),now()+interval '10 min');
        INSERT INTO identity.passkeys VALUES('preserved','A',decode('aa','hex'),0,'{}',NULL,NULL,NULL);
    """)
    async with server(environment) as client:
        before = int(time.time() * 1000)
        first = await client.post(
            RESET, headers=HEADERS, json={"id": "A", "owner": "B"}
        )
        assert first.status_code == 200, first.text
        result = first.json()
        assert set(result) == {"ok", "name", "code", "expires"}
        assert result["ok"] and result["name"] == "Alice"
        assert re.fullmatch(
            r"[A-HJ-NP-Z2-9]{4}(?:-[A-HJ-NP-Z2-9]{4}){2}", result["code"]
        )
        assert (
            before + 86400000 <= result["expires"] <= int(time.time() * 1000) + 86400000
        )
        row = await observer.fetchrow(
            "SELECT code_digest,expires_at,issued_by FROM identity.password_resets WHERE owner_id='A'"
        )
        assert (
            row["code_digest"]
            == hashlib.sha256(
                ("opengym-reset:" + result["code"].replace("-", "")).encode()
            ).digest()
        )
        assert (
            row["issued_by"] == "B"
            and int(row["expires_at"].timestamp() * 1000) == result["expires"]
        )
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.password_credentials WHERE owner_id='A'"
        )
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.device_links WHERE owner_id='A'"
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.passkeys WHERE owner_id='A'"
            )
            == 1
        )
        alias = await observer.fetchrow(
            "SELECT password_name_claim,reset_name_until FROM identity.login_aliases WHERE alias_key='alice'"
        )
        assert (
            not alias["password_name_claim"]
            and alias["reset_name_until"] == row["expires_at"]
        )
        assert (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {A}"})
        ).status_code == 401
        second = await client.post(RESET, headers=HEADERS, json={"id": "A"})
        assert second.status_code == 200
        assert second.json()["code"] != result["code"]
        for code, expected in (
            (result["code"], 400),
            (second.json()["code"], 200),
            (second.json()["code"], 400),
        ):
            response = await client.post(
                "/api/v1/login/password-reset",
                json={
                    "identifier": "a@example.test",
                    "code": code,
                    "next": "violet river stones",
                },
            )
            assert response.status_code == expected, response.text
            client.cookies.clear()
        assert (await client.get("/api/v1/me", headers=HEADERS)).status_code == 200
    assert (
        await observer.fetchval(
            "SELECT session_version FROM identity.users WHERE id='A'"
        )
        == 3
    )


@pytest.mark.asyncio
async def test_guards_revoke_errors_and_note_projection(identities):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    async with server(environment) as client:
        for method, path, body in (
            ("GET", ROOT, None),
            ("POST", ROOT + "/new", {}),
            ("POST", ROOT + "/revoke", {}),
            ("POST", RESET, {"id": "A"}),
        ):
            for token, expected in ((None, 401), (A, 403), ("forged", 401)):
                response = await client.request(
                    method,
                    path,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )
                assert response.status_code == expected, (path, response.text)
                assert response.headers["cache-control"] == "no-store"
        for path in (ROOT + "/new", ROOT + "/revoke", RESET):
            assert (
                await client.post(
                    path,
                    headers={
                        "Cookie": "gymsid=" + B,
                        "Origin": "https://foreign.example",
                    },
                    json={},
                )
            ).status_code == 403
            for raw in ("[1]", "{", '{"note":NaN}'):
                assert (
                    await client.post(path, headers=HEADERS, content=raw)
                ).status_code == 400
            assert (
                await client.post(
                    path, headers=HEADERS, content=b"x" * (5 * 1024 * 1024 + 1)
                )
            ).status_code == 413
        created = (
            await client.post(ROOT + "/new", headers=HEADERS, json={"note": "x" * 61})
        ).json()["invite"]
        assert created["note"] == "x" * 60
        response = await client.post(
            ROOT + "/revoke", headers=HEADERS, json={"code": created["code"].lower()}
        )
        assert response.status_code == 200 and response.json() == {"ok": True}
        response = await client.post(
            ROOT + "/revoke", headers=HEADERS, json={"code": created["code"]}
        )
        assert response.status_code == 404 and response.json() == {
            "error": "no such code"
        }
        for target, expected in ((None, 404), ({}, 404), ("missing", 404), ("B", 400)):
            response = await client.post(RESET, headers=HEADERS, json={"id": target})
            assert response.status_code == expected, response.text
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.password_resets"
        )
    environment["PASSWORD_LOGIN"] = "0"
    async with server(environment) as client:
        for headers in ({}, HEADERS):
            assert (
                await client.post(RESET, headers=headers, json={"id": "A"})
            ).status_code == 404
        assert (await client.get(ROOT, headers=HEADERS)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["list", "new", "revoke", "reset"])
@pytest.mark.parametrize(
    "change", ["revoked", "demoted", "disabled", "deleted", "expired"]
)
async def test_waiting_operation_revalidates_current_admin_authority(
    identities, operation, change
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute(
        "INSERT INTO identity.invitations VALUES('UNUSED','kept','B',NULL,false,NULL,NULL,false)"
    )
    async with server(environment) as client:
        expiry = await observer.fetchval(
            "SELECT clock_timestamp()+interval '900 milliseconds'"
        )
        token = (
            signed(f"B:{int(expiry.timestamp() * 1000)}:3")
            if change == "expired"
            else B
        )
        headers = {"Authorization": f"Bearer {token}"}
        # Namespace is the shared public concurrency boundary for invitation/alias operations.
        async with observer.transaction():
            await observer.execute("SELECT pg_advisory_xact_lock(728323)")
            task = asyncio.create_task(
                client.get(ROOT, headers=headers)
                if operation == "list"
                else client.post(
                    RESET if operation == "reset" else ROOT + "/" + operation,
                    headers=headers,
                    json={"code": "UNUSED", "id": "A", "note": "no write"},
                )
            )
            async with asyncio.timeout(1.5):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%administration.%')"
                    ):
                        break
                    await asyncio.sleep(0.01)
            if change == "expired":
                await observer.execute(
                    "SELECT pg_sleep(greatest(0,extract(epoch FROM ($1::timestamptz-clock_timestamp()))))",
                    expiry,
                )
            elif change == "deleted":
                await observer.execute("DELETE FROM identity.users WHERE id='B'")
            else:
                assignments = {
                    "revoked": "session_version=4",
                    "demoted": "is_admin=false",
                    "disabled": "disabled=true",
                }
                await observer.execute(
                    f"UPDATE identity.users SET {assignments[change]} WHERE id='B'"
                )
        response = await task
        assert response.status_code == (403 if change == "demoted" else 401), (
            response.text
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.invitations") == 1
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.password_resets"
        )
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 0
        )


@pytest.mark.asyncio
async def test_reset_alias_conflict_rollback_and_disabled_profile_preserve_other_access(
    identities,
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute("""
        UPDATE identity.users SET display_name=' Ａlice ' WHERE id='A';
        INSERT INTO identity.password_credentials VALUES('A','old-hash',NULL),('B','admin-sentinel',NULL);
        INSERT INTO identity.login_aliases VALUES('alice','B',true,false,NULL);
        INSERT INTO identity.device_links VALUES(decode(repeat('ab',32),'hex'),'A',now(),now()+interval '10 min');
    """)
    async with server(environment) as client:
        response = await client.post(RESET, headers=HEADERS, json={"id": "A"})
        assert response.status_code == 409 and response.json() == {
            "error": "another profile already signs in with this name",
            "code": "name-taken",
        }
        assert (
            await observer.fetchval(
                "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='A'"
            )
            == "old-hash"
        )
        await observer.execute(
            "DELETE FROM identity.login_aliases; INSERT INTO identity.login_aliases VALUES('alice','B',false,false,now()-interval '1 second')"
        )
        await observer.execute("""
            CREATE FUNCTION public.synthetic_fail_reset_link() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic-failure'; END $$;
            CREATE TRIGGER synthetic_fail_reset BEFORE DELETE ON identity.device_links FOR EACH ROW EXECUTE FUNCTION public.synthetic_fail_reset_link();
        """)
        response = await client.post(RESET, headers=HEADERS, json={"id": "A"})
        assert response.status_code == 500 and response.json() == {
            "error": "server error"
        }
        assert "code" not in response.json() and "set-cookie" not in response.headers
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 0
        )
        assert (
            await observer.fetchval(
                "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='A'"
            )
            == "old-hash"
        )
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.password_resets"
        )
        assert (
            await observer.fetchval(
                "SELECT owner_id FROM identity.login_aliases WHERE alias_key='alice'"
            )
            == "B"
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.device_links") == 1
        )
        await observer.execute(
            "DROP TRIGGER synthetic_fail_reset ON identity.device_links; UPDATE identity.users SET disabled=true WHERE id='A'"
        )
        response = await client.post(RESET, headers=HEADERS, json={"id": "A"})
        assert response.status_code == 200 and response.json()["name"] == " Ａlice "
        assert (
            await observer.fetchval(
                "SELECT owner_id FROM identity.login_aliases WHERE alias_key='alice'"
            )
            == "A"
        )
        redeemed = await client.post(
            "/api/v1/login/password-reset",
            json={
                "name": "Alice",
                "code": response.json()["code"],
                "next": "violet river stones",
            },
        )
        assert redeemed.status_code == 403 and redeemed.json()["code"] == "disabled"
        assert await observer.fetchval(
            "SELECT disabled FROM identity.users WHERE id='A'"
        )
        assert (
            await observer.fetchval(
                "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id='B'"
            )
            == "admin-sentinel"
        )
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='B'"
            )
            == 3
        )


@pytest.mark.asyncio
async def test_previous_head_upgrade_catalog_and_no_direct_invitation_access(
    deployment, tmp_path
):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p004_admin_invites.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_external_cleanup"
    )
    await observer.execute("""
        INSERT INTO identity.users(id,display_name,is_admin,session_version) VALUES('A','Alice',false,0),('B','Bob',true,3);
        INSERT INTO identity.invitations VALUES('LEGACY-CODE','historical','deleted-admin',NULL,true,'deleted-owner',NULL,false),('CONSUMED','no owner','deleted-admin',NULL,true,NULL,NULL,false);
    """)
    before = await observer.fetch("SELECT * FROM identity.invitations ORDER BY code")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetch("SELECT * FROM identity.invitations ORDER BY code")
        == before
    )
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_admin_invites"
    )
    functions = await observer.fetch("""SELECT p.oid::regprocedure::text AS signature,p.prosecdef,p.proconfig,
        pg_get_userbyid(p.proowner) AS owner,has_function_privilege('opengym_api_runtime',p.oid,'EXECUTE') AS runtime,
        EXISTS(SELECT FROM aclexplode(p.proacl) WHERE grantee=0 OR (is_grantable AND grantee<>'opengym_administration_executor'::regrole)) AS exposed
        FROM pg_proc p WHERE pronamespace='administration'::regnamespace AND proname IN ('list_invitations','create_invitation','revoke_invitation','issue_reset')""")
    assert {r["signature"] for r in functions} == {
        "administration.list_invitations(text,bigint,timestamp with time zone)",
        "administration.create_invitation(text,bigint,timestamp with time zone,text,text,timestamp with time zone)",
        "administration.revoke_invitation(text,bigint,timestamp with time zone,text)",
        "administration.issue_reset(text,bigint,timestamp with time zone,text,bytea,timestamp with time zone)",
    }
    assert all(
        r["prosecdef"]
        and r["runtime"]
        and not r["exposed"]
        and r["owner"] == "opengym_administration_executor"
        and r["proconfig"] == ["search_path=pg_catalog, pg_temp"]
        for r in functions
    )
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        for query in (
            "SELECT * FROM identity.invitations",
            "DELETE FROM identity.invitations",
            "SET ROLE opengym_administration_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(query)
        assert (
            json.loads(
                await runtime.fetchval(
                    "SELECT administration.list_invitations('A',0,now()+interval '1 day')"
                )
            )
            == {}
        )
        assert (
            await runtime.fetchval(
                "SELECT administration.list_invitations('B',999,now()+interval '1 day')"
            )
            is None
        )
        async with runtime.transaction():
            assert (
                len(
                    json.loads(
                        await runtime.fetchval(
                            "SELECT administration.list_invitations('B',3,now()+interval '1 day')"
                        )
                    )
                )
                == 2
            )
        assert not await runtime.fetchval(
            "SELECT nullif(current_setting('app.owner_id',true),'')"
        )
    finally:
        await runtime.close()
    async with server(environment) as client:
        for code in ("LEGACY-CODE", "CONSUMED"):
            response = await client.post(
                ROOT + "/revoke", headers=HEADERS, json={"code": code}
            )
            assert response.status_code == 400 and response.json() == {
                "error": "already used, cannot revoke"
            }


@pytest.mark.asyncio
async def test_reset_revalidates_after_streaming_body_without_a_database_lease(
    identities,
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    release = asyncio.Event()

    async def body():
        yield b'{"id":'
        await release.wait()
        yield b'"A"}'

    async with server(environment) as client:
        await observer.execute("SELECT pg_advisory_lock(728323)")
        task = asyncio.create_task(client.post(RESET, headers=HEADERS, content=body()))
        try:
            async with asyncio.timeout(3):
                while True:
                    await observer.execute("SELECT pg_stat_clear_snapshot()")
                    if await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%administration.inspect_user%')"
                    ):
                        break
                    await asyncio.sleep(0.01)
            await observer.execute("SELECT pg_advisory_unlock(728323)")
            # Queue behind preflight; reacquisition proves it committed before the body ends.
            await observer.execute("SELECT pg_advisory_lock(728323)")
            await observer.execute(
                "UPDATE identity.users SET session_version=4 WHERE id='B'"
            )
        finally:
            await observer.execute("SELECT pg_advisory_unlock_all()")
            release.set()
        response = await task
        assert response.status_code == 401 and response.json() == {
            "error": "not signed in"
        }
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.password_resets"
        )
        assert (
            await observer.fetchval(
                "SELECT session_version FROM identity.users WHERE id='A'"
            )
            == 0
        )


@pytest.mark.asyncio
async def test_note_utf16_and_unrepresentable_input_fail_without_silent_replacement(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        for value, expected in (
            (123, "123"),
            (True, ""),
            ({}, ""),
            ("é" * 61, "é" * 60),
            ("😀" * 31, "😀" * 30),
        ):
            response = await client.post(
                ROOT + "/new", headers=HEADERS, json={"note": value}
            )
            assert (
                response.status_code == 200
                and response.json()["invite"]["note"] == expected
            )
        before = await observer.fetchval("SELECT count(*) FROM identity.invitations")
        for note in ("x\x00y", "x\ud800y", "x" * 59 + "😀"):
            response = await client.post(
                ROOT + "/new", headers=HEADERS, content=json.dumps({"note": note})
            )
            assert response.status_code == 400 and response.json() == {
                "error": "invalid json"
            }
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.invitations")
            == before
        )
