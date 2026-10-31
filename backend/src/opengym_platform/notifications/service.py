"""Subscription operations own authorization, transaction and endpoint transfer."""

import re
from datetime import UTC, datetime

from opengym_platform.identity.sessions import authorize
from opengym_platform.notifications.endpoints import endpoint_error


async def preflight(database, session):
    async with database.transaction() as handle:
        return await authorize(handle, session)


async def handle(database, session, operation, body):
    def response(body, status=200):
        return status, body

    if operation == "subscribe":
        sub = body.get("subscription")
        if not isinstance(sub, dict):
            return response({"error": "invalid subscription"}, 400)
        keys = sub.get("keys")
        if not isinstance(keys, dict) or not all(
            isinstance(value, str)
            and value
            and "\x00" not in value
            and not any(0xD800 <= ord(char) <= 0xDFFF for char in value)
            for value in (
                sub.get("endpoint"),
                keys.get("p256dh"),
                keys.get("auth"),
            )
        ):
            return response({"error": "invalid subscription"}, 400)
        error = endpoint_error(sub["endpoint"])
        if error:
            return response({"error": error}, 400)
        device = body.get("deviceId")
        if not isinstance(device, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{8,64}", device
        ):
            device = None
        async with database.transaction() as handle:
            rows = await handle.fetch(
                "SELECT notifications.upsert_subscription($1,$2,$3,$4,$5,$6,$7,$8) AS accepted",
                session.owner,
                session.version,
                session.expires_at,
                sub["endpoint"],
                keys["p256dh"],
                keys["auth"],
                device,
                datetime.now(UTC),
            )
            if not rows[0]["accepted"]:
                return response({"error": "not signed in"}, 401)
        return response({"ok": True})
    async with database.transaction() as handle:
        if not await authorize(handle, session):
            return response({"error": "not signed in"}, 401)
        if operation == "status":
            endpoint = body.get("endpoint", "")
            rows = (
                await handle.fetch(
                    "SELECT device_id FROM notifications.subscriptions WHERE endpoint=$1",
                    endpoint,
                )
                if "\x00" not in endpoint
                else []
            )
            return response(
                {"subscribed": True, "deviceId": rows[0]["device_id"]}
                if rows
                else {"subscribed": False}
            )
        removed = body.get("endpoint")
        if isinstance(removed, str) and "\x00" not in removed:
            await handle.execute(
                "DELETE FROM notifications.subscriptions WHERE endpoint=$1",
                removed,
            )
        return response({"ok": True})
