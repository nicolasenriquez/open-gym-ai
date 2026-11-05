"""Bounded public availability and consented execution settings."""

import json
import os

from opengym_platform.coach.payload import ASSETS

LABELS = {
    "fixture": "Fixture (testing)",
    "claude": "Claude (Anthropic)",
    "codex": "Codex (OpenAI)",
    **{provider: meta["label"] for provider, meta in ASSETS["providers"].items()},
}
DEFAULT_MODELS = {
    provider: meta["defaultModel"] for provider, meta in ASSETS["providers"].items()
}


async def execution_config(handle, session):
    rows = await handle.fetch(
        "SELECT * FROM coach.execution_config($1,$2,$3)",
        session.owner,
        session.version,
        session.expires_at,
    )
    if not rows:
        return None
    config = dict(rows[0])
    config["options"] = json.loads(config["options"])
    config["model"] = config["model"] or DEFAULT_MODELS.get(config["provider"])
    return config


async def public_config(database):
    rows = await database.fetch("SELECT * FROM coach.public_disclosure()")
    if not rows or os.environ.get("COACH_DISABLED", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None
    row = rows[0]
    # Deferred selections remain visible but never advertise executable work.
    if not row["enabled"] and row["provider"] not in {"claude", "codex"}:
        return None
    return {
        "enabled": row["enabled"],
        "provider": row["provider"],
        "providerLabel": LABELS[row["provider"]],
        "authMode": row["auth_mode"],
        "community": row["community"],
    }
