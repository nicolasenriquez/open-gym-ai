"""Identity operations own their transaction; collaborators use its same handle."""

import logging
import os
import secrets
import time
from datetime import UTC, datetime

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.passwords import (
    SPACE,
    BusyError,
    identifier_text,
    make_hash,
    name_key,
)
from opengym_platform.identity.registration import (
    ERRORS,
    normalize_email,
    password_problem,
)
from opengym_platform.identity.sessions import authorize, sign
from opengym_platform.identity.throttle import LockedError


async def note_pull(database, session):
    """Best-effort admin sync timestamp; never changes a successful Training read."""
    try:
        async with database.transaction() as handle:
            if await authorize(handle, session):
                await handle.execute(
                    """UPDATE identity.users SET last_pull_at=clock_timestamp()
                    WHERE id=$1 AND (last_pull_at IS NULL OR last_pull_at<=clock_timestamp()-interval '10 minutes')""",
                    session.owner,
                )
    except DatabaseError:
        logging.getLogger(__name__).warning("TRAINING_PULL_NOTE_FAILED")


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


async def password_register(
    database, passwords, throttle, address, body, secret, session_days
):
    name = identifier_text(body.get("name")).strip(SPACE)
    name = name.encode("utf-16-le", "surrogatepass")[:80].decode(
        "utf-16-le", "surrogatepass"
    )
    if not name:
        return 400, {"error": "name required", "code": "missing"}, None
    code = identifier_text(body.get("code")).strip(SPACE).upper()
    owner = secrets.token_urlsafe(12)
    key = name_key(name)
    settings = (
        (
            "invite_only",
            os.environ.get("INVITE_ONLY", "").lower() in {"1", "true", "yes", "on"},
        ),
        (
            "first_user_admin",
            os.environ.get("FIRST_USER_ADMIN", "").lower()
            in {"1", "true", "yes", "on"},
        ),
        (
            "admin_uids",
            ",".join(
                s.strip()
                for s in os.environ.get("ADMIN_UIDS", "").split(",")
                if s.strip()
            ),
        ),
    )

    async def claim(email, stored):
        async with database.transaction() as handle:
            for setting, value in settings:
                await handle.execute(
                    "SELECT set_config($1,$2,true)",
                    "app." + setting,
                    str(value).lower() if isinstance(value, bool) else value,
                )
            rows = await handle.fetch(
                "SELECT * FROM identity.register_password($1,$2,$3,$4,$5,$6,$7)",
                owner,
                name,
                key,
                email,
                stored,
                code,
                datetime.now(UTC),
            )
        return rows[0]

    early = await claim(None, None)
    if early["result"] == "invite":
        throttle.addresses.attempt("signup|" + address)
        return 403, {"error": "a valid invite code is required", "code": "invite"}, None
    problem = password_problem(body.get("password"), name)
    if problem:
        return 400, {"error": ERRORS[problem], "code": problem}, None
    if early["result"] == "name-taken":
        return 409, {"error": ERRORS["name-taken"], "code": "name-taken"}, None
    has_email = isinstance(body.get("email"), str) and bool(body["email"].strip(SPACE))
    email = normalize_email(body["email"]) if has_email else None
    if has_email and not email:
        return 400, {"error": ERRORS["email-invalid"], "code": "email-invalid"}, None
    if email:
        wait = throttle.addresses.wait("email|" + address)
        if wait:
            raise LockedError(wait)
    stored = await passwords.run(make_hash, body["password"])
    actor = await claim(email, stored)
    outcome = actor["result"]
    if outcome == "invite":
        return (
            403,
            {
                "error": "invite code is no longer valid, ask for a new one",
                "code": "invite",
            },
            None,
        )
    if outcome in {"name-taken", "email-taken"}:
        if outcome == "email-taken":
            throttle.addresses.attempt("email|" + address)
        return 409, {"error": ERRORS[outcome], "code": outcome}, None
    token = sign(
        f"{owner}:{int(time.time() * 1000 + session_days * 86400000)}:0", secret
    )
    return 200, {"user": {"id": owner, "name": name, "admin": actor["admin"]}}, token


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
