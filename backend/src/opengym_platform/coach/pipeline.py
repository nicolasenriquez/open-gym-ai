"""Python owns HTTP coordination; generated assets keep prompt/schema sources singular."""

import json
import re
from datetime import UTC, datetime

from opengym_platform.coach.http import base_url, invoke
from opengym_platform.coach.payload import (
    ASSETS,
    build,
    dumps,
    find_workout,
    plan_hash,
    workout_meta,
)
from opengym_platform.coach.validation import refine_plan, validate


def invalid_constant(value):
    raise ValueError("non-finite JSON")


def extract_json(raw):
    raw = raw.strip()
    candidates = [raw]
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        candidates.append(fenced[1])
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate, parse_constant=invalid_constant)
        except (ValueError, TypeError):
            pass
    return None


class Pipeline:
    def __init__(self, secret, credentials=None):
        self.secret = secret
        self.credentials = credentials

    def available(self, config, owner):
        return (
            bool(base_url(config))
            and bool(config.get("model"))
            and (
                config["provider"] == "compatible"
                or bool(self.key(owner, config["provider"]))
            )
        )

    def key(self, owner, provider):
        return (
            self.credentials(owner, provider) if self.credentials is not None else None
        )

    async def run(self, owner, job, state, config, opts, previous, timeout):
        if (
            job["kind"] == "debrief"
            and find_workout(state, opts.get("workoutId")) is None
        ):
            return {"outcome": "failed", "error": "noworkout"}
        payload = build(
            state, owner, self.secret, job["kind"], opts, previous.get("bundle")
        )
        if len(dumps(payload).encode("utf-16-le")) // 2 > 300000:
            return {"outcome": "failed", "error": "toolarge"}
        prompts = ASSETS["prompts"]
        task = (
            "refine"
            if job["kind"] == "create" and payload.get("refine")
            else job["kind"]
        )
        rules = (
            prompts["create"] + "\n\n---\n\n" + prompts["refine"]
            if task == "refine"
            else prompts[task]
        )
        system = prompts["common"] + "\n\n---\n\n" + rules
        prompt = "## Payload\n\n```json\n" + dumps(payload) + "\n```\n"
        user = prompt
        for attempt in range(2):
            response = await invoke(
                config,
                self.key(owner, config["provider"]),
                user,
                system,
                ASSETS["schemas"][job["kind"]],
                timeout,
            )
            if response.get("error"):
                return {"outcome": "failed", "error": response["error"]}
            data = extract_json(response["text"])
            if job["kind"] == "create":
                data = refine_plan(previous.get("bundle"), data)
            checked = validate(data, job["kind"], payload)
            if checked["ok"]:
                break
            if attempt:
                return {"outcome": "failed", "error": "unusable"}
            repair = (
                prompts["repair"]
                .replace("{{PREVIOUS}}", response["text"][:4000])
                .replace("{{ERRORS}}", "\n".join("- " + e for e in checked["errors"]))
            )
            user = prompt + "\n\n---\n\n" + repair
        if checked.get("nochange"):
            return {"outcome": "nochange", "reading": checked["reading"]}
        now = int(datetime.now(UTC).timestamp() * 1000)
        return {
            "outcome": "ready",
            "pending": {
                "id": job["id"],
                "kind": job["kind"],
                "createdAt": now,
                "expiresAt": now + 14 * 86400000,
                "planHash": plan_hash(state),
                "iteration": previous.get("iteration", 1) + 1
                if opts.get("refine")
                else 1,
                **(
                    {"workout": workout_meta(state, opts.get("workoutId"))}
                    if job["kind"] == "debrief"
                    else {}
                ),
                **checked["result"],
            },
        }
