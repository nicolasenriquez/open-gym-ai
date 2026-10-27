"""Private media through real HTTP, restricted PostgreSQL and owned files."""

import asyncio
import hashlib
import json
import os
import struct

import pytest
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import server


@pytest.mark.asyncio
async def test_upload_download_is_private_and_survives_restart(identities, tmp_path):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    data = b"\xff\xd8\xffsynthetic-private-photo"
    digest = hashlib.sha256(data).hexdigest()
    path = f"/api/v1/media/{digest}"
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/gif"}
    async with server(environment) as client:
        response = await client.put(path, headers=headers, content=data)
        assert response.status_code == 201
        assert response.json() == {
            "ok": True,
            "hash": digest,
            "mime": "image/jpeg",
            "size": len(data),
            "existed": False,
        }
        assert (await client.put(path, headers=headers, content=data)).json() == {
            **response.json(),
            "existed": True,
        }
        missing = await client.get(
            path, headers={"Authorization": f"Bearer {B}", "X-Owner-Id": "A"}
        )
        assert missing.status_code == 404
        assert missing.json() == {"error": "no such file", "code": "media-missing"}
        assert (await client.get(path)).status_code == 401
    async with server(environment) as client:
        response = await client.get(
            path, headers=headers | {"Range": "bytes=0-1", "If-None-Match": "*"}
        )
        assert response.status_code == 200 and response.content == data
        for key, value in {
            "content-type": "image/jpeg",
            "content-length": str(len(data)),
            "cache-control": "private, no-store",
            "x-content-type-options": "nosniff",
            "content-security-policy": "default-src 'none'; sandbox",
            "cross-origin-resource-policy": "same-origin",
            "content-disposition": f'inline; filename="{digest}.jpg"',
            "x-robots-tag": "noindex",
            "access-control-expose-headers": "Content-Length",
        }.items():
            assert response.headers[key] == value
        assert (
            "etag" not in response.headers and "accept-ranges" not in response.headers
        )
    stored = tmp_path / "data" / "uploads" / "A" / f"{digest}.jpg"
    assert stored.read_bytes() == data
    assert stored.stat().st_mode & 0o777 == 0o600
    assert stored.parent.stat().st_mode & 0o777 == 0o700


def box(kind, body):
    return struct.pack(">I", len(body) + 8) + kind + body


def movie(brand=b"isom", *, seconds=5, wide=False, fragmented=False):
    # Independent ISO-BMFF layout: 1000 ticks/s; version 1 uses 64-bit duration.
    header = (
        (b"\x01" + bytes(19) + struct.pack(">IQ", 1000, seconds * 1000))
        if wide
        else (bytes(12) + struct.pack(">II", 1000, 0 if fragmented else seconds * 1000))
    )
    children = box(b"mvhd", header)
    if fragmented:
        children += box(
            b"mvex", box(b"mehd", bytes(4) + struct.pack(">I", seconds * 1000))
        )
    return (
        box(b"ftyp", brand + bytes(4))
        + box(b"mdat", b"synthetic")
        + box(b"moov", children)
    )


