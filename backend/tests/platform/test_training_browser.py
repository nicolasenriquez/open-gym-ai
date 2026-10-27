"""Synthetic setup/faults and independent PG observation for the real browser proof."""

import asyncio
import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from test_identity_password import PASSWORD
from test_identity_password import accounts as accounts  # noqa: PLC0414
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server


@pytest.mark.asyncio
async def test_real_frontend_training_browser(accounts, tmp_path):
    observer, environment = accounts
    environment["DEFAULT_LANG"] = "es"
    environment["ORIGIN"] = "http://localhost:8080"
    environment["MEDIA_UPLOADS"] = "1"
    environment["MEDIA_MIN_FREE_MB"] = (
        "0"  # isolated test tmpfs is below the production floor
    )
    environment["DATA_DIR"] = str(tmp_path / "media-data")
    await observer.execute("""INSERT INTO training.documents(owner_id,document)
        VALUES ('B','{"_rev":2,"workouts":[{"id":"foreign-sentinel"}]}')""")
    await observer.execute("""INSERT INTO identity.passkeys VALUES
        ('foreign-browser-sentinel','B',decode('aa','hex'),0,'{}',NULL,NULL,NULL)""")
    done = asyncio.Event()
    result = {}
    loop = asyncio.get_running_loop()

    async with server(environment, host="0.0.0.0", port=3000) as client:

        async def control(path, body):
            if path == "/ready":
                return {"ready": True}
            if path == "/media-fixture":
                # Public routes seed a second-device photo; browser must download
                # and verify it itself, without injecting its store or IndexedDB.
                data = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
                )
                digest = hashlib.sha256(data).hexdigest()
                login = await client.post(
                    "/api/v1/login/password",
                    json={"identifier": "alice", "password": PASSWORD},
                )
                assert login.status_code == 200
                upload = await client.put(
                    f"/api/v1/media/{digest}",
                    content=data,
                    headers={"Content-Type": "image/png"},
                )
                assert upload.status_code == 201
                current = (await client.get("/api/v1/data")).json()
                document = current["state"]
                reference = {
                    "hash": digest,
                    "mime": "image/png",
                    "size": len(data),
                    "width": 1,
                    "height": 1,
                }
                document["workouts"].append(
                    {
                        "id": "private-progress-photo",
                        "d": body["day"],
                        "entries": [],
                        "media": [
                            {
                                **reference,
                                "kind": "image",
                                "at": 100,
                            }
                        ],
                    }
                )
                saved = await client.put(
                    "/api/v1/data",
                    json={
                        "baseRev": current["rev"],
                        "stamped": True,
                        "state": document,
                    },
                )
                assert saved.status_code == 200
                persisted = json.loads(
                    await observer.fetchval(
                        "SELECT document FROM training.documents WHERE owner_id='A'"
                    )
                )
                assert persisted["workouts"][-1]["media"][0]["hash"] == digest
                stored = tmp_path / "media-data/uploads/A" / f"{digest}.png"
                assert stored.read_bytes() == data
                assert digest not in json.loads(
                    (stored.parent / ".gc.json").read_text()
                )
                return {"hash": digest}
            if path == "/media-queue":
                persisted = json.loads(
                    await observer.fetchval(
                        "SELECT document FROM training.documents WHERE owner_id='A'"
                    )
                )
                workout = next(
                    w
                    for w in persisted["workouts"]
                    if w["id"] == "private-progress-photo"
                )
                references = workout.get("media", [])
                hashes = {entry["hash"] for entry in references}
                hashes.update(
                    entry["poster"]["hash"]
                    for entry in references
                    if entry.get("poster")
                )
                files = []
                directory = tmp_path / "media-data/uploads/A"
                for digest in hashes:
                    matches = list(directory.glob(digest + ".*"))
                    if matches:
                        data = matches[0].read_bytes()
                        assert hashlib.sha256(data).hexdigest() == digest
                        files.append({"hash": digest, "size": len(data)})
                return {"references": references, "files": files}
            if path == "/links":
                return {
                    "pending": await observer.fetchval(
                        "SELECT count(*) FROM identity.device_links WHERE owner_id='A'"
                    )
                }
            if path == "/reset-fixture":
                # Independent setup for 2.7; administrative issuance belongs to 6.4.
                async with observer.transaction():
                    await observer.execute("""
                        DELETE FROM identity.password_credentials WHERE owner_id='A';
                        UPDATE identity.login_aliases SET password_name_claim=false,
                            reset_name_until=clock_timestamp()+interval '24 hours' WHERE alias_key='alice';
                        INSERT INTO identity.password_resets VALUES ('A',
                            decode('f9609fb684797772a50289433359af852edd3ee2471fd56adcd44e5d0b5dc7ab','hex'),
                            clock_timestamp()+interval '24 hours','B');
                        UPDATE identity.users SET session_version=session_version+1 WHERE id='A';
                    """)
                return {"ok": True}
            if path == "/reset-state":
                return {
                    "remaining": await observer.fetchval(
                        "SELECT count(*) FROM identity.password_resets"
                    ),
                    "password": await observer.fetchval(
                        "SELECT count(*) FROM identity.password_credentials WHERE owner_id='A'"
                    ),
                    "version": await observer.fetchval(
                        "SELECT session_version FROM identity.users WHERE id='A'"
                    ),
                }
            if path == "/passkeys":
                own = await observer.fetch(
                    "SELECT credential_id,label FROM identity.passkeys WHERE owner_id='A'"
                )
                return {
                    "own": [dict(row) for row in own],
                    "foreign": await observer.fetchval(
                        "SELECT count(*) FROM identity.passkeys WHERE owner_id='B'"
                    ),
                    "sessionVersion": await observer.fetchval(
                        "SELECT session_version FROM identity.users WHERE id='A'"
                    ),
                }
            if path == "/snapshot":
                rows = await observer.fetch(
                    "SELECT owner_id,document FROM training.documents"
                )
                return {row["owner_id"]: json.loads(row["document"]) for row in rows}
            if path == "/revoke":
                await observer.execute(
                    "UPDATE identity.users SET session_version=session_version+1 WHERE id='A'"
                )
                return {"ok": True}
            if path == "/compete":
                login = await client.post(
                    "/api/v1/login/password",
                    json={"identifier": "alice", "password": PASSWORD},
                )
                assert login.status_code == 200
                current = (await client.get("/api/v1/data")).json()
                document = current["state"]
                document["workouts"].append(
                    {
                        "id": body["id"],
                        "d": "2026-10-26",
                        "start": 1,
                        "end": 2,
                        "entries": [],
                    }
                )
                response = await client.put(
                    "/api/v1/data",
                    json={
                        "baseRev": current["rev"],
                        "baseWid": document["_wid"],
                        "stamped": True,
                        "state": document,
                    },
                )
                assert response.status_code == 200
                return {"rev": response.json()["rev"]}
            if path == "/restore":
                revision = await observer.fetchval(
                    "SELECT revision FROM training.documents WHERE owner_id='A'"
                )
                await observer.execute(
                    "UPDATE training.documents SET document=$1::jsonb WHERE owner_id='A'",
                    json.dumps(
                        {
                            "_rev": revision,
                            "_wid": "synthetic-restored-branch",
                            "_wids": [],
                            "workouts": [
                                {
                                    "id": "restored-workout",
                                    "d": "2026-10-25",
                                    "entries": [],
                                }
                            ],
                            "routines": [],
                        }
                    ),
                )
                return {"rev": revision}
            if path == "/done":
                result.update(body)
                done.set()
                return {"ok": True}
            raise AssertionError("Unknown browser fixture operation")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                self.exchange({})

            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                assert 0 <= size <= 4096
                self.exchange(json.loads(self.rfile.read(size)))

            def exchange(self, body):
                response = asyncio.run_coroutine_threadsafe(
                    control(self.path, body), loop
                ).result(10)
                payload = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        fixture = ThreadingHTTPServer(("0.0.0.0", 3001), Handler)
        thread = threading.Thread(target=fixture.serve_forever, daemon=True)
        thread.start()
        try:
            await asyncio.wait_for(done.wait(), 220)
            assert result.get("completed") is True, result.get("stage")
            assert result["cases"] == [
                "passkeys",
                "login",
                "offline",
                "auth",
                "conflicts",
                "lost-reply",
                "restore",
                "reset",
                "links",
                "media",
                "media-queue",
            ]
            assert result["errors"] == 0
            assert (
                await observer.fetchval(
                    "SELECT document->'workouts'->0->>'id' FROM training.documents WHERE owner_id='B'"
                )
                == "foreign-sentinel"
            )
            print(
                "PLATFORM_BROWSER_OK: eleven cases; independent PG/filesystem sentinels preserved"
            )
        finally:
            await asyncio.to_thread(fixture.shutdown)
            fixture.server_close()
            thread.join(timeout=2)
