"""Activity and device alerts through HTTP, restricted SQL and private push."""

import asyncio
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from test_identity_session import A, B, wait_for_actor_locks
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_notification_delivery import runtime_environment, seed

from opengym_platform.application import create_app


@pytest_asyncio.fixture
async def alerts(identities, monkeypatch):
    observer, environment = identities
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append((subscription["endpoint"], payload))
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            yield observer, client, calls


async def post(client, path, body=None, token=A):
    response = await client.post(
        "/api/v1/" + path, json=body or {}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_test_push_uses_only_callers_subscriptions_and_language(
    identities, monkeypatch
):
    observer, environment = identities
    await seed(observer, {"lang": "pt-BR"})
    await seed(observer, {}, "B")
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append((subscription["endpoint"], payload))
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            response = await client.post(
                "/api/v1/push/test",
                headers={"Authorization": f"Bearer {A}"},
                json={"owner_id": "B"},
            )
            assert response.status_code == 200
            assert response.json() == {"ok": True}
    assert calls == [
        (
            "https://push.example/A",
            {
                "title": "openGym",
                "body": "Notificação de teste ✅ É assim que os alertas aparecem.",
                "tag": "test",
            },
        )
    ]


@pytest.mark.asyncio
async def test_rest_alert_selects_device_and_legacy_but_not_other_owner(
    identities, monkeypatch
):
    observer, environment = identities
    await seed(observer, {"lang": "pt-BR"})
    await seed(observer, {}, "B")
    await observer.execute(
        "INSERT INTO notifications.subscriptions VALUES('https://push.example/phone','A','p','a','phone000',now()),('https://push.example/desktop','A','p','a','desktop0',now())"
    )
    runtime_environment(monkeypatch, environment)
    calls = []
    ready = asyncio.Event()

    async def send(subscription, payload):
        calls.append((subscription["endpoint"], payload))
        if len(calls) == 2:
            ready.set()
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            await post(
                client,
                "push/rest-timer",
                {"seconds": "1", "deviceId": "phone000", "owner_id": "B"},
            )
            await post(client, "push/rest-timer/cancel", {"deviceId": "phone000"}, B)
            await asyncio.wait_for(ready.wait(), 4)
    assert {endpoint for endpoint, _ in calls} == {
        "https://push.example/A",
        "https://push.example/phone",
    }
    assert all(
        payload
        == {
            "title": "Descanso terminado 💪",
            "body": "Hora da próxima série.",
            "tag": "rest-timer",
        }
        for _, payload in calls
    )


@pytest.mark.asyncio
async def test_activity_is_visible_only_to_admin_and_expires_after_hidden_or_ttl(
    identities, monkeypatch
):
    _, environment = identities
    runtime_environment(monkeypatch, environment)
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client,
    ):
        await post(
            client,
            "activity",
            {
                "active": True,
                "name": "Strength",
                "exIdx": "2",
                "exTotal": 5,
                "setsDone": 3,
                "setsTotal": 12,
                "startedAt": 1000,
                "owner_id": "B",
            },
        )
        from opengym_platform.notifications import activity

        clock = [1000000]
        monkeypatch.setattr(activity, "now_ms", lambda: clock[0])
        await post(
            client,
            "activity",
            {
                "active": True,
                "name": "Strength",
                "exIdx": "2",
                "exTotal": 5,
                "setsDone": 3,
                "setsTotal": 12,
                "startedAt": 1000,
            },
        )

        async def live():
            response = await client.get(
                "/api/v1/admin/users", headers={"Authorization": f"Bearer {B}"}
            )
            assert response.status_code == 200
            users = {u["id"]: u for u in response.json()["users"]}
            assert users["B"]["live"] is None
            return users["A"]["live"]

        expected = {
            "name": "Strength",
            "exIdx": 2,
            "exTotal": 5,
            "setsDone": 3,
            "setsTotal": 12,
            "startedAt": 1000,
            "updatedAt": 1000000,
        }
        assert await live() == expected
        assert (
            await client.get(
                "/api/v1/admin/users", headers={"Authorization": f"Bearer {A}"}
            )
        ).status_code == 403
        await post(client, "activity", {"active": False, "reason": "hidden"})
        clock[0] += 44000
        await post(client, "activity", {"active": False, "reason": "hidden"})
        assert await live() == expected
        clock[0] += 1000
        assert await live() is None
        await post(client, "activity", {"active": True})
        clock[0] += 69999
        assert await live() is not None
        clock[0] += 1
        assert await live() is None
        await post(client, "activity", {"active": True})
        await post(client, "activity", {"active": False, "reason": "hidden"})
        clock[0] += 44000
        await post(client, "activity", {"active": True})
        clock[0] += 44000
        assert await live() is not None
        await post(client, "activity", {"active": True})
        await post(client, "activity", {"active": False, "reason": "navigated"})
        assert await live() is None
        await post(client, "activity", {"active": True})
        await post(client, "admin/user/disable", {"id": "A", "disabled": True}, B)
        await post(client, "admin/user/disable", {"id": "A", "disabled": False}, B)
        assert await live() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["activity", "push/test", "push/rest-timer", "push/rest-timer/cancel"]
)
async def test_activity_routes_reject_anonymous_cross_origin_and_revoked_actors(
    alerts, path
):
    observer, client, calls = alerts
    url = "/api/v1/" + path
    assert (await client.post(url, json={})).status_code == 401
    assert (
        await client.post(
            url,
            json={},
            headers={"cookie": "og_session=" + A, "origin": "https://evil.example"},
        )
    ).status_code == 403
    for body in (b"[1]", b"bad-json", b'{"seconds":NaN}', b"[" * 2000):
        response = await client.post(
            url, content=body, headers={"Authorization": f"Bearer {A}"}
        )
        assert response.status_code == (200 if path == "push/test" else 400)
    await observer.execute("UPDATE identity.users SET session_version=1 WHERE id='A'")
    response = await client.post(
        url, content=b"bad-json", headers={"Authorization": f"Bearer {A}"}
    )
    assert response.status_code == 401
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["activity", "push/test", "push/rest-timer", "push/rest-timer/cancel"]
)
async def test_activity_revalidates_actor_after_waiting_for_account_lock(alerts, path):
    observer, client, calls = alerts
    async with observer.transaction():
        await observer.execute("SELECT id FROM identity.users WHERE id='A' FOR UPDATE")
        pending = asyncio.create_task(
            client.post(
                "/api/v1/" + path,
                json={"active": True, "seconds": 1},
                headers={"Authorization": f"Bearer {A}"},
            )
        )
        await wait_for_actor_locks(observer, 1)
        await observer.execute("UPDATE identity.users SET disabled=true WHERE id='A'")
    assert (await pending).status_code == 401
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "seconds", [None, False, True, [], {}, "", "wrong", "inf", "1_0", 0, -1, 0.99]
)
async def test_rest_seconds_must_be_a_number_or_numeric_string_at_least_one(
    alerts, seconds
):
    _, client, calls = alerts
    response = await client.post(
        "/api/v1/push/rest-timer",
        json={"seconds": seconds},
        headers={"Authorization": f"Bearer {A}"},
    )
    assert response.status_code == 400
    assert response.json() == {"error": "seconds required"}
    assert calls == []


