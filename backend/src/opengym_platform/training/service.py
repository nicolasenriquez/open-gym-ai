"""Training operations own the actor lock, RLS context and commit boundary."""

import asyncio
import json
import logging
import secrets

from opengym_platform.identity.service import note_pull
from opengym_platform.identity.sessions import authorize
from opengym_platform.training.stamps import number, stamp_put


async def admin_projection(handle, session, target, *, detail):
    """Legacy admin projection; explicit actor/target, never target owner context."""
    name = "read_admin_detail" if detail else "read_admin_summary"
    rows = await handle.fetch(
        f"SELECT training.{name}($1,$2,$3,$4) AS view",
        session.owner,
        session.version,
        session.expires_at,
        target,
    )
    return json.loads(rows[0]["view"]) if rows[0]["view"] else None


async def coach_consent(handle):
    """Coach's bounded consent projection, on the caller's locked owner transaction."""
    rows = await handle.fetch("""SELECT document #> '{coach,consent,agreedAt}' IS NOT NULL
        AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""') AS agreed
        FROM training.documents""")
    return bool(rows and rows[0]["agreed"])


async def notification_document(handle):
    """Notification input, within an authorized actor or locked delivery-owner context."""
    rows = await handle.fetch("SELECT document FROM training.documents")
    return json.loads(rows[0]["document"]) if rows else None


async def coach_document(handle):
    """Owner's ephemeral Coach input, within the initiating authorized transaction."""
    rows = await handle.fetch("SELECT document FROM training.documents")
    return json.loads(rows[0]["document"]) if rows else None


async def read(database, session, *, revision_only):
    async with database.transaction() as handle:
        if not await authorize(handle, session):
            return None
        columns = "revision, write_id" if revision_only else "document, revision"
        rows = await handle.fetch(f"SELECT {columns} FROM training.documents")
        if revision_only:
            return {
                "rev": rows[0]["revision"] if rows else 0,
                **(
                    {"wid": rows[0]["write_id"]} if rows and rows[0]["write_id"] else {}
                ),
            }
        document = json.loads(rows[0]["document"]) if rows else None
        if document is not None:
            document.pop("_unstamped", None)
            document.pop("_prior", None)
        result = {"state": document, "rev": rows[0]["revision"] if rows else 0}
    await note_pull(database, session)
    return result


async def write(database, session, body, note_state=None, *, coach=None):
    async with database.transaction() as handle:
        if not await authorize(handle, session):
            return 401, {"error": "not signed in"}
        document = body.get("state")
        if not isinstance(document, (dict, list)) or (
            isinstance(document, dict) and not (document.keys() - {"_rev", "_ts"})
        ):
            return 400, {"error": "state required"}
        if not isinstance(document, dict) or any(
            document.get(key) is not None and not isinstance(document[key], list)
            for key in ("workouts", "routines")
        ):
            return 400, {"error": "invalid state"}
        for key in ("workouts", "routines"):
            if isinstance(document.get(key), list):
                document[key] = [
                    entry for entry in document[key] if isinstance(entry, dict)
                ]
        rows = await handle.fetch("SELECT document, revision FROM training.documents")
        current = json.loads(rows[0]["document"]) if rows else None
        revision = rows[0]["revision"] if rows else 0
        base = body.get("baseRev")
        if base is not None and (
            type(base) not in (int, float)
            or base != revision
            or (
                isinstance(body.get("baseWid"), str)
                and current
                and current.get("_wid")
                and body["baseWid"] != current["_wid"]
            )
        ):
            visible = (
                {
                    key: value
                    for key, value in current.items()
                    if key not in {"_prior", "_unstamped"}
                }
                if current is not None
                else None
            )
            return 409, {"error": "conflict", "rev": revision, "state": visible}
        if revision > 9007199254740989:
            return 400, {"error": "invalid state"}
        document.pop("active", None)
        if current and number(current.get("resetAt")) > number(document.get("resetAt")):
            document["resetAt"] = current["resetAt"]
            if isinstance(current.get("resetIds"), (dict, list)):
                document["resetIds"] = current["resetIds"]
            else:
                document.pop("resetIds", None)
        try:
            corrected = stamp_put(
                current,
                document,
                over_read=base is not None and base == revision,
                stamped=body.get("stamped") is True,
            )
            document["_rev"] = revision + (2 if corrected else 1)
            ancestors = current.get("_wids", []) if current else []
            ancestors = ancestors if isinstance(ancestors, list) else []
            if current and current.get("_wid"):
                ancestors = [*ancestors, current["_wid"]]
            document["_wids"] = [
                value for value in ancestors if isinstance(value, str)
            ][-50:]
            document["_wid"] = secrets.token_hex(8)
            text = json.dumps(document, ensure_ascii=False, allow_nan=False)
            pending = [document]
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    pending.extend(value)
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
                elif isinstance(value, str) and (
                    "\x00" in value
                    or any(0xD800 <= ord(char) <= 0xDFFF for char in value)
                ):
                    return 400, {"error": "invalid state"}
        except (ValueError, RecursionError):
            return 400, {"error": "invalid state"}
        await handle.execute(
            "INSERT INTO training.documents(owner_id, document) VALUES ($1, $2::jsonb) "
            "ON CONFLICT (owner_id) DO UPDATE SET document = EXCLUDED.document",
            session.owner,
            text,
        )
        cancelled_job = (
            await coach.training_changed(handle, session.owner, current, document)
            if coach is not None
            else None
        )
        timestamp = document.get("_ts")
        if (
            timestamp is False
            or timestamp is None
            or timestamp == ""
            or (type(timestamp) in (int, float) and timestamp == 0)
        ):
            timestamp = None
        result = {
            "ok": True,
            "ts": timestamp,
            "rev": revision + 1,
            "wid": document["_wid"],
        }
    if coach is not None:
        coach.cancel(cancelled_job)
    if note_state is not None:
        try:
            async with asyncio.timeout(2):
                await note_state(session.owner, document)
        except Exception:  # noqa: BLE001 -- postcommit bookkeeping cannot change acknowledged business success
            logging.getLogger(__name__).warning("PLATFORM_TRAINING_MEDIA_NOTE_FAILED")
    return 200, result
