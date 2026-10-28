"""Owned GC through HTTP, real restricted PostgreSQL and independent bytes."""

import asyncio
import hashlib
import json
import os
import shutil
import time
from contextlib import suppress
from pathlib import Path

import asyncpg
import pytest
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server


@pytest.mark.asyncio
async def test_internal_gc_identity_confirms_only_existing_id_and_holds_account_lock(
    identities,
):
    observer, environment = identities
    connection = await asyncpg.connect(
        host="db",
        user="opengym_api_runtime",
        database="opengym_dev",
        password=Path(environment["PLATFORM_RUNTIME_PASSWORD_FILE"])
        .read_text()
        .rstrip("\n"),
        ssl=False,
        timeout=5,
        command_timeout=2,
    )
    try:
        async with connection.transaction():
            rows = await connection.fetch(
                "SELECT * FROM identity.lock_media_owner($1)", "A"
            )
            assert [dict(row) for row in rows] == [{"id": "A"}]
            assert (
                await connection.fetch(
                    "SELECT * FROM identity.lock_media_owner($1)", "missing"
                )
                == []
            )
            assert await connection.fetch("SELECT id FROM identity.users") == []
            async with observer.transaction():
                with pytest.raises(asyncpg.LockNotAvailableError):
                    await observer.execute(
                        "SELECT id FROM identity.users WHERE id='A' FOR UPDATE NOWAIT"
                    )
        assert await connection.fetch("SELECT id FROM identity.users") == []
        assert await observer.fetchval(
            "SELECT NOT rolcanlogin FROM pg_roles WHERE rolname='opengym_identity_executor'"
        )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_explicit_sweep_requires_own_readable_training_and_preserves_foreign_bytes(
    identities, tmp_path
):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "MEDIA_MIN_FREE_MB": "0",
        "DATA_DIR": str(tmp_path / "data"),
    }
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"}
    kept, old = b"\xff\xd8\xffok", b"\xff\xd8\xffcollect"
    kept_hash, old_hash = (hashlib.sha256(data).hexdigest() for data in (kept, old))
    async with server(environment) as client:
        for data, digest in ((kept, kept_hash), (old, old_hash)):
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
        # No Training row is not evidence of an empty profile.
        response = await client.post("/api/v1/media/sweep", headers=headers, json={})
        assert response.status_code == 200
        assert response.json() == {
            "removed": 0,
            "freedBytes": 0,
            "usage": {"bytes": 15, "count": 2, "quotaBytes": 209715200},
        }
        assert (
            await client.put(
                "/api/v1/data",
                headers=headers,
                json={
                    "stamped": True,
                    "state": {
                        "customEx": [
                            {"id": "x", "media": {"poster": {"hash": kept_hash}}}
                        ]
                    },
                },
            )
        ).status_code == 200
        response = await client.post(
            "/api/v1/media/sweep", headers=headers, json={"owner": "B"}
        )
        assert response.json() == {
            "removed": 1,
            "freedBytes": 10,
            "usage": {"bytes": 5, "count": 1, "quotaBytes": 209715200},
        }
        assert (
            await client.get(f"/api/v1/media/{kept_hash}", headers=headers)
        ).content == kept
        assert (
            await client.get(f"/api/v1/media/{old_hash}", headers=headers)
        ).status_code == 404
        assert (tmp_path / "data/uploads/B" / f"{old_hash}.jpg").read_bytes() == old
        assert old_hash not in json.loads(
            (tmp_path / "data/uploads/A/.gc.json").read_text()
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "broken",
    ['{"torn', "[" * 2000 + "0" + "]" * 2000, '{"irrelevant":' + "9" * 1000 + "}"],
    ids=["torn", "deep", "large-integer"],
)
async def test_periodic_gc_restarts_corrupt_marks_and_keeps_references_unknown_owners(
    identities, tmp_path, broken
):
    observer, environment = identities
    root = tmp_path / "data/uploads"
    hashes = {}
    for name in ("old", "fresh", "kept"):
        data = b"\xff\xd8\xff" + name.encode()
        digest = hashlib.sha256(data).hexdigest()
        hashes[name] = digest
        for owner in ("A", "B", "orphan"):
            directory = root / owner
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{digest}.jpg").write_bytes(data)
            (directory / ".gc.json").write_text(json.dumps({digest: 0}))
    marks = root / "A/.gc.json"
    marks.write_text(broken)
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(
            {"_rev": 1, "customEx": [{"media": {"poster": {"hash": hashes["kept"]}}}]}
        ),
    )
    (tmp_path / "gc_clock.py").write_text("""import asyncio
from opengym_platform.application import create_app
original = asyncio.sleep
async def sleep(seconds, *args, **kwargs):
    return await original(0.05 if seconds in (300, 3600) else seconds, *args, **kwargs)
asyncio.sleep = sleep
""")
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
        "PYTHONPATH": str(tmp_path) + os.pathsep + environment["PYTHONPATH"],
    }
    async with server(environment, factory="gc_clock:create_app"):
        async with asyncio.timeout(3):
            while True:
                try:
                    repaired = json.loads(marks.read_text())
                    if isinstance(repaired, dict) and set(repaired) == {
                        hashes["old"],
                        hashes["fresh"],
                    }:
                        break
                except (ValueError, RecursionError):
                    pass
                await asyncio.sleep(0.02)
        assert hashes["kept"] not in repaired
        assert (root / "A" / f"{hashes['old']}.jpg").read_bytes() == b"\xff\xd8\xffold"
        repaired[hashes["old"]] = int((time.time() - 20 * 86400) * 1000)
        marks.write_text(json.dumps(repaired))
        async with asyncio.timeout(3):
            while (root / "A" / f"{hashes['old']}.jpg").exists():
                await asyncio.sleep(0.02)
        for name in ("fresh", "kept"):
            assert (
                root / "A" / f"{hashes[name]}.jpg"
            ).read_bytes() == b"\xff\xd8\xff" + name.encode()
        for owner in ("B", "orphan"):
            assert (
                root / owner / f"{hashes['old']}.jpg"
            ).read_bytes() == b"\xff\xd8\xffold"


