"""Compatible admin settings; provider I/O happens after authorization commits."""

import asyncio
import json
import math
import os
import re
from datetime import UTC, datetime

from opengym_platform.coach.http import DEFAULT_BASES, base_url, invoke, models
from opengym_platform.coach.jobs import Refused
from opengym_platform.coach.payload import ASSETS, string
from opengym_platform.coach.pipeline import extract_json
from opengym_platform.coach.service import DEFAULT_MODELS, LABELS
from opengym_platform.identity.sessions import authorize


class Invalid(Exception):
    def __init__(self, error, status=400):
        self.body, self.status = {"error": error}, status


def truth(value):
    return value not in (None, False, 0, "")


def clamp(value, low, high, fallback=0):
    if isinstance(value, list):
        value = string(value)
    try:
        number = (
            float(int(value, 0))
            if isinstance(value, str)
            and re.fullmatch(
                r"0(?:[xX][0-9a-fA-F]+|[bB][01]+|[oO][0-7]+)", value.strip()
            )
            else float(value or 0)
        )
    except (ValueError, TypeError, OverflowError):
        number = 0
    if math.isnan(number):
        number = 0
    bounded = max(low, min(high, number or fallback))
    if int(bounded) != bounded:
        raise Invalid("limits must be whole numbers")
    return int(bounded)


def patch_config(current, body):
    settings = current["settings"].copy()
    providers = current["providers"]
    target = body.get("provider", settings["provider"])
    if not isinstance(target, str) or target not in LABELS:
        raise Invalid("unknown provider")
    settings["provider"] = target
    patch = {}
    for key in ("enabled", "community"):
        if key in body:
            settings[key] = truth(body[key])
    if "model" in body:
        patch["model"] = string(body["model"])[:80] if truth(body["model"]) else None
    options = providers[target]["options"].copy()
    for key in ("baseUrl", "headers"):
        if key not in body:
            continue
        if target != "compatible":
            raise Invalid(f"{target} has a fixed endpoint")
        if key == "baseUrl":
            raw = body[key]
            value = raw.strip() if isinstance(raw, str) else ""
            config = {"provider": target, "options": {"baseUrl": value}}
            if not value:
                raise Invalid(f"{target} has no default endpoint, enter one")
            if not base_url(config):
                raise Invalid("not a valid URL")
            options[key] = base_url(config)
        else:
            from opengym_platform.coach.http import RESERVED_HEADERS

            raw = body[key]
            if raw in (None, ""):
                options.pop(key, None)
                continue
            if not isinstance(raw, dict):
                raise Invalid("headers must be an object of name to value")
            if len(raw) > 8:
                raise Invalid("at most 8 headers")
            clean = {}
            for name, value in raw.items():
                if len(name) > 64 or not re.fullmatch(
                    r"[!#$%&'*+\-.^_`|~0-9a-z]+", name, re.IGNORECASE
                ):
                    raise Invalid(f"bad header name: {name}")
                if name.lower() in RESERVED_HEADERS:
                    raise Invalid(f"header is reserved: {name}")
                if not isinstance(value, str) or not value.strip():
                    raise Invalid(f"header {name} needs a value")
                if len(value) > 500 or "\r" in value or "\n" in value:
                    raise Invalid(f"header {name} is too long")
                clean[name.lower()] = value.strip()
            if clean:
                options[key] = clean
            else:
                options.pop(key, None)
    if "headers" in body or "baseUrl" in body:
        patch["options"] = options
    if truth(body.get("caps")):
        caps = body["caps"] if isinstance(body["caps"], dict) else {}
        settings["per_profile_daily"] = clamp(caps.get("perProfileDaily"), 0, 200)
        settings["instance_daily"] = clamp(caps.get("instanceDaily"), 0, 5000)
    for public, column, low, high in (
        ("maxMessageLen", "max_message_len", 200, 4000),
        ("maxOutputTokens", "max_output_tokens", 1024, 65536),
    ):
        if public in body:
            settings[column] = clamp(body[public], low, high, settings[column])
    return settings, {target: patch} if patch else {}


