"""Compatible audit through restricted HTTP and independent PostgreSQL observation."""

import asyncio
import json
import shutil
import time
from pathlib import Path

import asyncpg
import pytest
from test_identity_password import HASH, PASSWORD
from test_identity_session import A, B, signed
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

HEADERS = {"Authorization": f"Bearer {B}"}
ROOT = "/api/v1/admin/audit"


@pytest.mark.asyncio
async def test_admin_read_clear_preserves_sequence_and_denies_foreign_actor(identities):
    observer, environment = identities
    async with server(environment) as client:
        response = await client.get(ROOT, headers=HEADERS)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["events"] == [] and data["total"] == 0
        assert data["enabled"] and data["ip_mode"] == "off"
        assert data["retention"] == {"max": 5000, "days": 90}
        assert data["nextBefore"] is None
        for method, path in (("GET", ROOT), ("POST", ROOT + "/clear")):
            assert (await client.request(method, path)).status_code == 401
            assert (
                await client.request(
                    method, path, headers={"Authorization": f"Bearer {A}"}
                )
            ).status_code == 403
        response = await client.post(ROOT + "/clear", headers=HEADERS)
        assert response.status_code == 200 and response.json() == {"ok": True}
        first = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert len(first) == 1 and first[0]["ev"] == "admin.audit.clear"
        assert first[0]["uid"] == "B" and first[0]["name"] == "Bob" and first[0]["ok"]
        assert "ip" not in first[0]
        await client.post(ROOT + "/clear", headers=HEADERS)
        second = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert len(second) == 1 and second[0]["id"] > first[0]["id"]
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 1


@pytest.mark.asyncio
async def test_business_events_and_failed_append_never_change_committed_success(
    identities,
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute(
        "INSERT INTO identity.password_credentials VALUES('A',$1,NULL)", HASH
    )
    await observer.execute(
        "INSERT INTO identity.login_aliases VALUES('alice','A',false,true,NULL)"
    )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/login/password", json={"identifier": "Alice", "password": PASSWORD}
        )
        assert response.status_code == 200 and "set-cookie" in response.headers
        client.cookies.clear()
        response = await client.post(
            "/api/v1/admin/user/disable",
            headers=HEADERS,
            json={"id": "A", "disabled": True},
        )
        assert response.status_code == 200
        rows = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert [r["ev"] for r in rows] == ["admin.user.disable", "auth.password.ok"]
        assert rows[0]["uid"] == "B" and rows[0]["tgt"] == "A"
        assert rows[0]["name"] == "Bob" and rows[0]["tname"] == "Alice"
        assert rows[1]["uid"] == "A" and rows[1]["name"] == "Alice"
        assert all("ip" not in r for r in rows)
        await observer.execute("""CREATE FUNCTION public.reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'private-marker-must-not-be-logged'; END $$;
            CREATE TRIGGER reject_audit BEFORE INSERT ON audit.events FOR EACH ROW EXECUTE FUNCTION public.reject_audit();""")
        response = await client.post(
            "/api/v1/admin/user/disable",
            headers=HEADERS,
            json={"id": "A", "disabled": False},
        )
        assert response.status_code == 200 and not await observer.fetchval(
            "SELECT disabled FROM identity.users WHERE id='A'"
        )
        response = await client.post(
            "/api/v1/login/password", json={"identifier": "Alice", "password": PASSWORD}
        )
        assert response.status_code == 200 and "set-cookie" in response.headers
        assert (await client.get("/api/v1/me")).status_code == 200
        client.cookies.clear()
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 2
        await observer.execute("DROP TRIGGER reject_audit ON audit.events")
        response = await client.post(
            "/api/v1/admin/user/delete", headers=HEADERS, json={"id": "A"}
        )
        assert response.status_code == 200
        rows = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert rows[0]["ev"] == "admin.user.delete" and rows[0]["msg"] == "Alice"
        assert len(rows) == 3 and rows[-1]["uid"] == "A"
        assert not await observer.fetchval(
            "SELECT count(*) FROM identity.users WHERE id='A'"
        )


