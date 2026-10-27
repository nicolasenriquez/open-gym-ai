"""Private media through real HTTP, restricted PostgreSQL and owned files."""

import asyncio
import hashlib
import json
import os
import time

import pytest
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export
from test_lifecycle import server


@pytest.mark.asyncio
async def test_missing_reports_only_own_intact_files_and_usage(identities, tmp_path):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "MEDIA_MIN_FREE_MB": "0",
        "DATA_DIR": str(tmp_path / "data"),
        "MEDIA_QUOTA_MB": "1",
    }
    data = b"\xff\xd8\xffmissing-photo"
    digest = hashlib.sha256(data).hexdigest()
    headers = {"Authorization": f"Bearer {A}"}
    async with server(environment) as client:
        assert (
            await client.put(
                f"/api/v1/media/{digest}",
                headers=headers | {"Content-Type": "image/jpeg"},
                content=data,
            )
        ).status_code == 201
        response = await client.post(
            "/api/v1/media/missing",
            headers=headers,
            json={"hashes": [digest, "0" * 64, "0" * 64]},
        )
        assert response.status_code == 200
        assert response.json() == {
            "missing": ["0" * 64],
            "usage": {"bytes": len(data), "count": 1, "quotaBytes": 1048576},
        }
        foreign = await client.post(
            "/api/v1/media/missing",
            headers={"Authorization": f"Bearer {B}"},
            json={"hashes": [digest]},
        )
        assert foreign.json() == {
            "missing": [digest],
            "usage": {"bytes": 0, "count": 0, "quotaBytes": 1048576},
        }
        for body in (
            {},
            {"hashes": None},
            {"hashes": [1]},
            {"hashes": ["A" * 64]},
            {"hashes": [digest] * 1001},
        ):
            invalid = await client.post(
                "/api/v1/media/missing", headers=headers, json=body
            )
            assert invalid.status_code == 400
        for raw in (b"null", b"[]", b"{", b'{"hashes": [], "extra": NaN}'):
            assert (
                await client.post("/api/v1/media/missing", headers=headers, content=raw)
            ).status_code == 400
        assert (
            await client.post("/api/v1/media/missing", json={"hashes": []})
        ).status_code == 401
        assert (
            await client.post(
                "/api/v1/media/missing",
                headers={"Cookie": f"gymsid={A}", "Origin": "https://foreign.test"},
                json={"hashes": []},
            )
        ).status_code == 403
        stored = tmp_path / "data/uploads/A" / f"{digest}.jpg"
        stored.write_bytes(b"truncated")
        assert (
            await client.post(
                "/api/v1/media/missing", headers=headers, json={"hashes": [digest]}
            )
        ).json()["missing"] == [digest]
        assert (
            await client.put(
                f"/api/v1/media/{digest}",
                headers=headers | {"Content-Type": "image/jpeg"},
                content=data,
            )
        ).status_code == 201
        stored.write_bytes(b"")
        assert (
            await client.post(
                "/api/v1/media/missing", headers=headers, json={"hashes": [digest]}
            )
        ).json()["missing"] == [digest]

    async with server(environment | {"MEDIA_UPLOADS": "off"}) as client:
        assert (
            await client.post(
                "/api/v1/media/missing", headers=headers, json={"hashes": []}
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_quota_reserves_streams_and_releases_every_refusal(identities, tmp_path):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "MEDIA_MIN_FREE_MB": "0",
        "DATA_DIR": str(tmp_path / "data"),
        "MEDIA_QUOTA_MB": "0.001",
        "MEDIA_IMAGE_MAX_MB": "0.001",
    }
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"}
    data = b"\xff\xd8\xff" + b"a" * 697
    digest = hashlib.sha256(data).hexdigest()
    async with server(environment) as client:
        refused = await client.put(
            "/api/v1/media/" + "0" * 64, headers=headers, content=data
        )
        assert refused.status_code == 400 and refused.json()["code"] == "hash-mismatch"
        assert (
            await client.put(f"/api/v1/media/{digest}", headers=headers, content=data)
        ).status_code == 201
        other = b"\xff\xd8\xff" + b"b" * 697
        rejected = await client.put(
            "/api/v1/media/" + hashlib.sha256(other).hexdigest(),
            headers=headers,
            content=other,
        )
        assert rejected.status_code == 413 and rejected.json() == {
            "error": "your space for photos and videos is full",
            "code": "media-quota",
            "usedMB": 0,
            "quotaMB": 0.001,
        }
        assert (
            await client.put(f"/api/v1/media/{digest}", headers=headers, content=data)
        ).status_code == 200
        # Another account has its own quota; its bytes remain an independent sentinel.
        assert (
            await client.put(
                "/api/v1/media/" + hashlib.sha256(other).hexdigest(),
                headers=headers | {"Authorization": f"Bearer {B}"},
                content=other,
            )
        ).status_code == 201
    # Fresh store: an unknown length reserves the full kind cap before reading.
    environment["DATA_DIR"] = str(tmp_path / "concurrent")
    resume = asyncio.Event()

    async def body():
        yield data[:3]
        await resume.wait()
        yield data[3:]

    async with server(environment) as client:
        pending = asyncio.create_task(
            client.put(
                f"/api/v1/media/{digest}", headers=headers, content=body(), timeout=6
            )
        )
        try:
            async with asyncio.timeout(3):
                while not list((tmp_path / "concurrent/uploads/A/.tmp").glob("*")):
                    await asyncio.sleep(0.02)
            denied = await client.put(
                "/api/v1/media/" + hashlib.sha256(other).hexdigest(),
                headers=headers,
                content=other,
            )
            assert denied.status_code == 413 and denied.json()["code"] == "media-quota"
        finally:
            resume.set()
        assert (await pending).status_code == 201


@pytest.mark.asyncio
async def test_upload_admission_budgets_disk_and_disconnect_release(
    identities, tmp_path
):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "MEDIA_MIN_FREE_MB": "0",
        "DATA_DIR": str(tmp_path / "data"),
        "MEDIA_QUOTA_MB": "4",
    }
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"}
    data = b"\xff\xd8\xffadmission"
    digest = hashlib.sha256(data).hexdigest()
    path = f"/api/v1/media/{digest}"
    async with server(environment) as client:
        writers = []
        try:
            for _ in range(2):
                _, writer = await asyncio.open_connection(
                    "127.0.0.1", client.base_url.port
                )
                writers.append(writer)
                writer.write(
                    (
                        f"PUT {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {A}\r\nContent-Type: image/jpeg\r\nTransfer-Encoding: chunked\r\n\r\n3\r\n"
                    ).encode()
                    + b"\xff\xd8\xff\r\n"
                )
                await writer.drain()
            async with asyncio.timeout(3):
                while len(list((tmp_path / "data/uploads/A/.tmp").glob("*"))) != 2:
                    await asyncio.sleep(0.02)
            response = await client.put(path, headers=headers, content=data)
            assert response.status_code == 429 and response.json()["code"] == "busy"
            assert (
                response.json()["retryAfter"] == 5
                and response.headers["retry-after"] == "5"
            )
        finally:
            for writer in writers:
                writer.close()
                await writer.wait_closed()
        async with asyncio.timeout(3):
            while list((tmp_path / "data/uploads/A/.tmp").glob("*")):
                await asyncio.sleep(0.02)
        assert (
            await client.put(path, headers=headers, content=data)
        ).status_code == 201
    async with server(environment | {"MEDIA_UPLOADS_PER_HOUR": "1"}) as client:
        assert (
            await client.put(path, headers=headers, content=data)
        ).status_code == 200

        response = await client.put(path, headers=headers, content=data)
        assert response.status_code == 429 and response.json()["code"] == "locked"
        assert 3590 <= response.json()["retryAfter"] <= 3600
        assert int(response.headers["retry-after"]) == response.json()["retryAfter"]
        assert (
            await client.put(
                path, headers=headers | {"Authorization": f"Bearer {B}"}, content=data
            )
        ).status_code == 201
    # The floor is real statvfs, set above the entire disposable filesystem.
    async with server(environment | {"MEDIA_MIN_FREE_MB": "1000000000"}) as client:
        response = await client.put(
            "/api/v1/media/" + hashlib.sha256(data + b"new").hexdigest(),
            headers=headers,
            content=data + b"new",
        )
        assert response.status_code == 507 and response.json()["code"] == "storage-full"
        assert (
            await client.put(path, headers=headers, content=data)
        ).status_code == 200