@pytest.mark.asyncio
async def test_explicit_sweep_guards_and_ten_per_hour_budget_are_per_account(
    identities, tmp_path
):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    headers = {"Authorization": f"Bearer {A}"}
    async with server(environment) as client:
        assert (await client.post("/api/v1/media/sweep", json={})).status_code == 401
        assert (
            await client.post(
                "/api/v1/media/sweep",
                headers={"Cookie": f"gymsid={A}", "Origin": "https://foreign.test"},
                json={},
            )
        ).status_code == 403
        assert (
            await client.post("/api/v1/media/sweep", headers=headers, content="null")
        ).status_code == 400
        for _ in range(10):
            assert (
                await client.post("/api/v1/media/sweep", headers=headers, json={})
            ).status_code == 200
        refused = await client.post("/api/v1/media/sweep", headers=headers, json={})
        assert refused.status_code == 429 and refused.json()["code"] == "locked"
        assert 3590 <= refused.json()["retryAfter"] <= 3600
        assert int(refused.headers["retry-after"]) == refused.json()["retryAfter"]
        assert (
            await client.post(
                "/api/v1/media/sweep", headers={"Authorization": f"Bearer {B}"}, json={}
            )
        ).status_code == 200
    async with server(environment | {"MEDIA_UPLOADS": "off"}) as client:
        assert (
            await client.post("/api/v1/media/sweep", headers=headers, json={})
        ).status_code == 404


