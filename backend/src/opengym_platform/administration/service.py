"""Administration coordinates Identity and Training on the same transaction."""

import json
import time

from opengym_platform.identity.sessions import authorize
from opengym_platform.training.service import admin_projection


def checked(value):
    if value is None:
        return 401, {"error": "not signed in"}
    if value == {}:
        return 403, {"error": "forbidden"}
    if isinstance(value, dict) and "error" in value:
        return (400 if value["error"] == "cannot disable an admin" else 404), value
    return 200, value


async def handle(database, session, operation, body, config):
    async with database.transaction() as tx:
        args = (session.owner, session.version, session.expires_at)
        if operation == "users":
            users = []
            after = None
            while True:
                rows = await tx.fetch(
                    "SELECT administration.list_users($1,$2,$3,500,$4) AS view",
                    *args,
                    after,
                )
                status, page = checked(
                    json.loads(rows[0]["view"]) if rows[0]["view"] else None
                )
                if status != 200:
                    return status, page
                for user in page:
                    projection = await admin_projection(
                        tx, session, user["id"], detail=False
                    )
                    status, projection = checked(projection)
                    if status != 200:
                        return status, projection
                    if not config.get("password_login"):
                        user.pop("password", None)
                        user.pop("email", None)
                    users.append({**user, **projection, "live": None})
                if len(page) < 500:
                    break
                after = page[-1]["id"]
            result = {
                "users": users,
                "invite_only": config["invite_only"],
                "now": int(time.time() * 1000),
            }
            if config.get("password_login"):
                result["password_login"] = True
        else:
            target = body.get("id")
            if (
                not isinstance(target, str)
                or "\x00" in target
                or any(0xD800 <= ord(char) <= 0xDFFF for char in target)
            ):
                target = None
            if operation == "disable":
                rows = await tx.fetch(
                    "SELECT administration.set_disabled($1,$2,$3,$4,$5) AS view",
                    *args,
                    target,
                    not (
                        body.get("disabled") is None
                        or body.get("disabled") is False
                        or body.get("disabled") == ""
                        or (
                            type(body.get("disabled")) in (int, float)
                            and body["disabled"] == 0
                        )
                    ),
                )
            else:
                rows = await tx.fetch(
                    "SELECT administration.inspect_user($1,$2,$3,$4) AS view",
                    *args,
                    target,
                )
            status, result = checked(
                json.loads(rows[0]["view"]) if rows[0]["view"] else None
            )
            if status != 200:
                return status, result
            if operation == "user":
                status, projection = checked(
                    await admin_projection(tx, session, target, detail=True)
                )
                if status != 200:
                    return status, projection
                if not config.get("password_login"):
                    for key in ("password", "email", "resetUntil"):
                        result.pop(key, None)
                result = {"user": result, **projection}
        # Actor context is never the inspected target; expiry is checked after all waits.
        if not await authorize(tx, session):
            raise PermissionError
        return 200, result