@pytest.mark.asyncio
async def test_retention_filters_and_id_cursor_with_concurrent_insert(identities):
    observer, environment = identities
    environment.update(AUDIT_MAX="3", AUDIT_DAYS="1")
    await observer.execute("""INSERT INTO audit.events(occurred_at,event,ok)
        VALUES(now()-interval '2 days','auth.password.fail',false),
        (now(),'auth.password.ok',true),(now(),'admin.invite.create',true),
        (now(),'auth.login.fail',false),(now(),'admin.user.disable',true);""")
    async with server(environment) as client:
        first = (await client.get(ROOT + "?limit=2", headers=HEADERS)).json()
        assert [e["id"] for e in first["events"]] == [5, 4]
        assert first["total"] == 3 and first["nextBefore"] == 4
        fractional = (await client.get(ROOT + "?limit=2.5", headers=HEADERS)).json()
        assert len(fractional["events"]) == 2 and fractional["nextBefore"] is None
        negative_infinity = (
            await client.get(ROOT + "?before=-Infinity", headers=HEADERS)
        ).json()
        assert negative_infinity["events"] == []
        assert await observer.fetchval(
            "SELECT array_agg(id ORDER BY id) FROM audit.events"
        ) == [3, 4, 5]
        failed = (await client.get(ROOT + "?cat=fail", headers=HEADERS)).json()
        assert failed["total"] == 1 and failed["events"][0]["id"] == 4
        admin = (await client.get(ROOT + "?cat=admin", headers=HEADERS)).json()
        assert [e["id"] for e in admin["events"]] == [5, 3]
        await client.post(
            "/api/v1/admin/invites/new", headers=HEADERS, json={"note": "private-note"}
        )
        page = (await client.get(ROOT + "?limit=2&before=4", headers=HEADERS)).json()
        assert page["events"] == [] and page["total"] == 3
        assert (await client.get(ROOT + "?cat=does-not-exist", headers=HEADERS)).json()[
            "total"
        ] == 0
        for query in (
            "?limit=bogus&before=bogus",
            "?limit=0",
            "?limit=201",
            "?limit=-1",
            "?before=1e40",
            "?cat=%00",
        ):
            assert (await client.get(ROOT + query, headers=HEADERS)).status_code == 200
    # Retention changes apply at read, even when no event has been appended since restart.
    await observer.execute(
        "UPDATE audit.events SET occurred_at=now()-interval '2 days'"
    )
    async with server(environment) as client:
        assert (await client.get(ROOT, headers=HEADERS)).json()["events"] == []
    environment.update(AUDIT_MAX="0", AUDIT_DAYS="0")
    async with server(environment) as client:
        await client.post(ROOT + "/clear", headers=HEADERS)
        latest = (await client.get(ROOT, headers=HEADERS)).json()["events"][0]
        assert latest["id"] > 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,raw,expected",
    [
        ("off", "203.0.113.27", None),
        ("net", "203.0.113.27", "203.0.113.0/24"),
        ("full", "203.0.113.27", "203.0.113.27"),
        ("net", "2001:db8:abcd:1234::1", "2001:db8:abcd::/48"),
        ("full", "not-an-ip-private-marker", None),
        ("full", "fe80::1%private-marker", None),
    ],
)
async def test_ip_policy_and_sensitive_payloads_never_stored(
    identities, mode, raw, expected
):
    observer, environment = identities
    environment["AUDIT_IP"] = mode
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/admin/invites/new",
            headers={
                **HEADERS,
                "CF-Connecting-IP": raw,
                "User-Agent": "private-agent-marker",
            },
            json={
                "note": "private-note-marker",
                "password": "private-password-marker",
                "token": "private-token-marker",
            },
        )
        assert response.status_code == 200
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert len(events) == 1 and events[0].get("ip") == expected
        stored = await observer.fetchval(
            "SELECT row_to_json(e)::text FROM audit.events e"
        )
        assert (
            "private-" not in stored and response.json()["invite"]["code"] not in stored
        )


