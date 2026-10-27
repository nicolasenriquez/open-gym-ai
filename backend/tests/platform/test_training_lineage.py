"""Training legacy writes and retries through real HTTP and independent PG observation."""

import asyncio
import json
from contextlib import suppress
from copy import deepcopy
from pathlib import Path

import pytest
from test_identity_session import A, B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server
from test_training_write import external_factory

from opengym_platform.training.stamps import stamp_put

VECTORS = json.loads(
    (Path(__file__).parents[2] / "contracts/training-stamps.v1.json").read_text()
)["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["scenario"])
def test_independent_node_stamp_vectors(vector):
    document = deepcopy(vector["next"])
    options = vector["options"]
    corrected = stamp_put(
        vector["current"],
        document,
        now=options["now"],
        over_read=options.get("overRead", False),
        stamped=options.get("stamped", False),
    )
    assert document == vector["expected"]
    assert corrected == vector["corrected"]


@pytest.mark.asyncio
async def test_legacy_replace_without_base_preserves_reset_and_server_records(
    identities,
):
    observer, environment = identities
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(
            {
                "_rev": 7,
                "resetAt": 50,
                "resetIds": {"workouts": ["gone"]},
                "edited": {"restSec": 40},
                "workouts": [],
            }
        ),
    )
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"state": {"workouts": [], "restSec": 60}},
        )
        assert response.status_code == 200
        saved = (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
        ).json()
        assert saved["state"]["resetAt"] == 50
        assert saved["state"]["resetIds"] == {"workouts": ["gone"]}
        assert saved["state"]["edited"] == {"restSec": 40}
        assert response.json()["rev"] == saved["rev"] == 8
        assert (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={B}"})
        ).json() == {"state": None, "rev": 0}
    assert await observer.fetchval("SELECT revision FROM training.documents") == 8


@pytest.mark.asyncio
async def test_unstamped_removal_is_stamped_and_private_notes_stay_on_server(
    identities,
):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document) VALUES
        ('A','{"_rev":1,"workouts":[{"id":"gone"}],"restSec":60}')""")
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={"baseRev": 1, "state": {"workouts": [], "restSec": 90}},
        )
        assert response.status_code == 200
        saved = (
            await client.get("/api/v1/data", headers={"Cookie": f"gymsid={A}"})
        ).json()
        assert saved["state"]["deleted"]["workouts"]["gone"] > 0
        assert saved["state"]["edited"]["restSec"] > 0
        assert "_prior" not in saved["state"] and "_unstamped" not in saved["state"]
    document = json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    )
    assert document["_prior"]["restSec"] and document["_unstamped"]["fp"] == "none"


@pytest.mark.asyncio
async def test_lost_reply_retry_conflicts_then_merged_save_descends_from_commit(
    identities, tmp_path
):
    observer, environment = identities
    configured, marker = external_factory(tmp_path, environment, timeout=True)
    headers = {"Cookie": f"gymsid={A}"}
    body = {
        "baseRev": 0,
        "stamped": True,
        "state": {"workouts": [{"id": "saved-once"}]},
    }
    async with server(configured, factory="external_mark:create_app") as client:
        pending = asyncio.create_task(
            client.put("/api/v1/data", headers=headers, json=body)
        )
        try:
            async with asyncio.timeout(5):
                while not marker.exists():
                    await asyncio.sleep(0.01)
            assert json.loads(marker.read_text())["revision"] == 1
        finally:
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending
        # The response was never received; retry exactly the request the client retained.
        conflict = await client.put("/api/v1/data", headers=headers, json=body)
        assert conflict.status_code == 409
        saved = conflict.json()["state"]
        assert saved["workouts"] == [{"id": "saved-once"}]
        assert conflict.json()["rev"] == 1
        assert await observer.fetchval("SELECT revision FROM training.documents") == 1
        retry = await client.put(
            "/api/v1/data",
            headers=headers,
            timeout=4,
            json={**body, "baseRev": 1, "baseWid": saved["_wid"], "state": saved},
        )
        assert retry.status_code == 200 and retry.json()["rev"] == 2
        final = (await client.get("/api/v1/data", headers=headers)).json()
        assert final["state"]["_wids"] == [saved["_wid"]]
        assert final["state"]["_wid"] == retry.json()["wid"] != saved["_wid"]
        assert final["state"]["workouts"] == [{"id": "saved-once"}]
        assert (await client.get("/api/v1/data/rev", headers=headers)).json() == {
            "rev": 2,
            "wid": retry.json()["wid"],
        }
    assert (
        json.loads(await observer.fetchval("SELECT document FROM training.documents"))
        == final["state"]
    )


@pytest.mark.asyncio
async def test_restore_same_revision_other_wid_conflicts_and_lineage_is_server_owned(
    identities,
):
    observer, environment = identities
    current = {
        "_rev": 7,
        "_wid": "restored",
        "_wids": [None, 1, *map(str, range(60))],
        "workouts": [],
    }
    await observer.execute(
        "INSERT INTO training.documents(owner_id,document) VALUES ('A',$1::jsonb)",
        json.dumps(current),
    )
    headers = {"Cookie": f"gymsid={A}"}
    async with server(environment) as client:
        conflict = await client.put(
            "/api/v1/data",
            headers=headers,
            json={"baseRev": 7, "baseWid": "lost-branch", "state": {"workouts": []}},
        )
        assert conflict.status_code == 409 and conflict.json()["state"] == current
        assert (
            json.loads(
                await observer.fetchval("SELECT document FROM training.documents")
            )
            == current
        )
        response = await client.put(
            "/api/v1/data",
            headers=headers,
            json={
                "baseRev": 7,
                "baseWid": "restored",
                "stamped": True,
                "state": {
                    "workouts": [],
                    "_rev": 999,
                    "_wid": "forged",
                    "_wids": ["forged"],
                    "_prior": {"forged": []},
                    "_unstamped": {"fp": "forged"},
                },
            },
        )
        assert response.status_code == 200 and response.json()["rev"] == 8
        final = (await client.get("/api/v1/data", headers=headers)).json()["state"]
        assert final["_wids"] == [*map(str, range(11, 60)), "restored"]
        assert final["_wid"] == response.json()["wid"] != "forged"
    document = json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    )
    assert "_prior" not in document and "_unstamped" not in document


@pytest.mark.asyncio
@pytest.mark.parametrize("base", [{}, {"baseRev": None}])
async def test_unconditional_legacy_replace_is_not_stamped_as_over_read(
    identities, base
):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document) VALUES
        ('A','{"_rev":1,"workouts":[{"id":"removed"}],"routines":[],"restSec":60}')""")
    async with server(environment) as client:
        result = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                **base,
                "baseWid": "ignored-without-base",
                "state": {"workouts": [], "routines": [], "restSec": 90},
            },
        )
        assert result.status_code == 200 and result.json()["rev"] == 2
    stored = json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    )
    assert stored["restSec"] == 90 and stored["workouts"] == []
    assert "deleted" not in stored and "edited" not in stored


