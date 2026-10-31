"""One-worker reminders: claim before external effects, without exactly-once delivery."""

import asyncio
import logging
from datetime import UTC, datetime

from opengym_platform.core.database import DatabaseError
from opengym_platform.notifications.endpoints import endpoint_error
from opengym_platform.notifications.planner import message, planned
from opengym_platform.training.service import notification_document


class Notifications:
    def __init__(self, database, send):
        self.database = database
        self.send = send
        # Presence remains process-local; activity supplies updates in slice 7.3.
        self.active = set()
        self.lock = asyncio.Lock()
        self.workers = asyncio.Semaphore(4)

    async def tick(self, now=None):
        async with self.lock:
            now = now or datetime.now(UTC)
            candidates = await self.database.fetch(
                "SELECT * FROM notifications.delivery_candidates($1)", now
            )
            for row in candidates:
                try:
                    await self.deliver(row["owner_id"], now)
                except (DatabaseError, ValueError, TypeError, OverflowError, KeyError):
                    logging.getLogger(__name__).warning("PLATFORM_NOTIFICATION_SKIPPED")

    async def deliver(self, owner, now):
        async with self.database.transaction() as handle:
            if not await handle.fetch(
                "SELECT * FROM notifications.lock_delivery_owner($1)", owner
            ):
                return
            state = await notification_document(handle)
            payloads = []
            for kind, rid, day in planned(state, now, owner in self.active):
                column = "last_nudge_date" if kind == "nudge" else "last_reminder_date"
                rows = await handle.fetch(
                    f"""INSERT INTO notifications.delivery_state(owner_id,{column}) VALUES($1,$2)
                    ON CONFLICT(owner_id) DO UPDATE SET {column}=excluded.{column}
                    WHERE notifications.delivery_state.{column} IS DISTINCT FROM excluded.{column}
                    RETURNING owner_id""",
                    owner,
                    day,
                )
                if rows:
                    payloads.append(message(state, kind, rid, day))
            subscriptions = (
                await handle.fetch("SELECT * FROM notifications.subscriptions")
                if payloads
                else []
            )
        for payload in payloads:
            results = await asyncio.gather(
                *(self.send_one(owner, sub, payload) for sub in subscriptions),
                return_exceptions=True,
            )
            if any(isinstance(result, Exception) for result in results):
                logging.getLogger(__name__).warning("PLATFORM_PUSH_BOOKKEEPING_FAILED")

    async def send_one(self, owner, subscription, payload):
        async with self.workers:
            async with self.database.transaction() as handle:
                if not await handle.fetch(
                    "SELECT * FROM notifications.lock_delivery_owner($1)", owner
                ):
                    return
                current = await handle.fetch(
                    "SELECT * FROM notifications.subscriptions WHERE endpoint=$1 AND p256dh=$2 AND auth=$3",
                    subscription["endpoint"],
                    subscription["p256dh"],
                    subscription["auth"],
                )
                if not current:
                    return
            status = None
            invalid = endpoint_error(subscription["endpoint"])
            try:
                if not invalid:
                    async with asyncio.timeout(8):
                        status = await self.send(subscription, payload)
            except Exception:  # noqa: BLE001 -- external transport failure must not stop other recipients
                logging.getLogger(__name__).warning("PLATFORM_PUSH_FAILED")
            if invalid or status in (403, 404, 410):
                async with self.database.transaction() as handle:
                    if await handle.fetch(
                        "SELECT * FROM notifications.lock_delivery_owner($1)", owner
                    ):
                        await handle.execute(
                            "DELETE FROM notifications.subscriptions WHERE endpoint=$1 AND p256dh=$2 AND auth=$3",
                            subscription["endpoint"],
                            subscription["p256dh"],
                            subscription["auth"],
                        )
            elif status is not None and not 200 <= status < 300:
                logging.getLogger(__name__).warning("PLATFORM_PUSH_REJECTED")

    async def maintain(self):
        while True:
            await asyncio.sleep(10)
            try:
                await self.tick()
            except DatabaseError:
                logging.getLogger(__name__).warning("PLATFORM_NOTIFICATION_UNAVAILABLE")
