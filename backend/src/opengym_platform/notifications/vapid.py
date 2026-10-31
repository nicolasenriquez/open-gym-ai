"""Persistent Node-compatible VAPID material; never replace an existing key."""

import base64
import json
import os
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def public_key():
    directory = Path(os.environ.get("DATA_DIR", "/data"))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with _directory(directory) as parent:
        try:
            descriptor = os.open(
                "vapid.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
        except FileNotFoundError:
            private = ec.generate_private_key(ec.SECP256R1())
            value = {
                "publicKey": encode(
                    private.public_key().public_bytes(
                        Encoding.X962, PublicFormat.UncompressedPoint
                    )
                ),
                "privateKey": encode(
                    private.private_numbers().private_value.to_bytes(32, "big")
                ),
            }
            temporary = ".vapid-" + secrets.token_hex(16)
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(value, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(
                        temporary,
                        "vapid.json",
                        src_dir_fd=parent,
                        dst_dir_fd=parent,
                        follow_symlinks=False,
                    )
                    os.fsync(parent)
                except FileExistsError:
                    pass
            finally:
                os.unlink(temporary, dir_fd=parent)
            descriptor = os.open(
                "vapid.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
                raise ValueError
            value = json.loads(os.read(descriptor, 4097))
            raw = base64.b64decode(
                value["privateKey"] + "=" * (-len(value["privateKey"]) % 4),
                altchars=b"-_",
                validate=True,
            )
            if len(raw) != 32:
                raise ValueError
            private = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
            expected = encode(
                private.public_key().public_bytes(
                    Encoding.X962, PublicFormat.UncompressedPoint
                )
            )
            if value["publicKey"] != expected:
                raise ValueError
            return expected
        finally:
            os.close(descriptor)


@contextmanager
def _directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield descriptor
    finally:
        os.close(descriptor)
