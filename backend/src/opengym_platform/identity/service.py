"""Identity operations own their transaction; collaborators use its same handle."""

import time

from opengym_platform.identity.sessions import authorize, sign


async def profile(database, session, secret, session_days):
    async with database.transaction() as handle:
        if not await authorize(handle, session):
            return None
        rows = await handle.fetch(
            "SELECT id, display_name, is_admin FROM identity.users"
        )
        user = rows[0]
        result = {
            "user": {
                "id": user["id"],
                "name": user["display_name"],
                "admin": user["is_admin"],
            }
        }
        now = time.time() * 1000
        if (
            session.bearer
            and session.expires_at.timestamp() * 1000 - now
            < session_days * 86400000 / 2
        ):
            expiry = int(now + session_days * 86400000)
            result["token"] = sign(
                f"{session.owner}:{expiry}:{session.version}", secret
            )
    return result
