"""Process-local single-use WebAuthn ceremonies; crypto never owns a DB lease."""

import json
import os
import secrets
import time
from datetime import UTC, datetime
from functools import partial
from secrets import token_bytes

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, options_to_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from opengym_platform.identity.passwords import SPACE, identifier_text
from opengym_platform.identity.sessions import sign


class Passkeys:
    def __init__(self):
        self.challenges = {}
        self.rp_id = os.environ.get("RP_ID") or "localhost"
        self.rp_name = os.environ.get("RP_NAME") or "openGym"
        self.origin = os.environ.get("ORIGIN") or "http://localhost:8080"

    def remember(self, kind, options, **data):
        now = time.time()
        self.challenges = {
            key: value for key, value in self.challenges.items() if value["exp"] >= now
        }
        while len(self.challenges) >= 20000:
            del self.challenges[next(iter(self.challenges))]
        cid = secrets.token_urlsafe(16)
        self.challenges[cid] = {
            "kind": kind,
            "challenge": options.challenge,
            "exp": now + 300,
            **data,
        }
        public = json.loads(options_to_json(options))
        if kind == "register":
            public["extensions"] = {"credProps": True}
        return 200, {"cid": cid, "options": public}, None

    def login_options(self):
        options = generate_authentication_options(
            rp_id=self.rp_id, challenge=token_bytes(32)
        )
        return self.remember("login", options)

    async def register_options(
        self, database, passwords, throttle, address, body, secret, days
    ):
        name = identifier_text(body.get("name")).strip(SPACE)
        name = name.encode("utf-16-le", "surrogatepass")[:80].decode(
            "utf-16-le", "surrogatepass"
        )
        if not name:
            return 400, {"error": "name required"}, None
        uid = secrets.token_urlsafe(12)
        code = identifier_text(body.get("code")).strip(SPACE).upper()
        ceremony = {"uid": uid, "name": name, "code": code}
        availability = await self.claim(database, ceremony)
        if availability["result"] == "invite":
            return (
                403,
                {"error": "a valid invite code is required", "code": "invite"},
                None,
            )
        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=uid.encode(),
            user_name=name,
            challenge=token_bytes(32),
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                require_resident_key=True,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        return self.remember("register", options, uid=uid, name=name, code=code)

    async def claim(self, database, ceremony, credential=None, transports=None):
        async with database.transaction() as handle:
            for key in ("INVITE_ONLY", "FIRST_USER_ADMIN", "ADMIN_UIDS"):
                raw = os.environ.get(key, "")
                value = (
                    ",".join(s.strip() for s in raw.split(",") if s.strip())
                    if key == "ADMIN_UIDS"
                    else str(raw.lower() in {"1", "true", "yes", "on"}).lower()
                )
                await handle.execute(
                    "SELECT set_config($1,$2,true)", "app." + key.lower(), value
                )
            rows = await handle.fetch(
                "SELECT * FROM identity.register_passkey($1,$2,$3,$4,$5,$6,$7,$8)",
                ceremony["uid"],
                ceremony["name"],
                ceremony["code"],
                bytes_to_base64url(credential.credential_id) if credential else None,
                credential.credential_public_key if credential else None,
                credential.sign_count if credential else None,
                transports or [],
                datetime.now(UTC),
            )
        return rows[0]

    def take(self, body, kind):
        cid = body.get("cid")
        ceremony = self.challenges.pop(cid, None) if isinstance(cid, str) else None
        if not ceremony or ceremony["kind"] != kind or ceremony["exp"] < time.time():
            return None
        return ceremony

    def verify_error(self, error):
        message = str(error).lower()
        if "origin" in message or "rp id" in message:
            return {
                "error": f"verification failed: RP_ID={self.rp_id} and ORIGIN={self.origin} must match the address you opened. See docs/SELF_HOSTING.md."
            }
        return {"error": "verification failed"}

    @staticmethod
    def session(actor, secret, days):
        token = sign(
            f"{actor['id']}:{int(time.time() * 1000 + days * 86400000)}:{actor.get('session_version', 0)}",
            secret,
        )
        return (
            200,
            {
                "user": {
                    "id": actor["id"],
                    "name": actor["name"],
                    "admin": actor["admin"],
                }
            },
            token,
        )

    async def register_verify(
        self, database, passwords, throttle, address, body, secret, days
    ):
        ceremony = self.take(body, "register")
        if not ceremony:
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
                    credential=body.get("credential"),
                    expected_challenge=ceremony["challenge"],
                    expected_origin=self.origin,
                    expected_rp_id=self.rp_id,
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
            return 400, self.verify_error(error), None
        actor = await self.claim(
            database,
            ceremony,
            credential,
            body["credential"].get("response", {}).get("transports"),
        )
        if actor["result"] == "credential-exists":
            return 409, {"error": "credential already registered"}, None
        if actor["result"] == "invite":
            return (
                403,
                {
                    "error": "invite code is no longer valid, ask for a new one",
                    "code": "invite",
                },
                None,
            )
        return self.session(actor, secret, days)

    async def login_verify(
        self, database, passwords, throttle, address, body, secret, days
    ):
        ceremony = self.take(body, "login")
        if not ceremony:
            return (
                400,
                {"error": "challenge expired, try again", "code": "challenge-expired"},
                None,
            )
        raw = body.get("credential")
        credential_id = raw.get("id") if isinstance(raw, dict) else None
        rows = (
            await database.fetch(
                "SELECT * FROM identity.lookup_passkey($1)", credential_id
            )
            if isinstance(credential_id, str)
            else []
        )
        if not rows:
            return (
                404,
                {
                    "error": "unknown passkey, create a profile first",
                    "code": "unknown-credential",
                },
                None,
            )
        observed = rows[0]
        try:
            verified = await passwords.run(
                partial(
                    verify_authentication_response,
                    credential=raw,
                    expected_challenge=ceremony["challenge"],
                    expected_origin=self.origin,
                    expected_rp_id=self.rp_id,
                    credential_public_key=bytes(observed["public_key"]),
                    credential_current_sign_count=observed["counter"],
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
            return 400, self.verify_error(error), None
        try:
            async with database.transaction() as handle:
                rows = await handle.fetch(
                    "SELECT * FROM identity.finish_passkey_login($1,$2,$3,$4,$5)",
                    credential_id,
                    observed["public_key"],
                    observed["counter"],
                    verified.new_sign_count,
                    observed["session_version"],
                )
                if rows and rows[0]["id"] != observed["owner_id"]:
                    # Reject a rebound credential and roll back its counter update too.
                    raise WebAuthnException("credential owner changed")
        except WebAuthnException:
            return 400, {"error": "verification failed"}, None
        if not rows:
            return 400, {"error": "verification failed"}, None
        actor = rows[0]
        if actor["disabled"]:
            return (
                403,
                {"error": "this account has been disabled", "code": "disabled"},
                None,
            )
        return self.session(
            {
                "id": actor["id"],
                "name": actor["display_name"],
                "admin": actor["is_admin"],
                "session_version": actor["session_version"],
            },
            secret,
            days,
        )