@pytest.mark.asyncio
async def test_boot_and_hourly_cleanup_touch_only_temporary_files(identities, tmp_path):
    _, environment = identities
    root = tmp_path / "data/uploads"
    temporary = root / "A/.tmp"
    temporary.mkdir(parents=True)
    (temporary / "crashed").write_bytes(b"partial")
    sentinel = root / "B" / ("b" * 64 + ".jpg")
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"foreign-private-sentinel")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"protected")
    (root / "linked-owner").symlink_to(outside, target_is_directory=True)
    (temporary / "linked-file").symlink_to(outside / "keep")
    # Approved time seam: shorten the hourly maintenance wait, not file ages.
    (tmp_path / "media_maintenance.py").write_text("""import asyncio
from opengym_platform.application import create_app
original = asyncio.sleep
async def sleep(seconds, *args, **kwargs):
    return await original(0.05 if seconds == 3600 else seconds, *args, **kwargs)
asyncio.sleep = sleep
""")
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
        "PYTHONPATH": str(tmp_path) + os.pathsep + environment["PYTHONPATH"],
    }
    async with server(environment, factory="media_maintenance:create_app"):
        assert not (temporary / "crashed").exists()
        (temporary / "old").write_bytes(b"old")
        os.utime(temporary / "old", (time.time() - 7200,) * 2)
        (temporary / "fresh").write_bytes(b"fresh")
        marks_tmp = temporary.parent / ".gc.json.tmp"
        marks_tmp.write_text("{}")
        os.utime(marks_tmp, (time.time() - 7200,) * 2)
        async with asyncio.timeout(3):
            while (temporary / "old").exists() or marks_tmp.exists():
                await asyncio.sleep(0.02)
        assert (temporary / "fresh").read_bytes() == b"fresh"
        assert sentinel.read_bytes() == b"foreign-private-sentinel"
        assert (outside / "keep").read_bytes() == b"protected"
        assert (temporary / "linked-file").is_symlink()


