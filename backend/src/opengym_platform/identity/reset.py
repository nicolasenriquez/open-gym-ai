"""Code possession authorizes reset; crypto runs outside the database lease."""

import hashlib
import re
import time

from opengym_platform.identity.passwords import identifier_text, make_hash, name_key
from opengym_platform.identity.registration import ERRORS, password_problem
from opengym_platform.identity.sessions import sign


async def redeem(database, passwords, throttle, address, body, secret, session_days):
    raw = next(
        (body[k] for k in ("identifier", "name", "email") if body.get(k) is not None),
        "",
    )
    key = name_key(
        identifier_text(raw)
        .encode("utf-16-le", "surrogatepass")[:600]
        .decode("utf-16-le", "surrogatepass")
    )
    code = (
        identifier_text(body.get("code"))
        .encode("utf-16-le", "surrogatepass")[:128]
        .decode("utf-16-le", "surrogatepass")
    )
    if not key or not code:
        return 400, {"error": "name and code required", "code": "missing"}, None
    digest = hashlib.sha256(
        ("opengym-reset:" + re.sub("[^A-Z0-9]", "", code.upper())).encode()
    ).digest()
    rows = await database.fetch("SELECT * FROM identity.lookup_reset($1)", digest)
    observed = next(
        (r for r in rows if key in (name_key(r["display_name"]), r["email"])), None
    )
    invalid = (
        400,
        {"error": "that reset code is wrong or has expired", "code": "reset-invalid"},
        None,
    )
    if observed is None:
        throttle.addresses.attempt(address)
        return invalid
    if observed["disabled"]:
        return (
            403,
            {"error": "this account has been disabled", "code": "disabled"},
            None,
        )
    problem = password_problem(body.get("next"), observed["display_name"])
    if problem:
        return 400, {"error": ERRORS[problem], "code": problem}, None
    stored = await passwords.run(make_hash, body["next"])
    async with database.transaction() as handle:
        for setting, value in (
            ("identifier", key),
            ("alias", name_key(observed["display_name"])),
            ("name", observed["display_name"]),
            ("sv", str(observed["session_version"])),
        ):
            await handle.execute(
                "SELECT set_config($1,$2,true)", "app.reset_" + setting, value
            )
        rows = await handle.fetch(
            "SELECT * FROM identity.finish_reset($1,$2,$3)",
            observed["owner_id"],
            digest,
            stored,
        )
        if not rows:
            return invalid
        actor = rows[0]
        if actor["result"] == "disabled":
            return (
                403,
                {"error": "this account has been disabled", "code": "disabled"},
                None,
            )
        if actor["result"] == "name-taken":
            return 409, {"error": ERRORS["name-taken"], "code": "name-taken"}, None
        token = sign(
            f"{actor['id']}:{int(time.time() * 1000 + session_days * 86400000)}:{actor['session_version']}",
            secret,
        )
    throttle.accounts.entries.pop("acct:" + actor["id"], None)
    return (
        200,
        {
            "user": {
                "id": actor["id"],
                "name": actor["display_name"],
                "admin": actor["is_admin"],
            }
        },
        token,
    )
