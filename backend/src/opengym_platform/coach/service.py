"""Read-only availability; credentials and execution arrive in later slices."""

import os

LABELS = {
    "fixture": "Fixture (testing)",
    "claude": "Claude (Anthropic)",
    "codex": "Codex (OpenAI)",
    "anthropic": "Anthropic API",
    "openai": "OpenAI API",
    "gemini": "Google Gemini",
    "compatible": "OpenAI-compatible endpoint",
}


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