@pytest.mark.asyncio
async def test_disabled_audit_reads_history_but_clear_and_business_do_not_append(
    identities,
):
    observer, environment = identities
    environment["AUDIT_LOG"] = "off"
    await observer.execute(
        "INSERT INTO audit.events(occurred_at,event,ok) VALUES(now(),'auth.login.ok',true)"
    )
    async with server(environment) as client:
        before = (await client.get(ROOT, headers=HEADERS)).json()
        assert before["total"] == 1 and not before["enabled"]
        await client.post(ROOT + "/clear", headers=HEADERS)
        await client.post("/api/v1/admin/invites/new", headers=HEADERS, json={})
        assert (await client.get(ROOT, headers=HEADERS)).json()["events"] == []
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 0


@pytest.mark.asyncio
async def test_zero_invalid_and_negative_retention_keep_node_configuration(identities):
    _, environment = identities
    environment.update(AUDIT_MAX="invalid", AUDIT_DAYS="-1")
    async with server(environment) as client:
        result = (await client.get(ROOT, headers=HEADERS)).json()
        assert result["retention"] == {"max": 0, "days": 0}
        response = await client.get(ROOT + "?before=-1e40", headers=HEADERS)
        assert response.json()["events"] == []


@pytest.mark.asyncio
async def test_failure_is_observable_safe_and_recovers_without_retry(
    identities, monkeypatch, caplog
):
    from opengym_platform.audit.service import Audit
    from opengym_platform.core.database import Database

    observer, environment = identities
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    database = await Database.open_platform()
    audit = Audit(database)
    try:
        await observer.execute("""CREATE FUNCTION public.fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'private-failure-marker'; END $$;
            CREATE TRIGGER fail_audit BEFORE INSERT ON audit.events FOR EACH ROW EXECUTE FUNCTION public.fail_audit();""")
        for _ in range(2):
            await audit.append("auth.login.ok", actor="A")
        assert audit.degraded and audit.failures == 2
        assert caplog.text.count("AUDIT_WRITE_FAILED") == 1
        assert "private-failure-marker" not in caplog.text
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 0
        import logging

        def failed_sink(*args, **kwargs):
            raise OSError("private-sink-marker")

        with monkeypatch.context() as fault:
            fault.setattr(logging.Logger, "warning", failed_sink)
            other = Audit(database)
            await other.append("auth.login.ok", actor="A")
            assert other.degraded and other.failures == 1
        await observer.execute("DROP TRIGGER fail_audit ON audit.events")
        await audit.append("auth.login.ok", actor="A")
        assert not audit.degraded and audit.failures == 2
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 1
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_admin_revocation_and_expiry_after_audit_lock_wait(identities):
    observer, environment = identities
    async with server(environment) as client:
        await observer.execute("SELECT pg_advisory_lock(728323)")
        task = asyncio.create_task(client.get(ROOT, headers=HEADERS))
        try:
            async with asyncio.timeout(3):
                while not await observer.fetchval(
                    "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%audit.read_events%')"
                ):
                    await asyncio.sleep(0.01)
            await observer.execute(
                "UPDATE identity.users SET session_version=4 WHERE id='B'"
            )
        finally:
            await observer.execute("SELECT pg_advisory_unlock_all()")
        assert (await task).status_code == 401
        assert (await client.post(ROOT + "/clear", headers=HEADERS)).status_code == 401
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 0


