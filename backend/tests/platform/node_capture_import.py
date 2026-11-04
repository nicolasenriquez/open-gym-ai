"""Explicit chain receiver: requires the synthetic capture volume, not default discovery."""

import hashlib
import json
from pathlib import Path

import asyncpg
import pytest
from test_import import command, inspect, prepare
from test_lifecycle import deployment as deployment  # noqa: PLC0414 -- pytest fixture export

ROOT = Path("/run/node-capture")


def fingerprints(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.asyncio
async def test_captured_legacy_documents_media_and_secrets_import_without_opening_access(
    deployment, tmp_path
):
    expected = json.loads((ROOT / "expected.json").read_text())
    capture = ROOT / "capture"
    receipt = json.loads((capture / "capture.json").read_text())
    assert receipt["sourceCutoffAt"] == expected["sourceCutoffAt"]
    assert not receipt["importAuthorized"] and not receipt["operationalAcceptance"]
    before = fingerprints(ROOT)
    for file in receipt["files"]:
        assert before["capture/" + file["path"]] == file["sha256"]
        original = (
            file["path"].replace("data/", "source/", 1)
            if file["path"].startswith("data/")
            else file["path"]
        )
        assert before[original] == file["sha256"]
    observer, environment = deployment
    await prepare(observer, environment)
    code, result = await command(tmp_path, environment, source=capture / "data")
    assert (code, result["code"]) == (0, "IMPORT_OK"), result
    destination = tmp_path / "targets/new-a"
    completion = json.loads((destination / "import.json").read_text())
    assert completion["access"] == "quarantined"
    data_hashes = fingerprints(capture / "data")
    assert (
        completion["source_sha256"]
        == hashlib.sha256(json.dumps(data_hashes, sort_keys=True).encode()).hexdigest()
    )
    observer = await inspect()
    try:
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 2
        for user in expected["users"]:
            assert (
                await observer.fetchval(
                    "SELECT display_name FROM identity.users WHERE id=$1", user["id"]
                )
                == user["name"]
            )
            document = json.loads(
                await observer.fetchval(
                    "SELECT document FROM training.documents WHERE owner_id=$1",
                    user["id"],
                )
            )
            original = capture / "data" / f"state-{user['id']}.json"
            assert document == json.loads(original.read_text())
            assert document["workouts"][0]["id"] == user["workout"]
            assert document["_rev"] == user["rev"]
            source_user = next(
                entry
                for entry in json.loads((capture / "data/db.json").read_text())["users"]
                if entry["id"] == user["id"]
            )
            assert (
                await observer.fetchval(
                    "SELECT scrypt_hash FROM identity.password_credentials WHERE owner_id=$1",
                    user["id"],
                )
                == source_user["pw"]["h"]
            )
        owner = expected["users"][0]["id"]
        media = destination / "data/uploads" / owner / f"{expected['hash']}.jpg"
        assert media.read_bytes() == bytes.fromhex(expected["mediaHex"])
        for name in ("session-secret", "coach-secret"):
            assert (destination / name).read_text() == "c" * 64
        pending = json.loads((capture / "client-export/pending.json").read_text())
        assert pending["active"]["id"] == "local-active" and pending["dirty"]
        assert (
            capture / "protected-access/token"
        ).read_text() == "SYNTHETIC_DEFERRED_TOKEN"
        assert not (destination / "protected-access").exists()
        assert not (destination / "client-export").exists()
        assert not await observer.fetchval(
            "SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await asyncpg.connect(
                host="platform-db",
                database="opengym_dev",
                user="opengym_api_runtime",
                password="synthetic-lifecycle-runtime-password-only",
                ssl=False,
                timeout=5,
            )
        target_before = fingerprints(destination)
        documents_before = await observer.fetch(
            "SELECT owner_id,document FROM training.documents ORDER BY owner_id"
        )
        retry, blocked = await command(tmp_path, environment, source=capture / "data")
        assert (retry, blocked["code"]) == (1, "IMPORT_BLOCKED")
        assert fingerprints(destination) == target_before
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 2
        assert (
            await observer.fetch(
                "SELECT owner_id,document FROM training.documents ORDER BY owner_id"
            )
            == documents_before
        )
    finally:
        await observer.close()
    assert fingerprints(ROOT) == before


@pytest.mark.asyncio
async def test_unrepresentable_captured_bytes_leave_source_and_new_target_intact(
    deployment, tmp_path
):
    before = fingerprints(ROOT)
    observer, environment = deployment
    await prepare(observer, environment)
    code, result = await command(
        tmp_path, environment, source=ROOT / "invalid-capture/data"
    )
    assert (code, result["code"]) == (1, "IMPORT_BLOCKED")
    assert not (tmp_path / "targets/new-a").exists()
    observer = await inspect()
    try:
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0
        assert await observer.fetchval("SELECT count(*) FROM training.documents") == 0
        for sequence in (
            "audit.events_id_seq",
            "coach.history_events_event_id_seq",
            "coach.instance_results_event_id_seq",
        ):
            assert tuple(
                await observer.fetchrow(f"SELECT last_value,is_called FROM {sequence}")
            ) == (1, False)
    finally:
        await observer.close()
    assert fingerprints(ROOT) == before
