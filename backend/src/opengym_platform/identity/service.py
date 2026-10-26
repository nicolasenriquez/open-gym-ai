"""Identity operations own their transaction; collaborators use its same handle."""

import time

from opengym_platform.identity.passwords import BusyError, identifier_text, name_key
from opengym_platform.identity.sessions import authorize, sign


async def password_login(
    database, passwords, throttle, address, body, secret, session_days
):
    raw = next(
        (body[k] for k in ("identifier", "name", "email") if body.get(k) is not None),
        "",
    )
    raw = identifier_text(raw)
    # Node slices UTF-16 code units before applying NFKC.
    raw = (
        str(raw)
        .encode("utf-16-le", "surrogatepass")[:600]
        .decode("utf-16-le", "surrogatepass")
    )
    key = name_key(raw)
    password = body.get("password")
    if not key or not isinstance(password, str) or not password:
        return 400, {"error": "name and password required", "code": "missing"}, None
    only_email = "identifier" not in body and "name" not in body
    representable = "\x00" not in key and not any(
        0xD800 <= ord(char) <= 0xDFFF for char in key
    )
    rows = (
        await database.fetch("SELECT * FROM identity.lookup_password($1)", key)
        if representable
        else []
    )
    observed = rows[0] if rows else None
    if observed and only_email and not ("@" in key and observed["email_claim"]):
        observed = None
    stored = observed["scrypt_hash"] if observed else None
    account_key = "acct:" + observed["owner_id"] if observed else "id:" + key
    undo_account, undo_address = throttle.begin(account_key, address)
    failed = False
    wrong = (401, {"error": "wrong name or password", "code": "bad-credentials"}, None)
    try:
        if not await passwords.verify(password, stored):
            failed = True
            return wrong
        try:
            replacement = await passwords.rehash(password, stored)
        except BusyError:
            replacement = None
        async with database.transaction() as handle:
            rows = await handle.fetch(
                "SELECT * FROM identity.finish_password_login($1,$2,$3)",
                observed["owner_id"],
                stored,
                observed["session_version"],
            )
            if not rows:
                return wrong
            actor = rows[0]
            aliases = await handle.fetch(
                "SELECT * FROM identity.lookup_password($1)", key
            )
            if (
                not aliases
                or aliases[0]["owner_id"] != actor["id"]
                or (only_email and not aliases[0]["email_claim"])
            ):
                return wrong
            if actor["disabled"]:
                return (
                    403,
                    {"error": "this account has been disabled", "code": "disabled"},
                    None,
                )
            if replacement:
                await handle.execute(
                    "SELECT set_config('app.owner_id', $1, true)", actor["id"]
                )
                await handle.execute(
                    "UPDATE identity.password_credentials SET scrypt_hash=$1 WHERE owner_id=$2",
                    replacement,
                    actor["id"],
                )
            expiry = int(time.time() * 1000 + session_days * 86400000)
            token = sign(f"{actor['id']}:{expiry}:{actor['session_version']}", secret)
            result = {
                "user": {
                    "id": actor["id"],
                    "name": actor["display_name"],
                    "admin": actor["is_admin"],
                }
            }
        throttle.accounts.entries.pop(account_key, None)
        return 200, result, token
    finally:
        if not failed:
            undo_account()
            undo_address()


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
