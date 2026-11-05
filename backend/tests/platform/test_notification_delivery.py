"""Internal scheduled delivery with restricted SQL, a fixed clock and fake push."""

import asyncio
import base64
import json
import secrets
import socket
import ssl
from datetime import UTC, datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.x509.oid import NameOID
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414

from opengym_platform.application import create_app

NOW = datetime.fromisoformat("2026-11-01T05:35:00+00:00")
STATE = {
    "reminder": {"on": True, "time": "01:30", "tz": "America/New_York"},
    "routines": [{"id": "r", "name": "Strength", "emoji": "💪"}],
    "week": {"0": "r"},
    "workouts": [],
}


async def seed(observer, state=None, owner="A"):
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES($1,$2::jsonb) "
        "ON CONFLICT(owner_id) DO UPDATE SET document=excluded.document",
        owner,
        json.dumps(STATE if state is None else state),
    )
    await observer.execute(
        "INSERT INTO notifications.subscriptions VALUES($1,$2,'p','a',NULL,'2020-01-01') ON CONFLICT DO NOTHING",
        f"https://push.example/{owner}",
        owner,
    )


def runtime_environment(monkeypatch, environment):
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )


@pytest.mark.asyncio
async def test_local_reminder_is_claimed_once_across_repeated_hour_and_restart(
    identities,
    monkeypatch,
):
    observer, environment = identities
    await seed(observer)
    await seed(observer, {**STATE, "reminder": {"on": False}}, "B")
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append((subscription["endpoint"], payload))
        return 201

    for instant in (NOW, datetime.fromisoformat("2026-11-01T06:35:00+00:00")):
        app = create_app()
        async with app.router.lifespan_context(app):
            notifications = getattr(app.state, "notifications", None)
            assert notifications is not None, (
                "Scheduler must exist without a signed-in HTTP request"
            )
            notifications.send = send
            await notifications.tick(instant)
    assert calls == [
        (
            "https://push.example/A",
            {
                "title": "💪 Strength today",
                "body": "It's on your plan. Let's go 💪",
                "tag": "day-reminder",
            },
        )
    ]
    assert (
        str(
            await observer.fetchval(
                "SELECT last_reminder_date FROM notifications.delivery_state WHERE owner_id='A'"
            )
        )
        == "2026-11-01"
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM notifications.delivery_state WHERE owner_id='B'"
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("patch", "instant", "tag"),
    [
        ({"dayPlan": {"2026-11-01": "rest"}}, "2026-11-01T05:35:00+00:00", None),
        (
            {"dayNotes": {"2026-11-01": {"tag": "sick"}}},
            "2026-11-01T05:35:00+00:00",
            None,
        ),
        (
            {"dayNotes": {"2026-11-01": {"text": "Away"}}},
            "2026-11-01T05:35:00+00:00",
            None,
        ),
        ({"workouts": [{"d": "2026-11-01"}]}, "2026-11-01T05:35:00+00:00", None),
        ({}, "2026-11-01T05:45:00+00:00", "day-reminder"),
        ({}, "2026-11-01T05:46:00+00:00", None),
        (
            {"week": {}, "queue": {"ids": ["r"], "since": 0, "startsOn": "2026-11-01"}},
            "2026-11-01T05:35:00+00:00",
            "day-reminder",
        ),
        (
            {"week": {}, "dayPlan": {"2026-11-01": "r"}},
            "2026-11-01T05:35:00+00:00",
            "day-reminder",
        ),
        (
            {
                "reminder": {
                    "on": True,
                    "nudge": True,
                    "time": "08:00",
                    "tz": "America/New_York",
                }
            },
            "2026-11-02T01:00:00+00:00",
            "nudge",
        ),
        (
            {"reminder": {"on": True, "nudge": True, "time": "19:31", "tz": "UTC"}},
            "2026-11-01T21:30:00+00:00",
            None,
        ),
        (
            {"reminder": {"on": True, "time": "01:30", "tz": "invalid"}},
            "2026-11-01T05:35:00+00:00",
            None,
        ),
    ],
)
async def test_training_preferences_choose_local_reminders_and_nudges(
    identities, monkeypatch, patch, instant, tag
):
    observer, environment = identities
    await seed(observer, {**STATE, **patch})
    runtime_environment(monkeypatch, environment)
    calls = []

    async def send(subscription, payload):
        calls.append(payload)
        return 201

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        await app.state.notifications.tick(datetime.fromisoformat(instant))
    assert [p["tag"] for p in calls] == ([tag] if tag else [])


