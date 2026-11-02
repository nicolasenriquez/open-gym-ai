"""Read-only preservation check against independent client receipts and captured bytes."""

import asyncio
import hashlib
import json
import re
from pathlib import Path

import asyncpg

from opengym_platform.backup import read_private
from opengym_platform.core.platform_settings import load_database


async def check(config):
    connection = None
    try:
        settings = read_private(config, max_bytes=16 * 1024 * 1024)
        root = Path("/run/maintenance")
        journal = read_private(root / "journal.json")
        if (
            set(settings) != {"instance_id", "incident", "operation", "writes"}
            or settings["instance_id"] != journal["instance_id"]
            or settings["operation"] != journal["operation"]
            or not re.fullmatch(r"[a-f0-9]{32}", journal["operation"])
            or settings["incident"] != journal["incident"]
            or journal["phase"] != "checking"
            or not (root / "exclusive").is_dir()
            or not isinstance(settings["writes"], list)
            or not 2 <= len(settings["writes"]) <= 100
        ):
            raise ValueError
        target = load_database("backup")
        connection = await asyncpg.connect(
            host=target.host,
            port=5432,
            database=target.database,
            user=target.user,
            password=target.password,
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        owners = set()
        async with connection.transaction(isolation="repeatable_read", readonly=True):
            for receipt in settings["writes"]:
                if set(receipt) != {"owner", "rev", "wid", "state", "media"}:
                    raise ValueError
                owner = receipt["owner"]
                if (
                    not isinstance(owner, str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", owner)
                    or owner in owners
                ):
                    raise ValueError
                owners.add(owner)
                if (
                    type(receipt["rev"]) is not int
                    or not isinstance(receipt["wid"], str)
                    or not receipt["wid"]
                ):
                    raise ValueError
                row = await connection.fetchrow(
                    "SELECT revision, write_id, document - '_prior' - '_unstamped' = $2::jsonb AS matches "
                    "FROM training.documents WHERE owner_id=$1",
                    owner,
                    json.dumps(receipt["state"], allow_nan=False),
                )
                if (
                    not row
                    or row["revision"] != receipt["rev"]
                    or row["write_id"] != receipt["wid"]
                    or not row["matches"]
                ):
                    raise ValueError
                if not isinstance(receipt["media"], list):
                    raise TypeError
                for media in receipt["media"]:
                    if set(media) != {"name", "sha256"} or not re.fullmatch(
                        r"[a-f0-9]{64}\.(?:jpg|png|gif|webp|mp4)", media["name"]
                    ):
                        raise ValueError
                    # Read the coherent, no-follow copy, never an arbitrary host path.
                    path = (
                        root
                        / journal["operation"]
                        / "data"
                        / "uploads"
                        / owner
                        / media["name"]
                    )
                    if path.is_symlink():
                        raise ValueError
                    with path.open("rb") as stream:
                        if (
                            hashlib.file_digest(stream, "sha256").hexdigest()
                            != media["sha256"]
                        ):
                            raise ValueError
    except Exception:  # noqa: BLE001 -- private boundary never echoes receipts or database details
        return 1, {"code": "REPAIR_PRESERVATION_UNPROVEN"}
    finally:
        if connection is not None:
            await connection.close(timeout=5)
    return 0, {"code": "REPAIR_WRITES_PRESERVED", "owners": len(owners)}


def run(config):
    async def bounded():
        try:
            return await asyncio.wait_for(check(config), timeout=12)
        except TimeoutError:
            return 1, {"code": "REPAIR_PRESERVATION_UNPROVEN"}

    return asyncio.run(bounded())
