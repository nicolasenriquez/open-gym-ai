"""Subscription compatibility through real HTTP and restricted PostgreSQL."""

import asyncio
import base64
import json
import shutil
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import A, B, wait_for_actor_locks
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import migration, server

ENDPOINT = "https://push.example/subscription"


@pytest.mark.asyncio
async def test_subscription_transfer_preserves_date_device_and_isolation(identities):
    observer, environment = identities
    async with server(environment) as client:

        async def status(token):
            response = await client.get(
                "/api/v1/push/status",
                params={"endpoint": ENDPOINT},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            return response.json()

        assert await status(A) == {"subscribed": False}
        body = {
            "subscription": {
                "endpoint": ENDPOINT,
                "keys": {"p256dh": "p", "auth": "a"},
            },
            "deviceId": "dev_phone000",
            "owner_id": "B",
        }
        response = await client.post(
            "/api/v1/push/subscribe",
            json=body,
            headers={"Authorization": f"Bearer {A}"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        created = await observer.fetchval(
            "SELECT created_at FROM notifications.subscriptions"
        )
        assert await status(A) == {"subscribed": True, "deviceId": "dev_phone000"}
        assert await status(B) == {"subscribed": False}

        body["deviceId"] = {"invalid": True}
        response = await client.post(
            "/api/v1/push/subscribe",
            json=body,
            headers={"Authorization": f"Bearer {B}"},
        )
        assert response.status_code == 200
        assert await status(A) == {"subscribed": False}
        assert await status(B) == {"subscribed": True, "deviceId": "dev_phone000"}
        assert (
            await observer.fetchval(
                "SELECT created_at FROM notifications.subscriptions"
            )
            == created
        )
        response = await client.post(
            "/api/v1/push/unsubscribe",
            json={"endpoint": ENDPOINT},
            headers={"Authorization": f"Bearer {A}"},
        )
        assert response.json() == {"ok": True}
        assert await status(B) == {"subscribed": True, "deviceId": "dev_phone000"}
        await client.post(
            "/api/v1/push/unsubscribe",
            json={"endpoint": ENDPOINT},
            headers={"Authorization": f"Bearer {B}"},
        )
        assert await status(B) == {"subscribed": False}


@pytest.mark.asyncio
async def test_public_vapid_key_is_persistent_and_never_rotates_corrupt_material(
    identities, tmp_path
):
    _, environment = identities
    environment["DATA_DIR"] = str(tmp_path / "private-data")
    async with server(environment) as client:
        response = await client.get("/api/v1/push/public-key")
        assert response.status_code == 200
        key = response.json()["key"]
        decoded = base64.urlsafe_b64decode(key + "==")
        assert len(decoded) == 65 and decoded[0] == 4
    file = Path(environment["DATA_DIR"]) / "vapid.json"
    original = file.read_bytes()
    assert file.stat().st_mode & 0o777 == 0o600
    async with server(environment) as client:
        assert (await client.get("/api/v1/push/public-key")).json() == {"key": key}
        assert (
            json.loads(original)["privateKey"]
            not in (await client.get("/api/v1/push/public-key")).text
        )
    assert file.read_bytes() == original
    file.write_text('{"publicKey":"unusable"}')
    async with server(environment) as client:
        assert (await client.get("/api/v1/push/public-key")).status_code == 503
    assert file.read_text() == '{"publicKey":"unusable"}'
    # Independent Node createECDH('prime256v1') vector, private scalar 1.
    imported = {
        "publicKey": "BGsX0fLhLEJH-Lzm5WOkQPJ3A32BLeszoPShOUXYmMKWT-NC4v4af5uO5-tKfA-eFivOM1drMV7Oy7ZAaDe_UfU",
        "privateKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE",
    }
    file.write_text(json.dumps(imported))
    async with server(environment) as client:
        assert (await client.get("/api/v1/push/public-key")).json() == {
            "key": imported["publicKey"]
        }
    assert json.loads(file.read_text()) == imported


@pytest.mark.asyncio
async def test_concurrent_subscriptions_prune_only_own_oldest(identities):
    observer, environment = identities
    async with server(environment) as client:

        async def subscribe(index):
            return await client.post(
                "/api/v1/push/subscribe",
                json={
                    "subscription": {
                        "endpoint": f"https://push.example/{index}",
                        "keys": {"p256dh": "p", "auth": "a"},
                    }
                },
                headers={"Authorization": f"Bearer {A}"},
            )

        await observer.execute(
            "INSERT INTO notifications.subscriptions VALUES('https://foreign.example/','B','foreign','key',NULL,'2020-01-01')"
        )
        responses = await asyncio.gather(*(subscribe(index) for index in range(24)))
        assert all(response.status_code == 200 for response in responses)
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM notifications.subscriptions WHERE owner_id='A'"
            )
            == 20
        )
        assert (
            await observer.fetchval(
                "SELECT p256dh FROM notifications.subscriptions WHERE owner_id='B'"
            )
            == "foreign"
        )
        oldest = await observer.fetchval(
            "SELECT endpoint FROM notifications.subscriptions WHERE owner_id='A' ORDER BY created_at LIMIT 1"
        )
        await subscribe("last")
        assert not (
            await client.get(
                "/api/v1/push/status",
                params={"endpoint": oldest},
                headers={"Authorization": f"Bearer {A}"},
            )
        ).json()["subscribed"]


@pytest.mark.asyncio
async def test_validation_and_private_literal_forms_match_legacy(identities):
    observer, environment = identities
    async with server(environment) as client:

        async def subscribe(endpoint, **extra):
            return await client.post(
                "/api/v1/push/subscribe",
                json={
                    "subscription": {
                        "endpoint": endpoint,
                        "keys": {"p256dh": "p", "auth": "a"},
                    },
                    **extra,
                },
                headers={"Authorization": f"Bearer {A}"},
            )

        for endpoint in (
            "https://[::ffff:127.0.0.1]/x",
            "https://[::FFFF:C0A8:0101]/x",
            "https://[::1]/x",
            "https://[fe80::1]/x",
            "https://[fd00::1]/x",
            "https://127.0.0.1/x",
            "https://2130706433/x",
            "https://0x7f000001/x",
            "https://127.1/x",
        ):
            response = await subscribe(endpoint)
            assert response.status_code == 400, endpoint
            assert response.json() == {
                "error": "endpoint must not point at a private address"
            }
        for endpoint in (
            "https://[::ffff:8.8.8.8]/x",
            "https://[2606:4700::1111]/x",
            "https://8.8.8.8/x",
            "https://push.example/x",
        ):
            assert (await subscribe(endpoint)).status_code == 200
        for endpoint in (
            "http://push.example",
            "https://user:pass@push.example",
            "not-a-url",
            "https://push.example:99999/x",
            "https://push.example\x00/x",
        ):
            assert (await subscribe(endpoint)).status_code == 400
        assert (
            await client.post(
                "/api/v1/push/subscribe",
                json={"subscription": []},
                headers={"Authorization": f"Bearer {A}"},
            )
        ).status_code == 400
        assert (
            await observer.fetchval("SELECT count(*) FROM notifications.subscriptions")
            == 4
        )
        response = await client.get(
            "/api/v1/push/status",
            params={"endpoint": "bad\x00endpoint"},
            headers={"Authorization": f"Bearer {A}"},
        )
        assert response.status_code == 200
        assert response.json() == {"subscribed": False}


@pytest.mark.asyncio
async def test_subscription_auth_csrf_and_revocation_during_endpoint_lock(identities):
    observer, environment = identities
    body = {
        "subscription": {"endpoint": ENDPOINT, "keys": {"p256dh": "p", "auth": "a"}}
    }
    async with server(environment) as client:
        for method, route in (
            ("GET", "status"),
            ("POST", "subscribe"),
            ("POST", "unsubscribe"),
        ):
            assert (
                await client.request(method, "/api/v1/push/" + route, json=body)
            ).status_code == 401
        assert (
            await client.post(
                "/api/v1/push/subscribe",
                json=body,
                headers={"Cookie": f"gymsid={A}", "Origin": "https://foreign.example"},
            )
        ).status_code == 403
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/push/subscribe",
                    json=body,
                    headers={"Authorization": f"Bearer {A}"},
                )
            )
            await wait_for_actor_locks(observer, 1)
            await observer.execute(
                "UPDATE identity.users SET session_version=1 WHERE id='A'"
            )
        assert (await pending).status_code == 401
        assert (
            await observer.fetchval("SELECT count(*) FROM notifications.subscriptions")
            == 0
        )
        response = await client.get(
            "/api/v1/push/status", headers={"Authorization": f"Bearer {B}"}
        )
        assert (
            response.status_code == 200
            and response.headers["cache-control"] == "no-store"
        )