@pytest.mark.asyncio
async def test_failed_push_is_not_retried_and_only_own_dead_endpoints_are_pruned(
    identities, monkeypatch
):
    observer, environment = identities
    await seed(observer)
    for suffix in ("gone", "forbidden", "failed"):
        await observer.execute(
            "INSERT INTO notifications.subscriptions VALUES($1,'A','p','a',NULL,now())",
            "https://push.example/" + suffix,
        )
    await seed(observer, {**STATE, "reminder": {"on": False}}, "B")
    runtime_environment(monkeypatch, environment)
    calls = []
    observer_lock = asyncio.Lock()

    async def send(subscription, payload):
        # A real independent UPDATE proves no account lock/lease surrounds the transport.
        async with observer_lock:
            await observer.execute(
                "UPDATE identity.users SET display_name=display_name WHERE id='A'"
            )
        endpoint = subscription["endpoint"]
        calls.append(endpoint)
        if endpoint.endswith("failed"):
            raise OSError("PRIVATE-TRANSPORT-MARKER")
        return (
            410
            if endpoint.endswith("gone")
            else 403
            if endpoint.endswith("forbidden")
            else 201
        )

    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.notifications.send = send
        await app.state.notifications.tick(NOW)
        await app.state.notifications.tick(NOW)
    assert sorted(calls) == sorted(
        "https://push.example/" + s for s in ("A", "gone", "forbidden", "failed")
    )
    assert [
        r["endpoint"]
        for r in await observer.fetch(
            "SELECT endpoint FROM notifications.subscriptions ORDER BY endpoint"
        )
    ] == [
        "https://push.example/A",
        "https://push.example/B",
        "https://push.example/failed",
    ]
    assert (
        str(
            await observer.fetchval(
                "SELECT last_reminder_date FROM notifications.delivery_state WHERE owner_id='A'"
            )
        )
        == "2026-11-01"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "private", "mixed", "redirect", "long"])
