"""Legacy Coach encrypted records, confined to the configured local data directory."""

import base64
import json
import os
import re
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from opengym_platform.core.platform_settings import _secret

SHARED = "This instance is configured with a single shared account. Ask your admin to enable per-profile sign-in."


class SecretFiles:
    def __init__(self):
        self.directory = Path(os.environ.get("DATA_DIR", "/data"))
        self.key = None
        if os.environ.get("PLATFORM_COACH_SECRET_FILE"):
            secret = _secret("PLATFORM_COACH_SECRET_FILE").strip()
            if len(secret) < 32:
                raise ValueError("PLATFORM_COACH_CONFIG_INVALID")
            self.key = HKDF(
                algorithm=hashes.SHA256(), length=32, salt=b"", info=b"opengym-coach-v1"
            ).derive(secret.encode())

    @contextmanager
    def directory_fd(self):
        descriptor = os.open(
            self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            yield descriptor
        finally:
            os.close(descriptor)

    def valid_name(self, name):
        return isinstance(name, str) and re.fullmatch(
            r"(?:coach-key-[a-f0-9]{32}|coach-auth-[A-Za-z0-9_-]{1,64})\.json", name
        )

    def instance_name(self, name):
        return isinstance(name, str) and re.fullmatch(
            r"coach-key-[a-f0-9]{32}\.json", name
        )

    def read(self, name):
        if not self.valid_name(name):
            return None
        try:
            with self.directory_fd() as directory:
                descriptor = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
                )
                try:
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode) or info.st_size > 8 * 1024 * 1024:
                        return None
                    with os.fdopen(descriptor, "rb", closefd=False) as stream:
                        value = json.loads(stream.read(8 * 1024 * 1024 + 1))
                    return value if isinstance(value, dict) else None
                finally:
                    os.close(descriptor)
        except (OSError, ValueError, UnicodeError):
            return None

    def decrypt(self, record):
        try:
            if self.key is None or not record:
                return None
            raw = base64.b64decode(record["data"], validate=True)
            value = json.loads(
                AESGCM(self.key).decrypt(raw[:12], raw[28:] + raw[12:28], None)
            )
            return (
                value
                if isinstance(value, dict)
                and isinstance(value.get("token"), str)
                and value["token"]
                else None
            )
        except (KeyError, TypeError, ValueError, UnicodeError, InvalidTag):
            return None

    def save(self, record, token):
        if self.key is None:
            raise ValueError("COACH_DECRYPT_KEY_UNCONFIGURED")
        iv = secrets.token_bytes(12)
        encrypted = AESGCM(self.key).encrypt(
            iv,
            json.dumps(
                {"token": token}, separators=(",", ":"), ensure_ascii=False
            ).encode(),
            None,
        )
        record = {
            **record,
            "data": base64.b64encode(iv + encrypted[-16:] + encrypted[:-16]).decode(),
        }
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        name = "coach-key-" + secrets.token_hex(16) + ".json"
        with self.directory_fd() as directory:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(descriptor, "w", closefd=False) as stream:
                    json.dump(record, stream, separators=(",", ":"))
                    stream.flush()
                    os.fsync(descriptor)
            except BaseException:
                os.unlink(name, dir_fd=directory)
                raise
            finally:
                os.close(descriptor)
            os.fsync(directory)
        return name

    def remove(self, name):
        if not self.instance_name(name):
            return
        with self.directory_fd() as directory:
            try:
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("COACH_SECRET_PATH_INVALID")
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
            except FileNotFoundError:
                pass

    def resolve(self, context, owner):
        selected = context["provider"]
        mode = context["auth_mode"]
        if selected in {"claude", "codex"}:
            return {"ok": False, "reason": "off"}
        if (
            mode == "instance"
            and context.get("bound_owner_id")
            and context["bound_owner_id"] != owner
        ):
            return {"ok": False, "reason": "shared-account", "message": SHARED}
        if selected == "fixture":
            return {"ok": True, "record": None, "key": None}
        name = (
            f"coach-auth-{owner}.json"
            if mode == "profile"
            else context.get("secret_ref")
        )
        if mode == "instance" and name is not None and not self.instance_name(name):
            return {"ok": False, "reason": "no-credential", "record": None, "key": None}
        record = self.read(name)
        auth = self.decrypt(record)
        if not auth or record.get("type") != "apikey":
            optional = selected == "compatible" and mode == "instance" and name is None
            return {
                "ok": optional,
                "record": record,
                "key": None,
                "reason": None if optional else "no-credential",
            }
        return {"ok": True, "record": record, "key": auth["token"]}
