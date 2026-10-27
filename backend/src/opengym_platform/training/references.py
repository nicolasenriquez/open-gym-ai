"""Public Training media projection; caller supplies its authorized transaction."""

import json
import re


def referenced_hashes(document):
    result = set()
    if not isinstance(document, dict):
        return result

    def add(reference):
        if not isinstance(reference, dict):
            return
        for entry in (reference, reference.get("poster")):
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("hash"), str)
                and re.fullmatch(r"[0-9a-f]{64}", entry["hash"])
            ):
                result.add(entry["hash"])

    custom = document.get("customEx")
    for exercise in custom if isinstance(custom, list) else []:
        if isinstance(exercise, dict):
            add(exercise.get("media"))
    workouts = document.get("workouts")
    for workout in workouts if isinstance(workouts, list) else []:
        if isinstance(workout, dict) and isinstance(workout.get("media"), list):
            for reference in workout["media"]:
                add(reference)
    return result


async def media_references(handle, owner):
    context = await handle.fetch(
        "SELECT current_setting('app.owner_id', true) AS owner"
    )
    if context[0]["owner"] != owner:
        raise ValueError("PLATFORM_TRAINING_OWNER_REQUIRED")
    rows = await handle.fetch(
        "SELECT document FROM training.documents WHERE owner_id=$1", owner
    )
    # None distinguishes no document; database failures propagate to the initiator.
    return referenced_hashes(json.loads(rows[0]["document"])) if rows else None