async def test_real_transport_encrypts_like_independent_node_vector_and_pins_dns(
    identities, monkeypatch, tmp_path, mode
):
    observer, environment = identities
    await seed(observer)
    runtime_environment(monkeypatch, environment)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "private-data"))
    if mode == "long":
        await observer.execute(
            "UPDATE training.documents SET document=jsonb_set(document,'{routines,0,name}',$1::jsonb)",
            json.dumps("X" * 9000),
        )
    # Private TLS fixture only; no public service, real DNS or credentials.
    key = ec.derive_private_key(3, ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "push.example")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(datetime(2020, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2040, 1, 1, tzinfo=UTC))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("push.example")]), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    certfile, keyfile = tmp_path / "cert.pem", tmp_path / "key.pem"
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile, keyfile)
    monkeypatch.setenv("SSL_CERT_FILE", str(certfile))
    calls = []

    async def receive(reader, writer):
        try:
            head = (await reader.readuntil(b"\r\n\r\n")).decode()
            headers = dict(
                line.split(": ", 1) for line in head.split("\r\n")[1:] if ": " in line
            )
            body = await reader.readexactly(int(headers["Content-Length"]))
            calls.append((head, headers, body))
            writer.write(
                b"HTTP/1.1 307 Redirect\r\nLocation: https://127.0.0.1/private\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                if mode == "redirect"
                else b"HTTP/1.1 201 Created\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    listener = await asyncio.start_server(receive, "127.0.0.1", 0, ssl=context)
    async with listener:
        port = listener.sockets[0].getsockname()[1]
        endpoint = f"https://push.example:{port}/A"
        await observer.execute(
            "UPDATE notifications.subscriptions SET endpoint=$1,p256dh=$2,auth=$3",
            endpoint,
            "BGsX0fLhLEJH-Lzm5WOkQPJ3A32BLeszoPShOUXYmMKWT-NC4v4af5uO5-tKfA-eFivOM1drMV7Oy7ZAaDe_UfU",
            "AQEBAQEBAQEBAQEBAQEBAQ",
        )
        resolves = []
        original_resolve = asyncio.get_running_loop().getaddrinfo

        async def resolve(host, port, **kwargs):
            if host != "push.example":
                return await original_resolve(host, port, **kwargs)
            resolves.append(host)
            addresses = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))
            ]
            if mode == "mixed":
                addresses.append(
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.2", port))
                )
            return addresses

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
        monkeypatch.setattr(
            ec, "generate_private_key", lambda curve: ec.derive_private_key(2, curve)
        )
        monkeypatch.setattr(secrets, "token_bytes", lambda n: bytes(n))
        monkeypatch.setenv(
            "ALLOWED_PRIVATE_IPS", "" if mode == "private" else "127.0.0.1"
        )
        app = create_app()
        errors = []
        async with app.router.lifespan_context(app):
            actual_send = app.state.notifications.send

            async def observed_send(subscription, payload):
                try:
                    return await actual_send(subscription, payload)
                except Exception as error:
                    errors.append(repr(error))
                    raise

            app.state.notifications.send = observed_send
            await app.state.notifications.tick(NOW)
        assert resolves == ["push.example"]
        if mode in ("private", "mixed"):
            assert calls == []
            assert errors == ["ValueError('PUSH_ADDRESS_REFUSED')"]
            return
        assert len(calls) == 1, errors
        head, headers, body = calls[0]
        assert f"Host: push.example:{port}" in head
        assert headers["Content-Encoding"] == "aes128gcm"
        assert headers["Urgency"] == "high"
        assert headers["Authorization"].startswith("vapid t=")
        token, vapid_public = (
            headers["Authorization"].removeprefix("vapid t=").split(", k=")
        )
        header, claims, signature = token.split(".")
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        assert json.loads(decode(header)) == {"typ": "JWT", "alg": "ES256"}
        claims = json.loads(decode(claims))
        assert claims["aud"] == f"https://push.example:{port}"
        assert claims["sub"] == environment.get("ORIGIN", "http://localhost:8080")
        assert 43000 < claims["exp"] - datetime.now(UTC).timestamp() <= 43200
        sig = decode(signature)
        ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), decode(vapid_public)
        ).verify(
            encode_dss_signature(int.from_bytes(sig[:32]), int.from_bytes(sig[32:])),
            token.rsplit(".", 1)[0].encode(),
            ec.ECDSA(hashes.SHA256()),
        )
        # Node http_ece, subscriber scalar 1 / sender 2 / auth 16x01 / salt 16x00.
        if mode == "long":
            import hashlib

            assert len(body) == 9223
            assert (
                hashlib.sha256(body).hexdigest()
                == "f0e6638d363e625546173ec2038f6961fc4c8c5db6129dc24ce3185ddd32143f"
            )
            return
        assert (
            body.hex()
            == "000000000000000000000000000000000000100041047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d18cb77882d4dc1eeffa777b14350ac5de2f8d26305bb96f1e3a4633413eb097d2673c02ede43580a4a195d894ccaac65a92f110a20f481a2f077444f4347fdfad6a4f3f170366eb8038b2743b069812ca2ba8e854c6931d1c321c87054dbed81996555f552f370a921739c1c4faae1c"
        )
        assert resolves == ["push.example"]
