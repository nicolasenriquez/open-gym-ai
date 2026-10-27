"""Own account operations; namespace precedes actor locks, crypto stays outside."""

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import partial

from webauthn import verify_authentication_response
from webauthn.helpers.exceptions import WebAuthnException

from opengym_platform.identity.passwords import SPACE, make_hash, name_key
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
    def __init__(self, passkeys):
        self.passkeys = passkeys

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
        passkeys = await handle.fetch(
            "SELECT credential_id,public_key,counter FROM identity.passkeys"
        )
        aliases = await handle.fetch(
            "SELECT alias_key FROM identity.login_aliases WHERE email_claim"
        )
        return {
            **dict(users[0]),
            "stored": credentials[0]["scrypt_hash"] if credentials else None,
            "passkeys": passkeys,
            "email": aliases[0]["alias_key"] if aliases else None,
        }

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
            except (WebAuthnException, ValueError, TypeError, KeyError, OverflowError):
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