@pytest.mark.asyncio
async def test_anonymous_failures_are_bounded_without_refusing_requests_and_logout_is_logged(
    identities,
):
    _, environment = identities
    environment["TRUST_PROXY"] = "1"
    async with server(environment) as client:
        for _ in range(30):
            response = await client.post(
                "/api/v1/pair/redeem", json={"code": "invalid-private-marker"}
            )
            assert response.status_code == 400
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert len(events) == 10 and all(
            e["ev"] == "auth.pair.fail" and not e["ok"] for e in events
        )
        assert "invalid-private-marker" not in json.dumps(events)
        for source in range(12):
            for _ in range(10):
                response = await client.post(
                    "/api/v1/pair/redeem",
                    headers={"X-Forwarded-For": f"203.0.113.{source + 1}"},
                    json={"code": "invalid"},
                )
                assert response.status_code == 400
        assert (await client.get(ROOT, headers=HEADERS)).json()["total"] == 120
        response = await client.post(
            "/api/v1/logout", headers={"Cookie": f"gymsid={A}"}
        )
        assert response.status_code == 200 and response.json() == {"ok": True}
        assert "Max-Age=0" in response.headers["set-cookie"]
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert events[0]["ev"] == "auth.logout" and events[0]["uid"] == "A"


@pytest.mark.asyncio
async def test_clear_commits_even_when_its_separate_append_fails(identities):
    observer, environment = identities
    await observer.execute("""INSERT INTO audit.events(occurred_at,event,ok) VALUES(now(),'auth.login.ok',true);
        CREATE FUNCTION public.reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'private-clear-marker'; END $$;
        CREATE TRIGGER reject_audit BEFORE INSERT ON audit.events FOR EACH ROW EXECUTE FUNCTION public.reject_audit();""")
    async with server(environment) as client:
        response = await client.post(ROOT + "/clear", headers=HEADERS)
        assert response.status_code == 200 and response.json() == {"ok": True}
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 0
        await observer.execute("DROP TRIGGER reject_audit ON audit.events")
        await client.post(ROOT + "/clear", headers=HEADERS)
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert len(events) == 1 and events[0]["id"] > 1


@pytest.mark.asyncio
async def test_expiry_after_audit_lock_cannot_clear_history(identities):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO audit.events(occurred_at,event,ok) VALUES(now(),'auth.login.ok',true)"
    )
    async with server(environment) as client:
        await observer.execute("SELECT pg_advisory_lock(728325)")
        token = signed(f"B:{int(time.time() * 1000) + 1500}:3")
        task = asyncio.create_task(
            client.post(ROOT + "/clear", headers={"Authorization": f"Bearer {token}"})
        )
        try:
            async with asyncio.timeout(3):
                while not await observer.fetchval(
                    "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%audit.clear_events%')"
                ):
                    await asyncio.sleep(0.01)
            await asyncio.sleep(1.6)
        finally:
            await observer.execute("SELECT pg_advisory_unlock_all()")
        assert (await task).status_code == 401
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 1


@pytest.mark.asyncio
async def test_failed_passkey_add_link_options_and_signup_keep_failure_events(
    identities,
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute(
        "INSERT INTO identity.login_aliases VALUES('a@example.test','A',true,false,NULL)"
    )
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/account/passkeys/verify",
            headers={"Authorization": f"Bearer {A}"},
            json={"cid": "invalid", "credential": {"id": "private-id-marker"}},
        )
        assert response.status_code == 400
        response = await client.post(
            "/api/v1/device-link/options", json={"code": "invalid-private-marker"}
        )
        assert response.status_code == 400
        response = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Visitor",
                "email": "a@example.test",
                "password": "violet river stones",
            },
        )
        assert response.status_code == 409 and response.json()["code"] == "email-taken"
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert [e["ev"] for e in events] == [
            "auth.register.fail",
            "auth.link.fail",
            "auth.passkey.fail",
        ]
        assert all(not e["ok"] for e in events)
        assert "private-" not in json.dumps(
            events
        ) and "a@example.test" not in json.dumps(events)


@pytest.mark.asyncio
async def test_audit_does_not_wait_for_notification_endpoint_lock(identities):
    observer, environment = identities
    async with server(environment) as client:
        await observer.execute("SELECT pg_advisory_lock(728324)")
        try:
            response = await client.get(ROOT, headers=HEADERS, timeout=4)
            assert response.status_code == 200, response.text
        finally:
            await observer.execute("SELECT pg_advisory_unlock_all()")


