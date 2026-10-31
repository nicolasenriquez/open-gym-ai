"""Process-local workout heartbeats, with the existing hidden-page grace."""

import math
import re
import time

from opengym_platform.identity.passwords import SPACE, identifier_text


def now_ms():
    return int(time.time() * 1000)


def truthy(value):
    return not (
        value is None
        or value is False
        or value == ""
        or type(value) in (int, float)
        and value == 0
    )


def number(value):
    if isinstance(value, list):
        value = ",".join("" if v is None else str(v) for v in value)
    if value is None:
        return 0.0
    try:
        if isinstance(value, str):
            value = value.strip(SPACE)
            if not value:
                return 0.0
            if re.fullmatch(r"0(?:[xX][0-9a-fA-F]+|[oO][0-7]+|[bB][01]+)", value):
                return float(int(value, 0))
            if not re.fullmatch(
                r"[+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)",
                value,
            ):
                return 0.0
        result = float(value)
        return 0.0 if math.isnan(result) else result
    except (ValueError, TypeError, OverflowError):
        return 0.0


class Presence:
    def __init__(self):
        self.rows = {}

    def update(self, owner, body):
        now = now_ms()
        if truthy(body.get("active")):
            name = identifier_text(body.get("name"))
            name = name.encode("utf-16-le", errors="surrogatepass")[:120].decode(
                "utf-16-le", errors="replace"
            )
            values = {
                key: number(body.get(key))
                for key in ("exIdx", "exTotal", "setsDone", "setsTotal", "startedAt")
            }
            values["startedAt"] = values["startedAt"] or now
            self.rows[owner] = {
                "name": name,
                **{
                    key: value if math.isfinite(value) else None
                    for key, value in values.items()
                },
                "updatedAt": now,
            }
        elif body.get("reason") == "hidden":
            if owner in self.rows:
                self.rows[owner].setdefault("hiddenAt", now)
        else:
            self.rows.pop(owner, None)

    def live(self, owner):
        row = self.rows.get(owner)
        if row is None:
            return None
        now = now_ms()
        if (
            now - row["updatedAt"] >= 70000
            or "hiddenAt" in row
            and now - row["hiddenAt"] >= 45000
        ):
            self.rows.pop(owner, None)
            return None
        return {key: value for key, value in row.items() if key != "hiddenAt"}

    def clear(self):
        self.rows.clear()

    def sweep(self):
        for owner in list(self.rows):
            self.live(owner)