@pytest.mark.asyncio
async def test_quota_pressure_requires_readable_own_references_and_marks(
    identities, tmp_path
):
    observer, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "MEDIA_MIN_FREE_MB": "0",
        "DATA_DIR": str(tmp_path / "data"),
        "MEDIA_QUOTA_MB": str(3000 / 1048576),
    }
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"}
    old, kept, new = [
        b"\xff\xd8\xff" + bytes([n]) * (size - 3)
        for n, size in ((1, 1000), (2, 500), (3, 2000))
    ]
    old_hash, kept_hash, new_hash = [
        hashlib.sha256(data).hexdigest() for data in (old, kept, new)
    ]
    directory = tmp_path / "data/uploads/A"
    marks = directory / ".gc.json"
    async with server(environment) as client:
        for data, digest in ((old, old_hash), (kept, kept_hash)):
            assert (
                await client.put(
                    f"/api/v1/media/{digest}", headers=headers, content=data
                )
            ).status_code == 201
        assert (
            await client.put(
                f"/api/v1/media/{old_hash}",
                headers=headers | {"Authorization": f"Bearer {B}"},
                content=old,
            )
        ).status_code == 201
        assert (
            await client.put(
                "/api/v1/data",
                headers=headers,
                json={
                    "stamped": True,
                    "state": {
                        "customEx": [{"id": "kept", "media": {"hash": kept_hash}}]
                    },
                },
            )
        ).status_code == 200
        path = f"/api/v1/media/{new_hash}"
        # Corrupt marks restart grace rather than converting absence into deletion.
        marks.write_text("not-json")
        assert (await client.put(path, headers=headers, content=new)).status_code == 413
        assert (directory / f"{old_hash}.jpg").read_bytes() == old
        aged = json.dumps({old_hash: int((time.time() - 7200) * 1000), kept_hash: 0})
        marks.write_text(aged)
        await observer.execute(
            "REVOKE SELECT ON training.documents FROM opengym_api_runtime"
        )
        assert (await client.put(path, headers=headers, content=new)).status_code == 500
        assert (directory / f"{old_hash}.jpg").read_bytes() == old
        await observer.execute(
            "GRANT SELECT ON training.documents TO opengym_api_runtime"
        )
        directory.chmod(0o500)
        try:
            assert (
                await client.put(path, headers=headers, content=new)
            ).status_code == 413
        finally:
            directory.chmod(0o700)
        assert not (directory / f"{new_hash}.jpg").exists()
        assert (directory / f"{old_hash}.jpg").read_bytes() == old
        marks.write_text(aged)
        assert (await client.put(path, headers=headers, content=new)).status_code == 201
        assert not (directory / f"{old_hash}.jpg").exists()
        assert (directory / f"{kept_hash}.jpg").read_bytes() == kept
        assert (tmp_path / "data/uploads/B" / f"{old_hash}.jpg").read_bytes() == old