@pytest.mark.asyncio
async def test_noop_password_removal_does_not_invent_a_business_event(identities):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    async with server(environment) as client:
        response = await client.request(
            "DELETE",
            "/api/v1/account/password",
            headers={"Authorization": f"Bearer {A}"},
            json={},
        )
        assert response.status_code == 200
        assert await observer.fetchval("SELECT count(*) FROM audit.events") == 0


@pytest.mark.asyncio
async def test_password_pause_is_audited_once_without_password_or_identifier(
    identities,
):
    observer, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    await observer.execute(
        "INSERT INTO identity.password_credentials VALUES('A',$1,NULL)", HASH
    )
    await observer.execute(
        "INSERT INTO identity.login_aliases VALUES('alice','A',false,true,NULL)"
    )
    async with server(environment) as client:
        for _ in range(6):
            response = await client.post(
                "/api/v1/login/password",
                json={"identifier": "Alice", "password": "private-wrong-marker"},
            )
            assert response.status_code == 401
        for _ in range(2):
            assert (
                await client.post(
                    "/api/v1/login/password",
                    json={"identifier": "Alice", "password": "private-wrong-marker"},
                )
            ).status_code == 429
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        paused = [e for e in events if e["ev"] == "auth.password.locked"]
        assert len(paused) == 1 and paused[0]["uid"] == "A"
        assert len([e for e in events if e["ev"] == "auth.throttled"]) <= 1
        assert "private-wrong-marker" not in json.dumps(events)
        await observer.execute(
            "INSERT INTO identity.password_credentials VALUES('B',$1,NULL)", HASH
        )
        for _ in range(6):
            response = await client.post(
                "/api/v1/account/password",
                headers=HEADERS,
                json={
                    "next": "amber mountains sunlight",
                    "current": "private-proof-marker",
                },
            )
            assert response.status_code == 403
        events = (await client.get(ROOT, headers=HEADERS)).json()["events"]
        assert (
            len(
                [
                    e
                    for e in events
                    if e["ev"] == "auth.password.locked" and e.get("uid") == "B"
                ]
            )
            == 1
        )
        proof = next(e for e in events if e["ev"] == "auth.proof.fail")
        assert proof["act"] == "password" and proof["msg"] == "bad-current"


@pytest.mark.asyncio
async def test_upgrade_and_catalog_only_grants_three_functions(deployment, tmp_path):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns("p004_audit.py"),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p004_admin_invites"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name,is_admin,session_version) VALUES('A','Alice',false,0),('B','Bob',true,3)"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    functions = await observer.fetch("""SELECT p.oid::regprocedure::text AS signature,p.prosecdef,p.proconfig,
        pg_get_userbyid(p.proowner) AS owner,has_function_privilege('opengym_api_runtime',p.oid,'EXECUTE') AS runtime,
        EXISTS(SELECT FROM aclexplode(p.proacl) WHERE grantee=0 OR (is_grantable AND grantee<>'opengym_administration_executor'::regrole)) AS exposed
        FROM pg_proc p WHERE pronamespace='audit'::regnamespace""")
    assert {r["signature"] for r in functions} == {
        "audit.append_event(timestamp with time zone,text,boolean,text,text,text,text,text,text,text)",
        "audit.read_events(text,bigint,timestamp with time zone,bigint,integer)",
        "audit.clear_events(text,bigint,timestamp with time zone)",
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
            "SELECT * FROM audit.events",
            "DELETE FROM audit.events",
            "TRUNCATE audit.events RESTART IDENTITY",
            "SELECT nextval('audit.events_id_seq')",
            "SET ROLE opengym_administration_executor",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(query)
        assert (
            json.loads(
                await runtime.fetchval(
                    "SELECT audit.read_events('A',0,now()+interval '1 day',NULL,100)"
                )
            )
            == {}
        )
        assert (
            await runtime.fetchval(
                "SELECT audit.clear_events('B',999,now()+interval '1 day')"
            )
            is None
        )
        assert (
            await runtime.fetchval(
                "SELECT audit.read_events('B',3,now()-interval '1 second',NULL,100)"
            )
            is None
        )
    finally:
        await runtime.close()