@pytest.mark.asyncio
async def test_replacement_device_cancel_and_legacy_cancel_are_owner_scoped(alerts):
    observer, client, calls = alerts
    await seed(observer, {})
    await seed(observer, {}, "B")
    await observer.execute(
        "UPDATE notifications.subscriptions SET device_id='phone000' WHERE owner_id='A'"
    )
    await post(client, "push/rest-timer", {"seconds": 1, "deviceId": "phone000"})
    await post(client, "push/rest-timer", {"seconds": 99999, "deviceId": "phone000"})
    await post(client, "push/rest-timer", {"seconds": 1, "deviceId": "desktop0"})
    await post(client, "push/rest-timer", {"seconds": 1}, B)
    await post(client, "push/rest-timer/cancel", {"deviceId": "desktop0"})
    await asyncio.sleep(1.2)
    assert [endpoint for endpoint, _ in calls] == ["https://push.example/B"]
    calls.clear()
    # Invalid/missing ids retain the old account-wide send/cancel behavior.
    await post(client, "push/rest-timer", {"seconds": "0x1", "deviceId": "bad"})
    await asyncio.sleep(1.2)
    assert [endpoint for endpoint, _ in calls] == ["https://push.example/A"]
    calls.clear()
    for device in ("phone000", "desktop0", None):
        await post(client, "push/rest-timer", {"seconds": 1, "deviceId": device})
    await post(client, "push/rest-timer/cancel")
    await asyncio.sleep(1.2)
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["session_version=1", "disabled=true"])
async def test_pending_timer_cannot_send_after_revocation(alerts, change):
    observer, client, calls = alerts
    await seed(observer, {})
    await post(client, "push/rest-timer", {"seconds": 1})
    await observer.execute("UPDATE identity.users SET " + change + " WHERE id='A'")
    await asyncio.sleep(1.2)
    assert calls == []


@pytest.mark.asyncio
async def test_restart_drops_presence_and_pending_timer_without_late_send(
    identities, monkeypatch
):
    observer, environment = identities
    await seed(observer, {})
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append(payload)
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            await post(client, "activity", {"active": True})
            await post(client, "push/rest-timer", {"seconds": 1})
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            response = await client.get(
                "/api/v1/admin/users", headers={"Authorization": f"Bearer {B}"}
            )
            assert all(user["live"] is None for user in response.json()["users"])
            await asyncio.sleep(1.2)
    assert calls == []
    assert (
        await observer.fetchval("SELECT count(*) FROM notifications.delivery_state")
        == 0
    )


@pytest.mark.asyncio
async def test_hidden_presence_suppresses_nudge_until_grace_expires(
    alerts, monkeypatch
):
    observer, client, calls = alerts
    from test_notification_delivery import STATE

    from opengym_platform.notifications import activity

    instant = datetime.fromisoformat("2026-11-01T20:30:00+00:00")
    clock = [int(instant.timestamp() * 1000)]
    monkeypatch.setattr(activity, "now_ms", lambda: clock[0])
    await seed(
        observer,
        {
            **STATE,
            "reminder": {"on": True, "nudge": True, "time": "08:00", "tz": "UTC"},
        },
    )
    await post(client, "activity", {"active": True})
    await post(client, "activity", {"active": False, "reason": "hidden"})
    notifications = client._transport.app.state.notifications
    await notifications.tick(instant)
    assert calls == []
    clock[0] += 45000
    await notifications.tick(instant)
    assert [payload["tag"] for _, payload in calls] == ["nudge"]
