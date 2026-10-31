"""Bounded postcommit event writes and compatible administrative reads."""

import ipaddress
import json
import logging
import math
import os
import time
from datetime import UTC, datetime

from opengym_platform.core.database import DatabaseError
from opengym_platform.core.platform_settings import environment_number


def bounded(value, size):
    if not isinstance(value, str):
        return None
    return (
        value.encode("utf-16-le", "surrogatepass")[: size * 2]
        .decode("utf-16-le", "replace")
        .replace("\x00", "")
        or None
    )


class Audit:
    def __init__(self, database):
        self.database = database
        self.enabled = os.environ.get("AUDIT_LOG", "").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.cap = min(
            9007199254740991,
            environment_number(
                "AUDIT_MAX", 0 if os.environ.get("AUDIT_MAX") else 5000, 0
            ),
        )
        self.days = min(
            365000,
            environment_number(
                "AUDIT_DAYS", 0 if os.environ.get("AUDIT_DAYS") else 90, 0
            ),
        )
        raw = os.environ.get("AUDIT_IP", "").lower()
        self.ip_mode = (
            "full"
            if raw == "full"
            else "net"
            if raw in {"1", "true", "yes", "on", "net"}
            else "off"
        )
        self.degraded = False
        self.failures = 0
        self.failure_windows = {}

    def allow_failure(self, event, address, *, limit=10, seconds=60):
        now = time.monotonic()
        self.failure_windows = {
            k: v for k, v in self.failure_windows.items() if now < v[0]
        }
        keys = ((event, address, limit), (event, "*", 120))
        for ev, source, cap in keys:
            if self.failure_windows.get((ev, source), (now, 0))[1] >= cap:
                return False
        for ev, source, _ in keys:
            key = (ev, source)
            if key not in self.failure_windows and len(self.failure_windows) >= 10000:
                del self.failure_windows[next(iter(self.failure_windows))]
            deadline, count = self.failure_windows.get(key, (now + seconds, 0))
            self.failure_windows[key] = (deadline, count + 1)
        return True

    async def identity_result(
        self, operation, status, result, session, request, address
    ):
        events = {
            "password_login": "auth.password.ok",
            "password_register": "auth.register.ok",
            "register_verify": "auth.register.ok",
            "login_verify": "auth.login.ok",
            "redeem": "auth.password.reset",
            "add_passkey_verify": "auth.passkey.add",
            "remove_passkey": "auth.passkey.remove",
            "logout_all": "auth.logout.all",
            "create": "auth.link.create",
            "verify": "auth.link.ok",
            "pair_create": "auth.pair.create",
            "pair_redeem": "auth.pair.ok",
        }
        event = events.get(operation)
        success = status == 200
        code = result.get("code")
        if not success:
            if (
                operation
                in {"register_options", "password_register", "register_verify"}
                and code == "invite"
            ):
                event = "auth.register.denied"
            elif operation in {
                "password_login",
                "register_verify",
                "login_verify",
                "verify",
                "pair_redeem",
            }:
                event = {
                    "password_login": "auth.password.fail",
                    "register_verify": "auth.register.fail",
                    "login_verify": "auth.login.fail",
                    "verify": "auth.link.fail",
                    "pair_redeem": "auth.pair.fail",
                }[operation]
            elif operation == "add_passkey_verify":
                event = "auth.passkey.fail"
            elif operation == "options":
                event = "auth.link.fail"
            elif operation == "password_register" and code == "email-taken":
                event = "auth.register.fail"
            elif code in {"current-wrong", "passkey"}:
                event = "auth.proof.fail"
            elif operation == "set_email" and code == "email-taken":
                event = "auth.email.fail"
            elif operation != "redeem":
                return
        if not event:
            return
        if (
            not success
            and operation in {"register_verify", "login_verify", "pair_redeem"}
            and not self.allow_failure(event, address)
        ):
            return
        user = result.get("user", {})
        await self.append(
            event,
            request=request,
            ok=success,
            actor=user.get("id") or (session.owner if session else None),
            name=user.get("name"),
            message=None
            if success
            else {
                "current-wrong": "bad-current",
                "passkey": "step-up-failed",
                "disabled": "account-disabled",
            }.get(code, code)
            if code
            in {
                "invite",
                "email-taken",
                "current-wrong",
                "passkey",
                "disabled",
                "bad-credentials",
            }
            else "verification-failed",
            action={
                "set_password": "password",
                "remove_password": "password-remove",
                "set_email": "email",
                "remove_email": "email-remove",
                "add_passkey_options": "passkey-add",
                "remove_passkey": "passkey-remove",
                "create": "device-link",
            }.get(operation)
            if event == "auth.proof.fail"
            else None,
        )
        if (
            success
            and operation in {"password_register", "register_verify"}
            and user.get("admin")
            and os.environ.get("FIRST_USER_ADMIN", "").lower()
            in {"1", "true", "yes", "on"}
        ):
            try:
                rows = await self.database.fetch(
                    "SELECT identity.public_user_count() AS count"
                )
                if rows[0]["count"] == 1:
                    await self.append(
                        "admin.first-user",
                        request=request,
                        actor=user["id"],
                        name=user.get("name"),
                    )
            except DatabaseError:
                self.failed()

    def ip(self, request):
        if self.ip_mode == "off" or request is None:
            return None
        raw = (
            request.headers.get("cf-connecting-ip", "").strip()
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or request.headers.get("x-real-ip", "").strip()
            or (request.client.host if request.client else "")
        )
        if "%" in raw:
            return None
        try:
            address = ipaddress.ip_address(raw.strip("[]").removeprefix("::ffff:"))
            if self.ip_mode == "full":
                return str(address)
            prefix = 24 if address.version == 4 else 48
            return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))
        except ValueError:
            return None

    async def settings(self, tx):
        for key, value in (("max", math.ceil(self.cap)), ("days", self.days)):
            await tx.execute(
                "SELECT set_config($1,$2,true)", "app.audit_" + key, str(value)
            )

    async def append(
        self,
        event,
        *,
        request=None,
        ok=True,
        actor=None,
        target=None,
        name=None,
        target_name=None,
        message=None,
        action=None,
    ):
        if not self.enabled:
            return
        try:
            async with self.database.transaction() as tx:
                await self.settings(tx)
                await tx.execute(
                    "SELECT audit.append_event($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
                    datetime.now(UTC),
                    event,
                    ok,
                    actor,
                    target,
                    bounded(name, 40),
                    bounded(target_name, 40),
                    bounded(message, 120),
                    bounded(action, 40),
                    self.ip(request),
                )
            self.degraded = False
        except Exception:  # noqa: BLE001 -- audit is a best-effort boundary after business commit
            self.failed()

    def failed(self):
        self.failures += 1
        if not self.degraded:
            self.degraded = True
            # Never log exception text, SQL, request bodies or event fields.
            try:
                logging.getLogger(__name__).warning("AUDIT_WRITE_FAILED")
            except Exception:  # noqa: BLE001,S110 -- keep in-memory degradation when the logging sink fails too
                pass

    async def read(self, session, *, before=None, limit=100, category=""):
        async with self.database.transaction() as tx:
            await self.settings(tx)
            await tx.execute("SELECT set_config('app.audit_cat',$1,true)", category)
            rows = await tx.fetch(
                "SELECT audit.read_events($1,$2,$3,$4,$5) AS view",
                session.owner,
                session.version,
                session.expires_at,
                before,
                limit,
            )
            result = json.loads(rows[0]["view"]) if rows[0]["view"] else None
            status = 401 if result is None else 403 if result == {} else 200
        if status != 200:
            return status, {"error": "not signed in" if status == 401 else "forbidden"}
        result.update(
            enabled=self.enabled,
            ip_mode=self.ip_mode,
            retention={"max": self.cap, "days": self.days},
            now=int(time.time() * 1000),
        )
        return status, result

    async def clear(self, session, request):
        async with self.database.transaction() as tx:
            rows = await tx.fetch(
                "SELECT audit.clear_events($1,$2,$3) AS view",
                session.owner,
                session.version,
                session.expires_at,
            )
            result = json.loads(rows[0]["view"]) if rows[0]["view"] else None
            status = 401 if result is None else 403 if result == {} else 200
        if status != 200:
            return status, {"error": "not signed in" if status == 401 else "forbidden"}
        await self.append("admin.audit.clear", actor=session.owner, request=request)
        return status, result