@pytest.mark.asyncio
async def test_database_and_unreadable_marks_fail_safe_and_periodic_retry_recovers(
    identities, tmp_path
):
    observer, environment = identities
    root = tmp_path / "data/uploads"
    data = b"\xff\xd8\xffpreserve-on-read-error"
    digest = hashlib.sha256(data).hexdigest()
    for owner in ("A", "B"):
        directory = root / owner
        directory.mkdir(parents=True)
        (directory / f"{digest}.jpg").write_bytes(data)
        (directory / ".gc.json").write_text(json.dumps({digest: 0}))
    marks = root / "A/.gc.json"
    marks.chmod(0o000)
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A','{\"_rev\":1,\"workouts\":[]}')"
    )
    await observer.execute(
        "REVOKE SELECT ON training.documents FROM opengym_api_runtime"
    )
    (tmp_path / "error_clock.py").write_text("""import asyncio
from opengym_platform.application import create_app
original = asyncio.sleep
async def sleep(seconds, *args, **kwargs):
    return await original(0.05 if seconds in (300, 3600) else seconds, *args, **kwargs)
asyncio.sleep = sleep
""")
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
        "PYTHONPATH": str(tmp_path) + os.pathsep + environment["PYTHONPATH"],
    }
    async with server(environment, factory="error_clock:create_app") as client:
        response = await client.post(
            "/api/v1/media/sweep", headers={"Authorization": f"Bearer {A}"}, json={}
        )
        assert response.status_code == 500 and response.json() == {
            "error": "server error"
        }
        assert (root / "A" / f"{digest}.jpg").read_bytes() == data
        assert marks.stat().st_mode & 0o777 == 0
        await observer.execute(
            "GRANT SELECT ON training.documents TO opengym_api_runtime"
        )
        async with asyncio.timeout(3):
            while marks.stat().st_mode & 0o777 == 0:
                await asyncio.sleep(0.02)
        assert json.loads(marks.read_text())[digest] > (time.time() - 10) * 1000
        assert (root / "A" / f"{digest}.jpg").read_bytes() == data
        marks.write_text(json.dumps({digest: 0}))
        async with asyncio.timeout(3):
            while (root / "A" / f"{digest}.jpg").exists():
                await asyncio.sleep(0.02)
        assert (root / "B" / f"{digest}.jpg").read_bytes() == data


@pytest.mark.asyncio
async def test_sweep_during_upload_keeps_temporary_and_referenced_bytes(
    identities, tmp_path
):
    _, environment = identities
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "MEDIA_MIN_FREE_MB": "0",
        "DATA_DIR": str(tmp_path / "data"),
    }
    headers = {"Authorization": f"Bearer {A}", "Content-Type": "image/jpeg"}
    data, old = b"\xff\xd8\xffconcurrent-private", b"\xff\xd8\xffold"
    digest, old_hash = (hashlib.sha256(item).hexdigest() for item in (data, old))
    resume = asyncio.Event()

    async def stream():
        yield data[:3]
        await resume.wait()
        yield data[3:]

    async with server(environment) as client:
        for token in (A, B):
            assert (
                await client.put(
                    f"/api/v1/media/{old_hash}",
                    headers=headers | {"Authorization": f"Bearer {token}"},
                    content=old,
                )
            ).status_code == 201
        assert (
            await client.put(
                "/api/v1/data",
                headers=headers,
                json={
                    "stamped": True,
                    "state": {"workouts": [{"id": "w", "media": [{"hash": digest}]}]},
                },
            )
        ).status_code == 200
        upload = asyncio.create_task(
            client.put(
                f"/api/v1/media/{digest}", headers=headers, content=stream(), timeout=6
            )
        )
        try:
            async with asyncio.timeout(3):
                while not list((tmp_path / "data/uploads/A/.tmp").glob("*")):
                    await asyncio.sleep(0.02)
            response = await client.post(
                "/api/v1/media/sweep", headers=headers, json={}
            )
            assert response.status_code == 200 and response.json()["removed"] == 1
            assert len(list((tmp_path / "data/uploads/A/.tmp").glob("*"))) == 1
            assert (tmp_path / "data/uploads/B" / f"{old_hash}.jpg").read_bytes() == old
        finally:
            resume.set()
        assert (await upload).status_code == 201
        assert (
            await client.get(f"/api/v1/media/{digest}", headers=headers)
        ).content == data
        assert not list((tmp_path / "data/uploads/A/.tmp").glob("*"))
        assert digest not in json.loads(
            (tmp_path / "data/uploads/A/.gc.json").read_text()
        )
        assert (
            await client.post("/api/v1/media/sweep", headers=headers, json={})
        ).json()["removed"] == 0


