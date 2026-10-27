"""Own account operations; namespace precedes actor locks, crypto stays outside."""

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import partial

from webauthn import (
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from opengym_platform.identity import passkeys
from opengym_platform.identity.passwords import (
    SPACE,
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


class Refused(Exception):
    def __init__(self, status, error, code=None):
        self.status, self.body = (
            status,
            {"error": error, **({"code": code} if code else {})},
        )

    def response(self):
        return self.status, self.body, None


class Accounts:
    def __init__(self, passkeys, password_enabled=True):
        self.passkeys = passkeys
        self.password_enabled = password_enabled

    @asynccontextmanager
    async def locked(self, database, session):
        async with database.transaction() as handle:
            await handle.execute("SELECT pg_advisory_xact_lock(728323)")
            if not await authorize(handle, session):
                raise Refused(401, "not signed in")
            yield handle

    async def snapshot(self, handle):
        users = await handle.fetch("SELECT id, display_name FROM identity.users")
        credentials = await handle.fetch(
            "SELECT scrypt_hash FROM identity.password_credentials"
        )
        passkeys = await handle.fetch("SELECT * FROM identity.passkeys")
        aliases = await handle.fetch(
            "SELECT alias_key FROM identity.login_aliases WHERE email_claim"
        )
        return {
            **dict(users[0]),
            "stored": credentials[0]["scrypt_hash"] if credentials else None,
            "passkeys": passkeys,
            "email": aliases[0]["alias_key"] if aliases else None,
        }

    async def passkey_state(self, handle):
        observed = await self.snapshot(handle)
        if not self.password_enabled:
            observed["stored"] = None
        return observed, {
            "passkeys": [
                {
                    "id": row["credential_id"],
                    "name": row["label"] or None,
                    "created": self.passkeys.timestamp(row["created_at"]),
                    "lastUsed": self.passkeys.timestamp(row["last_used_at"]),
                    "transports": self.passkeys.transports(row["transports"]),
                }
                for row in observed["passkeys"]
            ],
            "password": bool(observed["stored"]),
            "lastWayIn": len(observed["passkeys"]) + bool(observed["stored"]) <= 1,
        }

    async def list_passkeys(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session) as handle:
                _, state = await self.passkey_state(handle)
            return 200, state, None
        except Refused as error:
            return error.response()

    @staticmethod
    def passkey_limit(observed):
        if len(observed["passkeys"]) >= 20:
            raise Refused(
                409, "a profile can have at most 20 passkeys", "passkey-limit"
            )

    async def add_passkey_options(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session) as handle:
                observed, _ = await self.passkey_state(handle)
                self.passkey_limit(observed)
            proof = await self.prove(passwords, throttle, address, body, observed)
            async with self.locked(database, session) as handle:
                current, _ = await self.passkey_state(handle)
                await self.confirm(handle, proof, observed, current, session, throttle)
                self.passkey_limit(current)
                options = generate_registration_options(
                    rp_id=self.passkeys.rp_id,
                    rp_name=self.passkeys.rp_name,
                    challenge=passkeys.token_bytes(32),
                    user_id=session.owner.encode(),
                    user_name=current["display_name"],
                    authenticator_selection=AuthenticatorSelectionCriteria(
                        resident_key=ResidentKeyRequirement.REQUIRED,
                        require_resident_key=True,
                        user_verification=UserVerificationRequirement.PREFERRED,
                    ),
                    exclude_credentials=[
                        PublicKeyCredentialDescriptor(
                            id=base64url_to_bytes(p["credential_id"]),
                            transports=self.passkeys.transports(p["transports"]),
                        )
                        for p in current["passkeys"]
                    ],
                )
            return self.passkeys.remember(
                "add", options, uid=session.owner, sv=session.version
            )
        except Refused as error:
            return error.response()

    async def add_passkey_verify(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session):
                ceremony = self.passkeys.take(body, "add")
                if not ceremony or ceremony["uid"] != session.owner:
                    raise Refused(
                        400, "challenge expired, try again", "challenge-expired"
                    )
            if not isinstance(body.get("credential"), dict):
                return 400, {"error": "verification failed"}, None
            try:
                credential = await passwords.run(
                    partial(
                        verify_registration_response,
                        credential=body.get("credential"),
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
            async with self.locked(database, session) as handle:
                if session.version != ceremony["sv"]:
                    raise Refused(401, "not signed in")
                # The namespace lock also serializes credential IDs across owners/signups.
                inserted = await handle.fetch(
                    """INSERT INTO identity.passkeys(credential_id,owner_id,public_key,counter,transports,label,created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(credential_id) DO NOTHING RETURNING credential_id""",
                    bytes_to_base64url(credential.credential_id),
                    session.owner,
                    credential.credential_public_key,
                    credential.sign_count,
                    self.passkeys.transports(
                        body["credential"].get("response", {}).get("transports")
                    ),
                    self.passkeys.label(body.get("name")),
                    datetime.now(UTC),
                )
                if not inserted:
                    raise Refused(
                        409, "credential already registered", "credential-exists"
                    )
                observed, state = await self.passkey_state(handle)
                if len(observed["passkeys"]) > 20:
                    raise Refused(
                        409, "a profile can have at most 20 passkeys", "passkey-limit"
                    )
            return 200, {"ok": True, **state}, None
        except Refused as error:
            return error.response()

    async def rename_passkey(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session) as handle:
                rows = await handle.fetch(
                    "UPDATE identity.passkeys SET label=$1 WHERE credential_id=$2 RETURNING credential_id",
                    self.passkeys.label(body.get("name")),
                    identifier_text(body.get("id")),
                )
                if not rows:
                    raise Refused(404, "passkey not found", "not-found")
                _, state = await self.passkey_state(handle)
            return 200, {"ok": True, **state}, None
        except Refused as error:
            return error.response()

    @staticmethod
    def removal_allowed(observed, credential_id):
        if not any(p["credential_id"] == credential_id for p in observed["passkeys"]):
            raise Refused(404, "passkey not found", "not-found")
        if len(observed["passkeys"]) - 1 + bool(observed["stored"]) < 1:
            raise Refused(
                409, "this passkey is the only way into this profile", "last-way-in"
            )

    async def remove_passkey(
        self,
        database,
        passwords,
        throttle,
        address,
        body,
        secret,
        days,
        *,
        session,
        credential_id,
    ):
        try:
            async with self.locked(database, session) as handle:
                observed, _ = await self.passkey_state(handle)
                self.removal_allowed(observed, credential_id)
            proof = await self.prove(passwords, throttle, address, body, observed)
            async with self.locked(database, session) as handle:
                current, _ = await self.passkey_state(handle)
                await self.confirm(handle, proof, observed, current, session, throttle)
                self.removal_allowed(current, credential_id)
                await handle.execute(
                    "DELETE FROM identity.passkeys WHERE credential_id=$1",
                    credential_id,
                )
                await handle.execute("DELETE FROM identity.device_links")
                _, state = await self.passkey_state(handle)
            return 200, {"ok": True, **state}, None
        except Refused as error:
            return error.response()

    async def prove(self, passwords, throttle, address, body, observed):
        raw = body.get("credential")
        if raw or isinstance(raw, (dict, list)):
            ceremony = self.passkeys.take(body, "login")
            credential = next(
                (
                    p
                    for p in observed["passkeys"]
                    if isinstance(raw, dict) and p["credential_id"] == raw.get("id")
                ),
                None,
            )
            if not ceremony or not credential:
                raise Refused(403, "the passkey could not be verified", "passkey")
            try:
                verified = await passwords.run(
                    partial(
                        verify_authentication_response,
                        credential=raw,
                        expected_challenge=ceremony["challenge"],
                        expected_origin=self.passkeys.origin,
                        expected_rp_id=self.passkeys.rp_id,
                        credential_public_key=bytes(credential["public_key"]),
                        credential_current_sign_count=credential["counter"],
                        require_user_verification=False,
                    )
                )
                return credential, verified.new_sign_count
            except WebAuthnException, ValueError, TypeError, KeyError, OverflowError:
                raise Refused(
                    403, "the passkey could not be verified", "passkey"
                ) from None
        if observed["stored"] is None:
            raise Refused(403, "confirm with your passkey first", "passkey-required")
        current = body.get("current")
        if not isinstance(current, str) or not current:
            raise Refused(403, "enter your current password", "current-required")
        key = "acct:" + observed["id"]
        undo_account, undo_address = throttle.begin(key, address)
        failed = False
        try:
            if not await passwords.verify(current, observed["stored"]):
                failed = True
                raise Refused(
                    403, "your current password is not right", "current-wrong"
                )
        finally:
            if not failed:
                undo_account()
                undo_address()

    async def confirm(self, handle, proof, observed, current, session, throttle):
        if proof is None:
            if current["stored"] != observed["stored"]:
                raise Refused(
                    403, "your current password is not right", "current-wrong"
                )
            throttle.accounts.entries.pop("acct:" + session.owner, None)
        else:
            credential, counter = proof
            actors = await handle.fetch(
                "SELECT * FROM identity.finish_passkey_login($1,$2,$3,$4,$5)",
                credential["credential_id"],
                credential["public_key"],
                credential["counter"],
                counter,
                session.version,
            )
            if not actors or actors[0]["id"] != session.owner:
                raise Refused(403, "the passkey could not be verified", "passkey")

    async def claim(self, handle, key, email):
        available = await handle.fetch(
            "SELECT identity.alias_available($1) AS available", key
        )
        if not available[0]["available"]:
            code = "email-taken" if email else "name-taken"
            raise Refused(409, ERRORS[code], code)
        await handle.execute("SELECT identity.release_expired_alias($1)", key)
        await handle.execute(
            """
            INSERT INTO identity.login_aliases(alias_key,owner_id,email_claim,password_name_claim)
            VALUES ($1,nullif(current_setting('app.owner_id',true),''),$2,NOT $2)
            ON CONFLICT(alias_key) DO UPDATE SET
                email_claim = identity.login_aliases.email_claim OR EXCLUDED.email_claim,
                password_name_claim = identity.login_aliases.password_name_claim OR EXCLUDED.password_name_claim,
                reset_name_until = CASE WHEN EXCLUDED.password_name_claim THEN NULL ELSE identity.login_aliases.reset_name_until END
        """,
            key,
            email,
        )

    async def set_password(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session) as handle:
                observed = await self.snapshot(handle)
                problem = password_problem(body.get("next"), observed["display_name"])
                if problem:
                    raise Refused(400, ERRORS[problem], problem)
                key = name_key(observed["display_name"])
                available = await handle.fetch(
                    "SELECT identity.alias_available($1) AS available", key
                )
                if not available[0]["available"]:
                    raise Refused(409, ERRORS["name-taken"], "name-taken")
            proof = await self.prove(passwords, throttle, address, body, observed)
            stored = await passwords.run(make_hash, body["next"])
            async with self.locked(database, session) as handle:
                current = await self.snapshot(handle)
                await self.confirm(handle, proof, observed, current, session, throttle)
                await self.claim(handle, name_key(current["display_name"]), False)
                await handle.execute(
                    """
                    INSERT INTO identity.password_credentials VALUES ($1,$2,$3)
                    ON CONFLICT(owner_id) DO UPDATE SET scrypt_hash=EXCLUDED.scrypt_hash, set_at=EXCLUDED.set_at
                """,
                    session.owner,
                    stored,
                    datetime.now(UTC),
                )
                await handle.execute("DELETE FROM identity.password_resets")
                await handle.execute("DELETE FROM identity.device_links")
                versions = await handle.fetch(
                    "UPDATE identity.users SET session_version=session_version+1 RETURNING session_version"
                )
                token = sign(
                    f"{session.owner}:{int(time.time() * 1000 + days * 86400000)}:{versions[0]['session_version']}",
                    secret,
                )
            throttle.accounts.entries.pop("acct:" + session.owner, None)
            return (
                200,
                {"ok": True, **({"token": token} if session.bearer else {})},
                None if session.bearer else token,
            )
        except Refused as error:
            return error.response()

    async def remove_password(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session) as handle:
                observed = await self.snapshot(handle)
                if observed["stored"] is None:
                    return 200, {"ok": True}, None
                if not observed["passkeys"]:
                    raise Refused(
                        409,
                        "the password is the only way into this profile",
                        "last-way-in",
                    )
            proof = await self.prove(passwords, throttle, address, body, observed)
            async with self.locked(database, session) as handle:
                current = await self.snapshot(handle)
                await self.confirm(handle, proof, observed, current, session, throttle)
                if not current["passkeys"]:
                    raise Refused(
                        409,
                        "the password is the only way into this profile",
                        "last-way-in",
                    )
                await handle.execute("DELETE FROM identity.password_credentials")
                await handle.execute(
                    "DELETE FROM identity.login_aliases WHERE password_name_claim AND NOT email_claim AND reset_name_until IS NULL"
                )
                await handle.execute(
                    "UPDATE identity.login_aliases SET password_name_claim=false WHERE password_name_claim"
                )
            return 200, {"ok": True}, None
        except Refused as error:
            return error.response()

    async def logout_all(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            async with self.locked(database, session) as handle:
                await handle.execute(
                    "UPDATE identity.users SET session_version=session_version+1"
                )
                await handle.execute("DELETE FROM identity.device_links")
            return 200, {"ok": True}, None
        except Refused as error:
            return error.response()

    @staticmethod
    def email_pause(throttle, address, owner):
        wait = throttle.addresses.wait(
            "email|acct:" + owner
        ) or throttle.addresses.wait("email|" + address)
        if wait:
            raise LockedError(wait)

    @staticmethod
    async def clear_email(handle):
        await handle.execute(
            "DELETE FROM identity.login_aliases WHERE email_claim AND NOT password_name_claim AND reset_name_until IS NULL"
        )
        await handle.execute(
            "UPDATE identity.login_aliases SET email_claim=false WHERE email_claim"
        )

    async def remove_email(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        return await self.set_email(
            database,
            passwords,
            throttle,
            address,
            {**body, "email": None},
            secret,
            days,
            session=session,
        )

    async def set_email(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        try:
            raw = body.get("email")
            removing = raw is None or (isinstance(raw, str) and not raw.strip(SPACE))
            email = None if removing else normalize_email(raw)
            async with self.locked(database, session) as handle:
                observed = await self.snapshot(handle)
                if not removing and not email:
                    raise Refused(400, ERRORS["email-invalid"], "email-invalid")
                if email == observed["email"]:
                    return 200, {"ok": True, "email": email}, None
            if not removing:
                self.email_pause(throttle, address, session.owner)
            proof = await self.prove(passwords, throttle, address, body, observed)
            async with self.locked(database, session) as handle:
                current = await self.snapshot(handle)
                await self.confirm(handle, proof, observed, current, session, throttle)
                if not removing:
                    self.email_pause(throttle, address, session.owner)
                    available = await handle.fetch(
                        "SELECT identity.alias_available($1) AS available", email
                    )
                    if not available[0]["available"]:
                        throttle.addresses.attempt("email|" + address)
                        throttle.addresses.attempt("email|acct:" + session.owner)
                        return (
                            409,
                            {"error": ERRORS["email-taken"], "code": "email-taken"},
                            None,
                        )
                await self.clear_email(handle)
                if email:
                    await self.claim(handle, email, True)
            return 200, {"ok": True, "email": email}, None
        except Refused as error:
            return error.response()

    async def password_status(
        self, database, passwords, throttle, address, body, secret, days, *, session
    ):
        async with database.transaction() as handle:
            await handle.execute("SELECT pg_advisory_xact_lock(728323)")
            if not await authorize(handle, session):
                return 401, {"error": "not signed in"}, None
            users = await handle.fetch("SELECT display_name FROM identity.users")
            name = users[0]["display_name"]
            credentials = await handle.fetch(
                "SELECT set_at FROM identity.password_credentials"
            )
            aliases = await handle.fetch(
                "SELECT alias_key FROM identity.login_aliases WHERE email_claim"
            )
            available = await handle.fetch(
                "SELECT identity.alias_available($1) AS available", name_key(name)
            )
            count = await handle.fetch(
                "SELECT count(*) AS count FROM identity.passkeys"
            )
            at = credentials[0]["set_at"] if credentials else None
            return (
                200,
                {
                    "set": bool(credentials),
                    "setAt": at.isoformat(timespec="milliseconds").replace(
                        "+00:00", "Z"
                    )
                    if at
                    else None,
                    "passkeys": count[0]["count"],
                    "name": name,
                    "nameTaken": not available[0]["available"],
                    "email": aliases[0]["alias_key"] if aliases else None,
                },
                None,
            )