@pytest.mark.asyncio
async def test_session_is_revalidated_after_waiting_for_global_endpoint_lock(
    identities,
):
    observer, environment = identities
    async with server(environment) as client:
        await observer.execute("SELECT pg_advisory_lock(728324)")
        try:
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/push/subscribe",
                    json={
                        "subscription": {
                            "endpoint": ENDPOINT,
                            "keys": {"p256dh": "p", "auth": "a"},
                        }
                    },
                    headers={"Authorization": f"Bearer {A}"},
                )
            )
            async with asyncio.timeout(1.5):
                while not await observer.fetchval(
                    "SELECT EXISTS(SELECT FROM pg_locks WHERE locktype='advisory' AND objid=728324 AND NOT granted)"
                ):
                    await asyncio.sleep(0.01)
            await observer.execute(
                "UPDATE identity.users SET session_version=1 WHERE id='A'"
            )
        finally:
            await observer.execute("SELECT pg_advisory_unlock(728324)")
        assert (await pending).status_code == 401
        assert (
            await observer.fetchval("SELECT count(*) FROM notifications.subscriptions")
            == 0
        )


@pytest.mark.asyncio
async def test_private_address_exception_is_explicit_and_bounded(identities):
    _, environment = identities
    environment["ALLOWED_PRIVATE_IPS"] = (
        "invalid,192.168.1.0/24,10.1.0.2-10.1.0.4,fd00::1,::ffff:10.2.0.1"
    )
    async with server(environment) as client:
        for address, expected in (
            ("192.168.1.2", 200),
            ("192.168.2.2", 400),
            ("10.1.0.3", 200),
            ("10.1.0.5", 400),
            ("[fd00::1]", 200),
            ("[fd00::2]", 400),
            ("[::ffff:192.168.1.2]", 200),
            ("[::ffff:10.2.0.1]", 200),
        ):
            response = await client.post(
                "/api/v1/push/subscribe",
                json={
                    "subscription": {
                        "endpoint": f"https://{address}/",
                        "keys": {"p256dh": "p", "auth": "a"},
                    }
                },
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == expected, address


@pytest.mark.asyncio
async def test_unrepresentable_keys_are_rejected_and_invalid_device_is_ignored(
    identities,
):
    _, environment = identities
    async with server(environment) as client:
        for keys, device, expected in (
            ({"p256dh": "p", "auth": "a"}, "bad\x00device", 200),
            ({"p256dh": "\ud800", "auth": "a"}, None, 400),
        ):
            response = await client.post(
                "/api/v1/push/subscribe",
                content=json.dumps(
                    {
                        "subscription": {"endpoint": ENDPOINT, "keys": keys},
                        "deviceId": device,
                    }
                ),
                headers={"Authorization": f"Bearer {A}"},
            )
            assert response.status_code == expected


@pytest.mark.asyncio
async def test_upgrade_and_runtime_cannot_enumerate_or_impersonate_subscriptions(
    deployment, tmp_path
):
    observer, environment = deployment
    previous = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        previous,
        ignore=shutil.ignore_patterns(
            "p005_delivery.py", "p004_admin_users.py", "p005_subscriptions.py"
        ),
    )
    await migration({**environment, "PYTHONPATH": str(previous.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p003_coach_client"
    )
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM alembic_version")
        == "p005_delivery"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES('A','Alice'),('B','Bob'); INSERT INTO notifications.subscriptions VALUES('https://push.example/foreign','B','p','a',NULL,now())"
    )
    runtime = await asyncpg.connect(
        host="db",
        database="opengym_dev",
        user="opengym_api_runtime",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"]).read_text(),
        ssl=False,
    )
    try:
        assert await runtime.fetch("SELECT * FROM notifications.subscriptions") == []
        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.owner_id','A',true)")
            assert (
                await runtime.fetch("SELECT * FROM notifications.subscriptions") == []
            )
            assert (
                await runtime.execute("DELETE FROM notifications.subscriptions")
                == "DELETE 0"
            )
            assert not await runtime.fetchval(
                "SELECT notifications.upsert_subscription('B',999,now()+interval '1 day','https://push.example/foreign','x','x',NULL,now())"
            )
        for statement in (
            "SET ROLE opengym_notifications_executor",
            "INSERT INTO notifications.subscriptions VALUES('https://push.example/x','B','p','a',NULL,now())",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(statement)
    finally:
        await runtime.close()
    row = await observer.fetchrow(
        "SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,NOT EXISTS(SELECT FROM aclexplode(proacl) WHERE grantee=0) AS private FROM pg_proc WHERE oid='notifications.upsert_subscription(text,bigint,timestamptz,text,text,text,text,timestamptz)'::regprocedure"
    )
    assert tuple(row) == (
        True,
        ["search_path=pg_catalog, pg_temp"],
        "opengym_notifications_executor",
        True,
    )
    assert await observer.fetchval(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='notifications.subscriptions'::regclass"
    )
    assert not await observer.fetchval(
        "SELECT rolcanlogin OR rolsuper OR rolbypassrls FROM pg_roles WHERE rolname='opengym_notifications_executor'"
    )
