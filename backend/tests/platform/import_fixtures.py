"""Small independent legacy files, frozen into the read-only test image."""

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SECRET = "synthetic-import-coach-signing-key-0123456789"
PASSWORD = "synthetic-import-password"
AT = "2026-10-31T12:00:00.000Z"


def fixtures(root):
    salt = b"independent-salt"
    digest = hashlib.scrypt(
        PASSWORD.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024
    )
    password = (
        "$scrypt$v=1$ln=15,r=8,p=1$"
        + base64.b64encode(salt).decode()
        + "$"
        + base64.b64encode(digest).decode()
    )
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"", info=b"opengym-coach-v1"
    ).derive(SECRET.encode())
    iv = b"012345678901"
    encrypted = AESGCM(key).encrypt(
        iv, b'{"token":"synthetic-import-provider-key"}', None
    )
    auth = {
        "type": "apikey",
        "account": "synthetic-account",
        "connectedAt": AT,
        "data": base64.b64encode(iv + encrypted[-16:] + encrypted[:-16]).decode(),
    }
    document = {
        "_rev": 7,
        "_wid": "legacy-write",
        "_wids": ["old", "legacy-write"],
        "_unstamped": True,
        "_prior": {"notes": None},
        "settings": {"coach": {"consent": True}},
        "workouts": [{"id": "w-old", "notes": None, "_f": {"notes": 4}}],
        "resetAt": 0,
    }
    files = {
        "db.json": {
            "users": [
                {
                    "id": "A",
                    "name": "Ａlice",
                    "admin": True,
                    "sv": 3,
                    "created": AT,
                    "pw": {"h": password, "set": AT},
                    "email": "alice@example.test",
                    "lastPull": 1793448000000,
                    "lastReminder": "2026-10-30",
                    "lastNudge": "2026-10-31",
                    "invitedBy": "OLD",
                },
                {
                    "id": "B",
                    "name": "Bob",
                    "disabled": True,
                    "sv": 2,
                    "pwReset": {
                        "h": "ab" * 32,
                        "exp": 1793534400000,
                        "by": "gone-admin",
                    },
                },
            ],
            "creds": [],
            "subs": [
                {
                    "userId": "A",
                    "endpoint": "https://push.example.test/a",
                    "keys": {"p256dh": "public-key", "auth": "auth-key"},
                    "deviceId": "device-01",
                    "created": AT,
                }
            ],
            "invites": [
                {
                    "code": "OLD",
                    "note": "legacy",
                    "createdBy": "gone-admin",
                    "usedBy": "A",
                    "usedAt": AT,
                }
            ],
            "deviceLinks": [
                {
                    "userId": "A",
                    "h": "cd" * 32,
                    "created": 1793448000000,
                    "exp": 1793448600000,
                }
            ],
        },
        "state-A.json": document,
        "coach.json": {
            "enabled": True,
            "provider": "codex",
            "authMode": "instance",
            "community": True,
            "models": {"codex": "legacy-codex-model", "openai": "legacy-http-model"},
            "providerOptions": {
                "compatible": {"baseUrl": "https://provider.example.test/v1"}
            },
            "auth": {
                "openai": auth,
                "codex": {"type": "oauth", "data": "protected-deferred"},
            },
            "boundUid": {"openai": "A", "codex": "A"},
            "caps": {"perProfileDaily": 10, "instanceDaily": 30},
            "maxMessageLen": 1000,
            "maxOutputTokens": 16000,
            "daily": {"date": "2026-10-31", "count": 19},
            "log": [],
        },
        "coach/A.json": {
            "share": True,
            "daily": {"date": "2026-10-31", "count": 4},
            "current": None,
            "pending": None,
            "history": [
                {
                    "id": "job-old",
                    "kind": "review",
                    "outcome": "ready",
                    "at": 1793448000000,
                },
                {
                    "id": "job-old",
                    "kind": "review",
                    "outcome": "applied",
                    "at": 1793448000001,
                    "accepted": 2,
                    "rejected": 1,
                },
            ],
        },
        "coach-auth-A.json": auth,
        "vapid.json": {
            "publicKey": "synthetic-vapid-public",
            "privateKey": "synthetic-vapid-private",
        },
    }
    from webauthn_vectors import VECTORS

    vector = VECTORS["cases"][0]
    files["db.json"]["creds"] = [
        {
            "id": vector["credentialId"],
            "userId": "A",
            "publicKey": vector["publicKey"],
            "counter": 17,
            "transports": ["internal", "hybrid"],
            "name": "Legacy key",
        }
    ]
    private = ec.derive_private_key(12345, ec.SECP256R1())
    files["vapid.json"] = {
        "privateKey": base64.urlsafe_b64encode(
            private.private_numbers().private_value.to_bytes(32, "big")
        )
        .decode()
        .rstrip("="),
        "publicKey": base64.urlsafe_b64encode(
            private.public_key().public_bytes(
                Encoding.X962, PublicFormat.UncompressedPoint
            )
        )
        .decode()
        .rstrip("="),
    }
    files["coach/A.json"]["pending"] = {
        "id": "proposal-old",
        "kind": "review",
        "createdAt": 1793448000000,
        "expiresAt": 1794657600000,
        "planHash": "legacy-plan",
        "iteration": 1,
        "changes": [],
        "reading": "preserved",
    }
    files["coach.json"]["log"] = [
        {"at": AT, "kind": "review", "trigger": "manual", "outcome": "ready", "ms": 12}
    ]
    variants = {"valid": files}
    for case in (
        "fractional",
        "orphan",
        "alias",
        "unknown",
        "log_detail",
        "bad_history",
        "bad_key",
        "current",
        "http",
        "claude",
        "bad_vapid",
        "revoked",
    ):
        variant = copy.deepcopy(files)
        if case == "revoked":
            variant["db.json"]["invites"][0]["revoked"] = True
        elif case == "fractional":
            variant["state-A.json"]["_rev"] = 1.5
        elif case == "orphan":
            variant["db.json"]["subs"][0]["userId"] = "missing"
        elif case == "alias":
            variant["db.json"]["users"][1]["email"] = "alice@example.test"
        elif case == "unknown":
            variant["db.json"]["users"][0]["unmapped"] = "never-discard"
        elif case == "log_detail":
            variant["coach.json"]["log"] = [
                {
                    "at": AT,
                    "uid": "A",
                    "kind": "review",
                    "trigger": "manual",
                    "outcome": "ready",
                    "ms": 1,
                    "detail": {"accepted": 1},
                }
            ]
        elif case == "bad_history":
            variant["coach/A.json"]["history"][0]["outcome"] = "unmapped"
        elif case == "bad_key":
            variant["db.json"]["creds"][0]["publicKey"] = "invalid"
        elif case == "current":
            variant["coach/A.json"]["current"] = {
                "id": "interrupted",
                "kind": "review",
                "state": "running",
                "startedAt": 1793448000000,
            }
        elif case == "http":
            variant["coach.json"]["provider"] = "openai"
            variant["coach.json"]["authMode"] = "profile"
        elif case == "claude":
            variant["coach.json"]["provider"] = "claude"
            variant["coach.json"]["models"]["claude"] = "legacy-claude-model"
        elif case == "bad_vapid":
            variant["vapid.json"]["privateKey"] = "invalid"
        variants[case] = variant
    for case in (
        "duplicate",
        "unicode",
        "nul",
        "missing_null",
        "utf16",
        "whole_number",
        "exponent_number",
    ):
        variants[case] = copy.deepcopy(files)
    for case, content in variants.items():
        directory = root / case
        directory.mkdir(parents=True)
        for name, value in content.items():
            file = directory / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(value, ensure_ascii=True))
        (directory / "secret").write_text(SECRET)
        (directory / "audit.log").write_text(
            '{"id":41,"ts":1793448000000,"ev":"auth.password","ok":true,"uid":"gone-owner","name":"historic"}\n'
        )
        media = directory / "uploads/A"
        media.mkdir(parents=True)
        content = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR4kAAAAASUVORK5CYII="
        )
        (media / (hashlib.sha256(content).hexdigest() + ".png")).write_bytes(content)
        (media / ".gc.json").write_text("{}")
        if case == "duplicate":
            (directory / "state-A.json").write_text('{"_rev":7,"_rev":8}')
        elif case == "unicode":
            (directory / "state-A.json").write_text('{"notes":"\\ud800"}')
        elif case == "nul":
            (directory / "state-A.json").write_text('{"notes":"\\u0000"}')
        elif case == "missing_null":
            (directory / "state-A.json").write_text(
                '{"_rev":null,"_wid":null,"optional":null}'
            )
        elif case == "utf16":
            (directory / "state-A.json").write_bytes('{"_rev":7}'.encode("utf-16"))
        elif case == "whole_number":
            (directory / "state-A.json").write_text('{"_rev":7.0,"_wid":"whole"}')
        elif case == "exponent_number":
            (directory / "state-A.json").write_text(
                '{"_rev":0,"number":1e20,"fraction":0.1,"flag":true,"list":[null,1,false]}'
            )
    (root / "symlink").symlink_to(root / "valid", target_is_directory=True)


if __name__ == "__main__":
    fixtures(Path(sys.argv[1]))
