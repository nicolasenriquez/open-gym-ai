"""Administration coordinates Identity and Training on the same transaction."""

import hashlib
import json
import secrets
import time
from datetime import UTC, datetime
from uuid import uuid4

from opengym_platform.identity.links import ALPHABET
from opengym_platform.identity.passwords import identifier_text, name_key
from opengym_platform.identity.sessions import authorize
from opengym_platform.training.service import admin_projection


def checked(value):
    if value is None:
        return 401, {"error": "not signed in"}
    if value == {}:
        return 403, {"error": "forbidden"}
    if isinstance(value, dict) and "error" in value:
        return (
            404 if value["error"] in {"no such user", "no such code"} else 400
        ), value
    return 200, value


async def handle(database, session, operation, body, config, coach, event):
    async with database.transaction() as tx:
        args = (session.owner, session.version, session.expires_at)
        if operation in {"invites", "new", "revoke"}:
            if operation == "invites":
                query = "SELECT administration.list_invitations($1,$2,$3) AS view"
                params = args
            elif operation == "new":
                note = identifier_text(body.get("note"))
                note = note.encode("utf-16-le", "surrogatepass")[:120].decode(
                    "utf-16-le", "surrogatepass"
                )
                if "\x00" in note or any(
                    0xD800 <= ord(char) <= 0xDFFF for char in note
                ):
                    return 400, {"error": "invalid json"}
                query = (
                    "SELECT administration.create_invitation($1,$2,$3,$4,$5,$6) AS view"
                )
                params = (*args, secrets.token_hex(8).upper(), note, datetime.now(UTC))
            else:
                code = identifier_text(body.get("code")).upper()
                if "\x00" in code or any(
                    0xD800 <= ord(char) <= 0xDFFF for char in code
                ):
                    code = ""
                query = "SELECT administration.revoke_invitation($1,$2,$3,$4) AS view"
                params = (*args, code)
            while True:
                rows = await tx.fetch(query, *params)
                status, result = checked(
                    json.loads(rows[0]["view"]) if rows[0]["view"] else None
                )
                if status != 200:
                    return status, result
                if operation != "new" or not result.get("collision"):
                    break
                params = (*args, secrets.token_hex(8).upper(), note, datetime.now(UTC))
            if operation == "invites":
                result = {"invites": result, "invite_only": config["invite_only"]}
        elif operation == "users":
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
            if operation == "delete":
                event["message"] = result["name"]
                if target == session.owner:
                    return 400, {"error": "you cannot delete your own account"}
                if not await coach.disconnect_owner(tx, session, target):
                    raise PermissionError
                rows = await tx.fetch(
                    "SELECT administration.delete_user($1,$2,$3,$4,$5) AS view",
                    *args,
                    target,
                    uuid4(),
                )
                status, result = checked(
                    json.loads(rows[0]["view"]) if rows[0]["view"] else None
                )
                if status != 200:
                    # Disconnection is a participant, never committed on a rejected deletion.
                    raise PermissionError
            if operation == "password-reset":
                for key, value in (
                    ("name", result["name"]),
                    ("alias", name_key(result["name"])),
                ):
                    await tx.execute(
                        "SELECT set_config($1,$2,true)", "app.admin_reset_" + key, value
                    )
                raw = "".join(
                    ALPHABET[b % len(ALPHABET)] for b in secrets.token_bytes(12)
                )
                expiry_ms = int(time.time() * 1000) + 86400000
                rows = await tx.fetch(
                    "SELECT administration.issue_reset($1,$2,$3,$4,$5,$6) AS view",
                    *args,
                    target,
                    hashlib.sha256(("opengym-reset:" + raw).encode()).digest(),
                    datetime.fromtimestamp(expiry_ms / 1000, UTC),
                )
                status, result = checked(
                    json.loads(rows[0]["view"]) if rows[0]["view"] else None
                )
                if result.get("code") == "name-taken":
                    return 409, result
                if status != 200:
                    return status, result
                result["code"] = "-".join(raw[i : i + 4] for i in (0, 4, 8))
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
        events = {
            "new": "admin.invite.create",
            "revoke": "admin.invite.revoke",
            "password-reset": "admin.password.reset",
            "delete": "admin.user.delete",
            "disable": "admin.user.disable"
            if result.get("disabled")
            else "admin.user.enable",
        }
        if operation in events:
            event["event"] = events[operation]
            if operation in {"disable", "password-reset"}:
                event["target"] = target
            # Invitation/reset codes, notes and credential material never enter audit.
        return 200, result