@pytest.mark.asyncio
async def test_new_reset_drops_old_records_history_and_unknowns(identities):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document) VALUES
        ('A','{"_rev":1,"resetAt":1,"future":null,"edited":{"restSec":2},"deleted":{"workouts":{"old":3}},"_prior":{"restSec":["old"]},"_unstamped":{"fp":"none","ed":{"restSec":2}}}')""")
    async with server(environment) as client:
        result = await client.put(
            "/api/v1/data",
            headers={"Cookie": f"gymsid={A}"},
            json={
                "baseRev": 1,
                "state": {
                    "resetAt": 10,
                    "resetIds": {"workouts": ["old"]},
                    "workouts": [],
                    "routines": [],
                },
            },
        )
        assert result.status_code == 200 and result.json()["rev"] == 2
    stored = json.loads(
        await observer.fetchval("SELECT document FROM training.documents")
    )
    assert stored["resetAt"] == 10 and stored["resetIds"] == {"workouts": ["old"]}
    assert not ({"future", "edited", "deleted", "_prior", "_unstamped"} & stored.keys())


@pytest.mark.asyncio
async def test_correction_can_reach_safe_revision_limit_then_fails_without_writing(
    identities,
):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document) VALUES
        ('A','{"_rev":9007199254740989,"workouts":[],"unknown":null}')""")
    headers = {"Cookie": f"gymsid={A}"}
    async with server(environment) as client:
        response = await client.put(
            "/api/v1/data",
            headers=headers,
            json={"baseRev": 9007199254740989, "state": {"workouts": []}},
        )
        assert (
            response.status_code == 200 and response.json()["rev"] == 9007199254740990
        )
        saved = (await client.get("/api/v1/data", headers=headers)).json()
        assert saved["rev"] == 9007199254740991 and saved["state"]["unknown"] is None
        before = await observer.fetchval("SELECT document FROM training.documents")
        refused = await client.put(
            "/api/v1/data", headers=headers, json={"state": {"workouts": []}}
        )
        assert refused.status_code == 400 and refused.json() == {
            "error": "invalid state"
        }
    assert await observer.fetchval("SELECT document FROM training.documents") == before


@pytest.mark.asyncio
async def test_stale_object_value_is_recognized_after_jsonb_reorders_keys(identities):
    observer, environment = identities
    await observer.execute("""INSERT INTO training.documents(owner_id,document) VALUES
        ('A','{"_rev":1,"queue":{"long":1,"x":2},"edited":{"queue":1},"workouts":[]}')""")
    headers = {"Cookie": f"gymsid={A}"}
    async with server(environment) as client:
        modern = await client.put(
            "/api/v1/data",
            headers=headers,
            json={
                "baseRev": 1,
                "stamped": True,
                "state": {"workouts": [], "queue": {"x": 3}, "edited": {"queue": 10}},
            },
        )
        assert modern.status_code == 200
        stale = await client.put(
            "/api/v1/data",
            headers=headers,
            json={
                "baseRev": 2,
                "state": {
                    "workouts": [],
                    "queue": {"long": 1, "x": 2},
                    "edited": {"queue": 1},
                },
            },
        )
        assert stale.status_code == 200
        saved = (await client.get("/api/v1/data", headers=headers)).json()
        assert saved["state"]["queue"] == {"x": 3}
        assert stale.json()["rev"] == 3 and saved["rev"] == 4