@pytest.mark.asyncio
async def test_supported_bytes_and_refusals_match_independent_contract(
    identities, tmp_path
):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
        "MEDIA_IMAGE_MAX_MB": "0.001",
    }
    headers = {"Authorization": f"Bearer {A}"}
    cases = [
        (b"\x89PNG\r\n\x1a\nphoto", "image/jpeg", "image/png", "png"),
        (b"GIF87aphoto", "image/png", "image/gif", "gif"),
        (b"GIF89aphoto", "image/gif", "image/gif", "gif"),
        (b"RIFF\x00\x00\x00\x00WEBPphoto", "image/webp", "image/webp", "webp"),
        (movie(), "video/quicktime", "video/mp4", "mp4"),
        (movie(b"qt  ", wide=True), "video/mp4", "video/quicktime", "mov"),
        (movie(seconds=61, fragmented=True), "video/mp4", "video/mp4", "mp4"),
        (movie(seconds=0), "video/mp4", "video/mp4", "mp4"),
        (
            b"\x1a\x45\xdf\xa3\x87\x42\x82\x84webmvideo",
            "video/webm",
            "video/webm",
            "webm",
        ),
    ]
    async with server(environment) as client:
        for data, declared, mime, extension in cases:
            digest = hashlib.sha256(data).hexdigest()
            response = await client.put(
                f"/api/v1/media/{digest}",
                headers=headers | {"Content-Type": declared},
                content=data,
            )
            assert response.status_code == 201, (mime, response.text)
            assert response.json() == {
                "ok": True,
                "hash": digest,
                "mime": mime,
                "size": len(data),
                "existed": False,
            }
            downloaded = await client.get(f"/api/v1/media/{digest}", headers=headers)
            assert (
                downloaded.content == data
                and downloaded.headers["content-type"] == mime
            )
            assert (
                tmp_path / "data/uploads/A" / f"{digest}.{extension}"
            ).read_bytes() == data
        for data, declared, status, code in [
            (b"<svg onload='x'/>", "image/png", 415, "media-type"),
            (b"\xff\xd8\xffphoto", "text/html", 415, "media-type"),
            (movie() + b"category-mismatch", "image/jpeg", 415, "media-type"),
            (b"\xff\xd8\xffphoto", "video/mp4", 415, "media-type"),
            (box(b"ftyp", b"heic"), "video/mp4", 415, "media-type"),
            (box(b"ftyp", b"isom"), "video/mp4", 415, "media-invalid"),
            (
                box(b"ftyp", b"isom") + box(b"moov", box(b"mvhd", bytes(20))),
                "video/mp4",
                415,
                "media-invalid",
            ),
            (
                box(b"ftyp", b"isom") + struct.pack(">I", 1000) + b"moov",
                "video/mp4",
                415,
                "media-invalid",
            ),
            (
                box(b"ftyp", b"isom")
                + box(b"free", b"") * 10001
                + box(
                    b"moov", box(b"mvhd", bytes(12) + struct.pack(">II", 1000, 5000))
                ),
                "video/mp4",
                415,
                "media-invalid",
            ),
            (
                box(b"ftyp", b"isom")
                + box(
                    b"moov",
                    box(b"mvhd", bytes(12) + struct.pack(">II", 1000, 5000))
                    + box(b"free", bytes(8 * 1024 * 1024)),
                ),
                "video/mp4",
                415,
                "media-invalid",
            ),
            (
                b"\x1a\x45\xdf\xa3\x8b\x42\x82\x88matroska",
                "video/webm",
                415,
                "media-type",
            ),
            (b"\x1a\x45\xdf\xa3\x00", "video/webm", 415, "media-type"),
            (movie(seconds=62), "video/mp4", 413, "media-too-long"),
            (b"\xff\xd8\xff" + b"x" * 1100, "image/gif", 413, "media-too-large"),
        ]:
            digest = hashlib.sha256(data).hexdigest()
            response = await client.put(
                f"/api/v1/media/{digest}",
                headers=headers | {"Content-Type": declared},
                content=data,
            )
            assert response.status_code == status and response.json()["code"] == code
            assert (
                await client.get(f"/api/v1/media/{digest}", headers=headers)
            ).status_code == 404
        wrong = await client.put(
            "/api/v1/media/" + "0" * 64,
            headers=headers | {"Content-Type": "image/jpeg"},
            content=b"\xff\xd8\xffphoto",
        )
        assert wrong.status_code == 400 and wrong.json()["code"] == "hash-mismatch"
    assert list((tmp_path / "data/uploads/A/.tmp").iterdir()) == []


@pytest.mark.asyncio
async def test_training_references_and_postcommit_marks_are_owner_scoped(
    identities, tmp_path
):
    observer, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    data = b"GIF89areference-photo"
    digest = hashlib.sha256(data).hexdigest()
    headers = {"Authorization": f"Bearer {A}"}
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('B',$1::jsonb)",
        json.dumps({"customEx": [{"media": {"hash": digest}}]}),
    )
    async with server(environment) as client:
        assert (
            await client.put(
                f"/api/v1/media/{digest}",
                content=data,
                headers=headers | {"Content-Type": "image/gif"},
            )
        ).status_code == 201
        marks = tmp_path / "data/uploads/A/.gc.json"
        assert json.loads(marks.read_text())[digest] > 0
        for state in (
            {"customEx": [{"media": {"poster": {"hash": digest}}}]},
            {"workouts": [{"id": "w", "media": [{"hash": digest}]}]},
            {"workouts": [{"id": "w", "media": [{"poster": {"hash": digest}}]}]},
        ):
            reply = await client.put(
                "/api/v1/data", headers=headers, json={"stamped": True, "state": state}
            )
            assert reply.status_code == 200
            assert digest not in json.loads(marks.read_text())
            reply = await client.put(
                "/api/v1/data",
                headers=headers,
                json={
                    "stamped": True,
                    "state": {"workouts": [], "active": {"media": [{"hash": digest}]}},
                },
            )
            assert reply.status_code == 200 and digest in json.loads(marks.read_text())
        # A public Training read failure must not masquerade as no references.
        await observer.execute(
            "REVOKE SELECT ON training.documents FROM opengym_api_runtime"
        )
        other = b"GIF89adatabase-unavailable"
        other_hash = hashlib.sha256(other).hexdigest()
        reply = await client.put(
            f"/api/v1/media/{other_hash}",
            content=other,
            headers=headers | {"Content-Type": "image/gif"},
        )
        assert reply.status_code == 500 and reply.json() == {"error": "server error"}
        assert not (tmp_path / "data/uploads/A" / f"{other_hash}.gif").exists()
        assert (
            await client.get(f"/api/v1/media/{digest}", headers=headers)
        ).content == data