@pytest.mark.asyncio
async def test_revoked_sweep_waiter_cannot_delete_bytes(identities, tmp_path):
    observer, environment = identities
    directory = tmp_path / "data/uploads/A"
    directory.mkdir(parents=True)
    data = b"\xff\xd8\xffrevoked-sweep"
    digest = hashlib.sha256(data).hexdigest()
    (directory / f"{digest}.jpg").write_bytes(data)
    (directory / ".gc.json").write_text(json.dumps({digest: 0}))
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A','{\"_rev\":1,\"workouts\":[]}')"
    )
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    async with server(environment) as client:
        async with observer.transaction():
            await observer.execute(
                "SELECT id FROM identity.users WHERE id='A' FOR UPDATE"
            )
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/media/sweep",
                    headers={"Authorization": f"Bearer {A}"},
                    json={},
                    timeout=6,
                )
            )
            try:
                async with asyncio.timeout(3):
                    while not await observer.fetchval(
                        "SELECT EXISTS(SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND wait_event_type='Lock' AND query LIKE '%identity.lock_actor%')"
                    ):
                        await observer.execute("SELECT pg_stat_clear_snapshot()")
                        await asyncio.sleep(0.02)
                await observer.execute(
                    "UPDATE identity.users SET session_version=1 WHERE id='A'"
                )
            except BaseException:
                pending.cancel()
                with suppress(asyncio.CancelledError):
                    await pending
                raise
        assert (await pending).status_code == 401
        assert (directory / f"{digest}.jpg").read_bytes() == data


@pytest.mark.asyncio
async def test_gc_migrates_previous_head_without_changing_training_or_bytes(
    deployment, tmp_path
):
    observer, environment = deployment
    package = tmp_path / "previous/opengym_platform"
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        package,
        ignore=shutil.ignore_patterns("p002_media_gc.py"),
    )
    await migration({**environment, "PYTHONPATH": str(package.parent)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_links"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'); INSERT INTO training.documents(owner_id,document) VALUES ('A','{\"_rev\":7,\"workouts\":[]}')"
    )
    sentinel = tmp_path / "sentinel.jpg"
    sentinel.write_bytes(b"private-migration-sentinel")
    await migration(environment, "up")
    await migration(environment, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p002_media_gc"
    )
    assert json.loads(
        await observer.fetchval(
            "SELECT document FROM training.documents WHERE owner_id='A'"
        )
    ) == {"_rev": 7, "workouts": []}
    assert sentinel.read_bytes() == b"private-migration-sentinel"
    assert (
        await observer.fetchval(
            "SELECT pg_get_function_result('identity.lock_media_owner(text)'::regprocedure)"
        )
        == "TABLE(id text)"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("link", ["owner", "marks-temporary", "blob"])
async def test_collection_never_follows_links_into_foreign_bytes(
    identities, tmp_path, link
):
    observer, environment = identities
    root = tmp_path / "data/uploads"
    foreign = root / "B"
    foreign.mkdir(parents=True)
    data = b"\xff\xd8\xffforeign-link-sentinel"
    digest = hashlib.sha256(data).hexdigest()
    protected = foreign / f"{digest}.jpg"
    protected.write_bytes(data)
    (foreign / ".gc.json").write_text(json.dumps({digest: 0}))
    own = root / "A"
    if link == "owner":
        own.symlink_to(foreign, target_is_directory=True)
    else:
        own.mkdir()
        if link == "blob":
            (own / f"{digest}.jpg").symlink_to(protected)
        else:
            (own / f"{digest}.jpg").write_bytes(data)
            (own / ".gc.json.tmp").symlink_to(protected)
        (own / ".gc.json").write_text(json.dumps({digest: 0}))
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A','{\"_rev\":1,\"workouts\":[]}')"
    )
    environment = {
        **environment,
        "MEDIA_UPLOADS": "1",
        "DATA_DIR": str(tmp_path / "data"),
    }
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/media/sweep", headers={"Authorization": f"Bearer {A}"}, json={}
        )
        assert protected.read_bytes() == data
        assert response.status_code == (500 if link == "owner" else 200)
        if link != "owner":
            assert response.json()["removed"] == 0
        if link == "blob":
            assert (
                await client.get(
                    f"/api/v1/media/{digest}", headers={"Authorization": f"Bearer {A}"}
                )
            ).status_code == 404
