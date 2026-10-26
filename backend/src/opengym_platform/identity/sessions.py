"""Compatible signed sessions; selection happens once before database work."""

import base64
import hashlib
import hmac
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Session:
    owner: str
    version: int
    expires_at: datetime
    bearer: bool


def select_token(cookie, authorization, secure):
    for name in ["__Host-gymsid", "gymsid"] if secure else ["gymsid"]:
        values = []
        for part in cookie.split(";"):
            key, separator, value = part.partition("=")
            if separator and key.strip() == name:
                values.append(value.strip())
        if values:
            if len(set(values)) == 1 and values[0]:
                return values[0], False
            break
    return (
        (authorization[7:].strip(), True)
        if authorization.startswith("Bearer ")
        else ("", True)
    )


def sign(payload, secret):
    mac = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return payload + "." + base64.urlsafe_b64encode(mac).decode().rstrip("=")


def verify(cookie, authorization, secure, secret):
    token, bearer = select_token(cookie, authorization, secure)
    payload, separator, mac = token.rpartition(".")
    if not separator or not hmac.compare_digest(
        mac.encode(), sign(payload, secret).rpartition(".")[2].encode()
    ):
        return None
    fields = payload.split(":")
    if len(fields) < 2 or not fields[0]:
        return None
    try:
        expiry = float(fields[1].strip() or "0")
        version = float(fields[2].strip() or "0") if len(fields) > 2 else 0.0
        if not math.isfinite(expiry) or expiry <= time.time() * 1000:
            return None
        if (
            not math.isfinite(version)
            or not version.is_integer()
            or not 0 <= version <= 9223372036854775807
        ):
            return None
        return Session(
            fields[0], int(version), datetime.fromtimestamp(expiry / 1000, UTC), bearer
        )
    except ValueError, OverflowError, OSError:
        return None


async def authorize(handle, session):
    actors = await handle.fetch(
        "SELECT id, is_admin, session_version FROM identity.lock_actor($1, $2, $3)",
        session.owner,
        session.version,
        session.expires_at,
    )
    if not actors:
        return False
    await handle.execute("SELECT set_config('app.owner_id', $1, true)", actors[0]["id"])
    return True