@pytest.mark.asyncio
async def test_revocation_during_stream_never_publishes_or_holds_database_lease(
    identities, tmp_path
):
    observer, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    data = b"GIF89arevoked-during-transfer"
    digest = hashlib.sha256(data).hexdigest()
    resume = asyncio.Event()

    async def body():
        yield data[:8]
        await resume.wait()
        yield data[8:]

    async with server(environment) as client:
        request = asyncio.create_task(
            client.put(
                f"/api/v1/media/{digest}",
                headers={"Authorization": f"Bearer {A}", "Content-Type": "image/gif"},
                content=body(),
                timeout=6,
            )
        )
        try:
            async with asyncio.timeout(3):
                while not list((tmp_path / "data/uploads/A/.tmp").glob("*")):
                    await asyncio.sleep(0.02)
            assert (
                await observer.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND (xact_start IS NOT NULL OR state <> 'idle')"
                )
                == 0
            )
            await observer.execute(
                "UPDATE identity.users SET session_version=1 WHERE id='A'"
            )
        finally:
            resume.set()
        response = await request
        assert response.status_code == 401 and response.json() == {
            "error": "not signed in"
        }
    assert not (tmp_path / "data/uploads/A" / f"{digest}.gif").exists()
    assert list((tmp_path / "data/uploads/A/.tmp").iterdir()) == []


@pytest.mark.asyncio
async def test_existing_file_is_vouched_for_without_reading_body_and_damaged_bytes_repair(
    identities, tmp_path
):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    data = b"GIF89aidempotence"
    digest = hashlib.sha256(data).hexdigest()
    path = f"/api/v1/media/{digest}"
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/gif"}
    async with server(environment) as client:
        assert (
            await client.put(path, headers=headers, content=data)
        ).status_code == 201
        response = await client.put(path, headers=headers, content=b"x" * len(data))
        assert response.status_code == 200 and response.json()["existed"] is True
        stored = tmp_path / "data/uploads/A" / f"{digest}.gif"
        stored.write_bytes(b"damaged")
        assert (
            await client.put(path, headers=headers, content=data)
        ).status_code == 201
        assert (await client.get(path, headers=headers)).content == data


@pytest.mark.asyncio
async def test_stream_caps_stall_and_transport_guards(identities, tmp_path):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
        "MEDIA_IMAGE_MAX_MB": "0.001",
    }
    # Approved time boundary: shorten only the upload's 60-second idle deadline.
    (tmp_path / "media_clock.py").write_text("""import asyncio
from opengym_platform.application import create_app
original = asyncio.timeout
asyncio.timeout = lambda seconds: original(0.2 if seconds == 60 else seconds)
""")
    environment["PYTHONPATH"] = str(tmp_path) + os.pathsep + environment["PYTHONPATH"]
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"}
    data = b"\xff\xd8\xff" + bytes(1100)
    path = "/api/v1/media/" + hashlib.sha256(data).hexdigest()

    async def oversized():
        yield data[:100]
        yield data[100:]

    async with server(environment, factory="media_clock:create_app") as client:
        response = await client.put(path, headers=headers, content=oversized())
        assert (
            response.status_code == 413 and response.json()["code"] == "media-too-large"
        )
        # Read while the upload stalls: a client that sends its entire body before
        # reading (HTTPX) cannot observe an early response on a closed connection.
        reader, writer = await asyncio.open_connection(
            "127.0.0.1", client.base_url.port
        )
        try:
            writer.write(
                (
                    f"PUT {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {A}\r\nContent-Type: image/jpeg\r\nTransfer-Encoding: chunked\r\n\r\n3\r\n"
                ).encode()
                + b"\xff\xd8\xff\r\n"
            )
            await writer.drain()
            async with asyncio.timeout(2):
                answer = await reader.readuntil(b"\r\n\r\n")
                assert (
                    answer.startswith(b"HTTP/1.1 408 ")
                    and b"connection: close" in answer.lower()
                )
                length = int(
                    next(
                        line.split(b":")[1]
                        for line in answer.lower().split(b"\r\n")
                        if line.startswith(b"content-length:")
                    )
                )
                assert json.loads(await reader.readexactly(length)) == {
                    "error": "the upload stalled",
                    "code": "timeout",
                }
        finally:
            writer.close()
            await writer.wait_closed()
        response = await client.put(
            path,
            headers={
                "Cookie": f"gymsid={A}",
                "Origin": "https://foreign.test",
                "Content-Type": "image/jpeg",
            },
            content=data,
        )
        assert response.status_code == 403
        assert (await client.get("/api/media/" + "a" * 64)).status_code == 404
        assert (
            await client.get("/api/v1/media/NOT-A-HASH", headers=headers)
        ).status_code == 404
    assert list((tmp_path / "data/uploads/A/.tmp").iterdir()) == []
    async with server(environment | {"MEDIA_UPLOADS": "off"}) as client:
        assert (await client.get(path, headers=headers)).status_code == 404
        assert (
            await client.put(path, headers=headers, content=data)
        ).status_code == 404
