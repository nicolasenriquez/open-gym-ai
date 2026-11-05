"""RFC 8291/8292 Web Push, with pinned DNS, original TLS identity and no redirects."""

import asyncio
import base64
import json
import os
import secrets
import socket
import ssl
import time

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from opengym_platform.notifications.endpoints import endpoint_error, private_address
from opengym_platform.notifications.vapid import encode, key_pair


def decode(value):
    return base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )


def derive(secret, salt, info, length):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(
        secret
    )


def encrypted(subscription, payload):
    receiver, auth = decode(subscription["p256dh"]), decode(subscription["auth"])
    if len(receiver) != 65 or len(auth) < 16:
        raise ValueError("PUSH_KEY_INVALID")
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), receiver)
    ephemeral = ec.generate_private_key(ec.SECP256R1())
    sender = ephemeral.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    shared = ephemeral.exchange(ec.ECDH(), peer)
    ikm = derive(shared, auth, b"WebPush: info\x00" + receiver + sender, 32)
    salt = secrets.token_bytes(16)
    key = derive(ikm, salt, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = derive(ikm, salt, b"Content-Encoding: nonce\x00", 12)
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    encrypted_records = []
    cipher = AESGCM(key)
    for sequence, offset in enumerate(range(0, max(1, len(plaintext)), 4079)):
        final = offset + 4079 >= len(plaintext)
        record_nonce = (int.from_bytes(nonce, "big") ^ sequence).to_bytes(12, "big")
        encrypted_records.append(
            cipher.encrypt(
                record_nonce,
                plaintext[offset : offset + 4079] + (b"\x02" if final else b"\x01"),
                None,
            )
        )
    return (
        salt
        + (4096).to_bytes(4, "big")
        + bytes([65])
        + sender
        + b"".join(encrypted_records)
    )


def authorization(url):
    pair = key_pair()
    private = ec.derive_private_key(
        int.from_bytes(decode(pair["privateKey"]), "big"), ec.SECP256R1()
    )
    audience = url.copy_with(path="/", query=None, fragment=None)
    claims = {
        "aud": str(audience).rstrip("/"),
        "exp": int(time.time()) + 12 * 3600,
        "sub": os.environ.get("VAPID_SUBJECT")
        or os.environ.get("ORIGIN", "http://localhost:8080"),
    }
    token = (
        encode(b'{"typ":"JWT","alg":"ES256"}')
        + "."
        + encode(json.dumps(claims, separators=(",", ":")).encode())
    )
    r, s = decode_dss_signature(private.sign(token.encode(), ec.ECDSA(hashes.SHA256())))
    token += "." + encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return "vapid t=" + token + ", k=" + pair["publicKey"]


async def send(subscription, payload):
    endpoint = subscription["endpoint"]
    if endpoint_error(endpoint):
        raise ValueError("PUSH_ENDPOINT_REFUSED")
    url = httpx.URL(endpoint)
    async with asyncio.timeout(7):
        addresses = await asyncio.get_running_loop().getaddrinfo(
            url.host, url.port or 443, type=socket.SOCK_STREAM
        )
        if not addresses or any(private_address(row[4][0]) for row in addresses):
            raise ValueError("PUSH_ADDRESS_REFUSED")
        # Connect to the checked literal: a second lookup cannot rebind the hostname.
        pinned = url.copy_with(host=addresses[0][4][0])
        headers = {
            "Host": url.netloc.decode(),
            "Authorization": authorization(url),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": "2419200",
            "Urgency": "high",
        }
        body = encrypted(subscription, payload)
        async with (
            httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=6,
                verify=ssl.create_default_context(),
            ) as client,
            client.stream(
                "POST",
                pinned,
                headers=headers,
                content=body,
                extensions={"sni_hostname": url.host},
            ) as response,
        ):
            return response.status_code