class Admin:
    def __init__(self, database, secrets):
        self.database, self.secrets = database, secrets

    async def preflight(self, session):
        async with self.database.transaction() as handle:
            await self.read(handle, session)

    async def read(self, handle, session):
        rows = await handle.fetch(
            "SELECT coach.read_instance($1,$2,$3) AS view",
            session.owner,
            session.version,
            session.expires_at,
        )
        value = json.loads(rows[0]["view"]) if rows[0]["view"] else None
        if value is None or not await authorize(handle, session):
            raise Refused("unauthorized")
        if not value:
            raise Invalid("admin only", 403)
        return value

    async def write(self, handle, session, settings, providers):
        rows = await handle.fetch(
            "SELECT coach.write_instance($1,$2,$3,$4::jsonb,$5::jsonb) AS view",
            session.owner,
            session.version,
            session.expires_at,
            json.dumps(settings),
            json.dumps(providers),
        )
        if rows[0]["view"] is None:
            raise Refused("unauthorized")
        if json.loads(rows[0]["view"]) == {}:
            raise Invalid("admin only", 403)

    async def handle(self, session, action, body):
        if action == "account":
            async with self.database.transaction() as handle:
                if not await authorize(handle, session):
                    raise Refused("unauthorized")
                rows = await handle.fetch(
                    "SELECT * FROM coach.credential_context($1,$2,$3)",
                    session.owner,
                    session.version,
                    session.expires_at,
                )
                if not rows:
                    raise Refused("unauthorized")
                context = dict(rows[0])
                credential = self.secrets.resolve(context, session.owner)
                record = credential.get("record") or {}
                return {
                    "mode": context["auth_mode"],
                    "provider": context["provider"],
                    "providerLabel": LABELS[context["provider"]],
                    "account": record.get("account") or None
                    if credential["ok"]
                    else None,
                    "connected": credential["ok"],
                    "reason": None if credential["ok"] else credential["reason"],
                    "message": None if credential["ok"] else credential.get("message"),
                }
        created = old = None
        try:
            async with self.database.transaction() as handle:
                current = await self.read(handle, session)
                if action == "view":
                    rows = await handle.fetch(
                        "SELECT coach.read_results($1,$2,$3) AS results",
                        session.owner,
                        session.version,
                        session.expires_at,
                    )
                    if rows[0]["results"] is None:
                        raise Refused("unauthorized")
                    current["results"] = json.loads(rows[0]["results"])
                if action == "config":
                    settings, providers = patch_config(current, body)
                    await self.write(handle, session, settings, providers)
                    return {"ok": True}
                if action in {"connect", "disconnect"}:
                    selected = body.get("provider", current["settings"]["provider"])
                    if not isinstance(selected, str) or selected not in LABELS:
                        raise Invalid("unknown provider")
                    if action == "connect":
                        if selected in {"claude", "codex"}:
                            raise Refused("off")
                        kind = string(body.get("type") or "")
                        if selected not in DEFAULT_BASES or kind != "apikey":
                            raise Invalid(
                                f'{selected} does not take a credential of type "{kind}"'
                            )
                        token = string(body.get("token") or "").strip()
                        if not token:
                            raise Invalid("no token supplied")
                        created = self.secrets.save(
                            {
                                "type": kind,
                                "account": string(body.get("account") or "")[:120],
                                "connectedAt": datetime.now(UTC)
                                .isoformat(timespec="milliseconds")
                                .replace("+00:00", "Z"),
                            },
                            token,
                        )
                    old = current["providers"][selected]["secret_ref"]
                    if any(
                        name != selected and row["secret_ref"] == old
                        for name, row in current["providers"].items()
                    ):
                        old = None
                    await self.write(
                        handle,
                        session,
                        current["settings"],
                        {selected: {"secret_ref": created}},
                    )
        except BaseException as error:
            # Unknown COMMIT retains the candidate; deleting it could destroy a live key.
            if created and getattr(error, "commit_outcome", None) != "unknown":
                self.secrets.remove(created)
            raise
        if action in {"connect", "disconnect"}:
            if old:
                self.secrets.remove(old)
            return {"ok": True}
        result = (
            await self.provider_check(current, action)
            if action in {"test", "models"}
            else await self.view(current)
        )
        # Provider calls hold no SQL lease; revalidate before returning their result.
        async with self.database.transaction() as handle:
            await self.read(handle, session)
        return result

    def credential(self, current):
        settings = current["settings"]
        selected = settings["provider"]
        context = {**settings, **current["providers"][selected]}
        if settings["auth_mode"] == "profile":
            return {"ok": False, "reason": "no-credential", "key": None}
        return self.secrets.resolve(context, context.get("bound_owner_id"))

    async def provider_check(self, current, action):
        settings = current["settings"]
        selected = settings["provider"]
        if selected in {"claude", "codex"} or os.environ.get(
            "COACH_DISABLED", ""
        ).lower() in {"1", "true", "yes", "on"}:
            raise Refused("off")
        if selected == "fixture":
            return (
                {"ok": True, "version": "Fixture"}
                if action != "models"
                else {
                    "ok": False,
                    "error": "this provider does not list models",
                    "models": [],
                }
            )
        if settings["auth_mode"] == "profile":
            return {
                "ok": False,
                "error": "no instance credential in per-profile mode",
                **({"models": []} if action == "models" else {}),
            }
        config = {**settings, **current["providers"][selected]}
        config["model"] = config["model"] or DEFAULT_MODELS.get(selected)
        credential = self.credential(current)
        if not credential["ok"]:
            return {
                "ok": False,
                "error": "no API key configured",
                **({"models": []} if action == "models" else {}),
            }
        if action == "models":
            return await models(config, credential["key"])
        if not config["model"]:
            return {"ok": False, "error": "no model chosen"}
        try:
            async with asyncio.timeout(90):
                result = await invoke(
                    config,
                    credential["key"],
                    'Reply with exactly this JSON object and nothing else: {"coach_contract":1,"ok":true}',
                    "",
                    None,
                    90,
                )
        except TimeoutError:
            return {"ok": False, "error": "timeout"}
        if result.get("error"):
            return {"ok": False, "error": result["error"]}
        value = extract_json(result["text"])
        return (
            {"ok": True, "version": "HTTPS"}
            if isinstance(value, dict) and truth(value.get("ok"))
            else {
                "ok": False,
                "error": "the provider answered, but not in the expected shape",
            }
        )

    async def view(self, current):
        settings, providers = current["settings"], current["providers"]
        selected = settings["provider"]
        record = providers[selected]
        filed = (
            self.secrets.read(record["secret_ref"])
            if selected in DEFAULT_BASES
            and self.secrets.instance_name(record["secret_ref"])
            else None
        )
        auth_state = {"state": "not-required"}
        if selected in DEFAULT_BASES:
            if record["secret_ref"] is None:
                auth_state = {
                    "state": "optional" if selected == "compatible" else "none"
                }
            elif not self.secrets.decrypt(filed):
                auth_state = {"state": "unreadable"}
            else:
                auth_state = {
                    "state": "connected",
                    "type": filed.get("type"),
                    "account": filed.get("account") or None,
                    "connectedAt": filed.get("connectedAt") or None,
                }
        check = {"ok": False, "error": "temporarily unavailable"}
        if selected not in {"claude", "codex"} and os.environ.get(
            "COACH_DISABLED", ""
        ).lower() not in {"1", "true", "yes", "on"}:
            if selected == "fixture":
                check = {"ok": True, "version": "Fixture"}
            elif (
                auth_state["state"] in {"none", "unreadable"}
                or settings["auth_mode"] == "profile"
            ):
                check = {"ok": True, "version": "HTTPS", "needsKey": True}
            else:
                check = await self.provider_check(current, "models")
                if check["ok"]:
                    check = {
                        **check,
                        "version": f"HTTPS · {len(check['models'])} models",
                    }
        return {
            "disabledByEnv": os.environ.get("COACH_DISABLED", "").lower()
            in {"1", "true", "yes", "on"},
            "enabled": settings["enabled"],
            "provider": selected,
            "providers": [
                {
                    "id": name,
                    "available": name not in {"claude", "codex"},
                    "label": label,
                    "runtime": "HTTPS"
                    if name in DEFAULT_BASES
                    else "Fixture"
                    if name == "fixture"
                    else "Claude Agent SDK"
                    if name == "claude"
                    else "Codex CLI",
                    "setupToken": False,
                    "deviceLogin": False,
                    "apiKey": name in DEFAULT_BASES,
                    "http": name in DEFAULT_BASES,
                    "baseUrl": name == "compatible",
                    "keyOptional": name == "compatible",
                    "keyPlaceholder": ASSETS["providers"]
                    .get(name, {})
                    .get("keyPlaceholder"),
                    "defaultModel": DEFAULT_MODELS.get(name),
                    "connected": providers[name]["connected"],
                }
                for name, label in LABELS.items()
            ],
            "model": record["model"] or DEFAULT_MODELS.get(selected),
            "models": {
                name: row["model"] for name, row in providers.items() if row["model"]
            },
            "baseUrl": base_url({"provider": selected, "options": record["options"]})
            if selected in DEFAULT_BASES
            else None,
            "headers": record["options"].get("headers")
            if selected in DEFAULT_BASES
            else None,
            "knownModels": check.get("models"),
            "caps": {
                "perProfileDaily": settings["per_profile_daily"],
                "instanceDaily": settings["instance_daily"],
            },
            "maxMessageLen": settings["max_message_len"],
            "maxOutputTokens": settings["max_output_tokens"],
            "community": settings["community"],
            "runtime": {
                "ok": check["ok"],
                "version": check.get("version"),
                "error": check.get("error"),
                "needsKey": check.get("needsKey", False),
            },
            "authMode": settings["auth_mode"],
            "boundUid": record["bound_owner_id"],
            "auth": auth_state,
            "unprivileged": {
                "ok": True,
                "dropped": False,
                "why": "this provider runs no child process",
            },
            "jobsToday": current.get("results", {}).get("jobsToday", 0),
            "lastSuccess": next(
                (
                    row
                    for row in current.get("results", {}).get("results", [])
                    if row["outcome"] in {"ready", "nochange"}
                ),
                None,
            ),
            "lastError": next(
                (
                    row
                    for row in current.get("results", {}).get("results", [])
                    if row["outcome"] == "failed"
                ),
                None,
            ),
            "recent": current.get("results", {}).get("results", [])[:20],
        }
