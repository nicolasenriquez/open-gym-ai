"""Ephemeral mobile pairing and one-use passkey device links."""

import hashlib
import json
import re
import secrets
import time
from datetime import UTC, datetime
from functools import partial

from webauthn import verify_registration_response
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException

from opengym_platform.identity.account import Refused
from opengym_platform.identity.passwords import SPACE, identifier_text
from opengym_platform.identity.sessions import Session

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIR_INVALID = (400, {"error": "invalid or expired code", "code": "pair-invalid"}, None)
LINK_INVALID = (
    400,
    {"error": "that code is wrong, used or expired", "code": "link-invalid"},
    None,
)


class Links:
    def __init__(self, accounts):
        self.accounts = accounts
        self.passkeys = accounts.passkeys
        self.pairings = {}

    async def pair_create(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.accounts.locked(database, session):
                expiry = datetime.fromtimestamp(time.time() + 300, UTC)
            self.pairings = {
                code: entry
                for code, entry in self.pairings.items()
                if entry.owner != session.owner and entry.expires_at > datetime.now(UTC)
            }
            while True:
                code = "".join(ALPHABET[b % 32] for b in secrets.token_bytes(8))
                if code not in self.pairings:
                    break
            self.pairings[code] = Session(session.owner, session.version, expiry, True)
            return 200, {"code": code}, None
        except Refused as error:
            return error.response()

    async def pair_redeem(
        self, database, passwords, throttle, address, body, secret, days
    ):
        code = identifier_text(body.get("code")).strip(SPACE).upper()
        session = self.pairings.pop(code, None)
        if session is None:
            return PAIR_INVALID
        try:
            async with self.accounts.locked(database, session) as handle:
                actors = await handle.fetch(
                    "SELECT id,display_name,is_admin FROM identity.users WHERE id=$1",
                    session.owner,
                )
                if not actors:
                    return PAIR_INVALID
                actor = actors[0]
                _, result, token = self.passkeys.session(
                    {
                        "id": actor["id"],
                        "name": actor["display_name"],
                        "admin": actor["is_admin"],
                        "session_version": session.version,
                    },
                    secret,
                    days,
                )
            return 200, {**result, "token": token}, None
        except Refused:
            return PAIR_INVALID

    @staticmethod
    def digest(code):
        clean = re.sub("[^A-Z0-9]", "", identifier_text(code).upper())
        return (
            hashlib.sha256(("opengym-link:" + clean).encode()).digest()
            if len(clean) == 12
            else None
        )

    async def create(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.accounts.locked(database, session) as handle:
                observed, _ = await self.accounts.passkey_state(handle)
                self.accounts.passkey_limit(observed)
            proof = await self.accounts.prove(
                passwords, throttle, address, body, observed
            )
            async with self.accounts.locked(database, session) as handle:
                current, _ = await self.accounts.passkey_state(handle)
                await self.accounts.confirm(
                    handle, proof, observed, current, session, throttle
                )
                self.accounts.passkey_limit(current)
                raw = "".join(ALPHABET[b % 32] for b in secrets.token_bytes(12))
                code = "-".join(raw[i : i + 4] for i in range(0, 12, 4))
                now = int(time.time() * 1000)
                expiry = now + 600000
                await handle.execute(
                    """INSERT INTO identity.device_links(code_digest,owner_id,created_at,expires_at)
                    VALUES ($1,$2,$3,$4) ON CONFLICT(owner_id) DO UPDATE SET
                    code_digest=EXCLUDED.code_digest,created_at=EXCLUDED.created_at,expires_at=EXCLUDED.expires_at""",
                    self.digest(code),
                    session.owner,
                    datetime.fromtimestamp(now / 1000, UTC),
                    datetime.fromtimestamp(expiry / 1000, UTC),
                )
            return 200, {"code": code, "expires": expiry}, None
        except Refused as error:
            return error.response()

    async def lookup(self, database, body, throttle, address):
        digest = self.digest(body.get("code"))
        rows = (
            await database.fetch(
                "SELECT * FROM identity.lookup_device_link($1)", digest
            )
            if digest
            else []
        )
        if not rows:
            throttle.addresses.attempt("link|" + address)
            raise Refused(400, LINK_INVALID[1]["error"], "link-invalid")
        return digest, rows[0]

    async def options(self, database, passwords, throttle, address, body, secret, days):
        try:
            digest, observed = await self.lookup(database, body, throttle, address)
            credentials = json.loads(observed["passkeys"])
            if len(credentials) >= 20:
                raise Refused(
                    409, "a profile can have at most 20 passkeys", "passkey-limit"
                )
            options = self.passkeys.registration_options(
                observed["owner_id"], observed["display_name"], credentials
            )
            status, result, token = self.passkeys.remember(
                "link",
                options,
                uid=observed["owner_id"],
                digest=digest,
                sv=observed["session_version"],
            )
            return (
                status,
                {
                    **result,
                    "id": observed["owner_id"],
                    "name": observed["display_name"],
                },
                token,
            )
        except Refused as error:
            return error.response()

    async def verify(self, database, passwords, throttle, address, body, secret, days):
        ceremony = self.passkeys.take(body, "link")
        try:
            digest, observed = await self.lookup(database, body, throttle, address)
        except Refused as error:
            return error.response()
        if (
            not ceremony
            or ceremony["digest"] != digest
            or ceremony["uid"] != observed["owner_id"]
        ):
            return (
                400,
                {"error": "challenge expired, try again", "code": "challenge-expired"},
                None,
            )
        if not isinstance(body.get("credential"), dict):
            return 400, {"error": "verification failed"}, None
        try:
            credential = await passwords.run(
                partial(
                    verify_registration_response,
                    credential=body["credential"],
                    expected_challenge=ceremony["challenge"],
                    expected_origin=self.passkeys.origin,
                    expected_rp_id=self.passkeys.rp_id,
                    require_user_verification=False,
                )
            )
        except (
            WebAuthnException,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
        ) as error:
            return 400, self.passkeys.verify_error(error), None
        async with database.transaction() as handle:
            await handle.execute(
                "SELECT set_config('app.link_sv',$1,true)", str(ceremony["sv"])
            )
            rows = await handle.fetch(
                "SELECT * FROM identity.finish_device_link($1,$2,$3,$4,$5,$6,$7)",
                ceremony["uid"],
                digest,
                bytes_to_base64url(credential.credential_id),
                credential.credential_public_key,
                credential.sign_count,
                self.passkeys.transports(
                    body["credential"].get("response", {}).get("transports")
                ),
                self.passkeys.label(body.get("name")),
            )
            if not rows:
                return LINK_INVALID
            actor = rows[0]
            if actor["result"] == "passkey-limit":
                return (
                    409,
                    {
                        "error": "a profile can have at most 20 passkeys",
                        "code": "passkey-limit",
                    },
                    None,
                )
            if actor["result"] == "credential-exists":
                return (
                    409,
                    {
                        "error": "credential already registered",
                        "code": "credential-exists",
                    },
                    None,
                )
            result = self.passkeys.session(actor, secret, days)
        return result
