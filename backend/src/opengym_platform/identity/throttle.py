"""Process-local Node-compatible password budgets; no persistence promise."""

import ipaddress
import math
import time


class LockedError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


class Backoff:
    def __init__(self, free, base, maximum, forget):
        self.free, self.base, self.maximum, self.forget = free, base, maximum, forget
        self.entries = {}

    def wait(self, key):
        entry = self.entries.get(key)
        return max(0, math.ceil(entry[1] - time.monotonic())) if entry else 0

    def attempt(self, key):
        now = time.monotonic()
        # Prune quiet keys, but never evict a live account's failure budget.
        for k, e in list(self.entries.items()):
            if now - max(e[1], e[2]) > self.forget:
                del self.entries[k]
        entry = self.entries.get(key, [0, 0, now])
        previous = entry[1]
        entry[0] += 1
        entry[2] = now
        locked = entry[0] > self.free
        if locked:
            entry[1] = now + min(
                self.maximum, self.base * 2 ** min(30, entry[0] - self.free - 1)
            )
        if key not in self.entries and len(self.entries) >= 10000:
            candidates = [k for k in self.entries if not k.startswith("acct:")]
            if candidates:
                victim = min(
                    candidates,
                    key=lambda k: (
                        self.wait(k) > 0,
                        self.entries[k][0],
                        self.entries[k][2],
                    ),
                )
                del self.entries[victim]
        self.entries[key] = entry
        open_attempt = True

        def undo():
            nonlocal open_attempt
            if not open_attempt:
                return
            open_attempt = False
            if self.entries.get(key) is not entry:
                return
            entry[0] -= 1
            if locked and entry[0] <= self.free:
                entry[1] = previous
            if entry[0] <= 0 and not self.wait(key):
                self.entries.pop(key, None)

        return undo


class Throttle:
    def __init__(self):
        self.accounts = Backoff(5, 60, 3600, 86400)
        self.addresses = Backoff(20, 30, 900, 3600)
        self.windows = {}

    def entry(self, address):
        now = time.monotonic()
        self.windows = {k: e for k, e in self.windows.items() if now - e[0] < 60}
        if address not in self.windows and len(self.windows) >= 10000:
            del self.windows[next(iter(self.windows))]
        entry = self.windows.setdefault(address, [now, 0])
        entry[1] += 1
        wait = (
            max(1, math.ceil(entry[0] + 60 - now))
            if entry[1] > 60
            else self.addresses.wait(address)
        )
        if wait:
            raise LockedError(wait)

    def begin(self, key, address):
        wait = self.accounts.wait(key) or self.addresses.wait(address)
        if wait:
            raise LockedError(wait)
        return self.accounts.attempt(key), self.addresses.attempt(address)


def limit_address(request, trust_proxy):
    raw = request.client.host if request.client else ""
    if trust_proxy:
        forwarded = [
            part.strip()
            for part in request.headers.get("x-forwarded-for", "").split(",")
            if part.strip()
        ]
        raw = (
            request.headers.get("cf-connecting-ip", "").strip()
            or (forwarded[-1] if forwarded else "")
            or request.headers.get("x-real-ip", "").strip()
            or raw
        )
    try:
        address = ipaddress.ip_address(raw.strip("[]"))
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped:
                return str(address.ipv4_mapped)
            # Match Node's four uncompressed hextets for the household /64.
            return (
                ":".join(
                    f"{int(part, 16):x}" for part in address.exploded.split(":")[:4]
                )
                + "::/64"
            )
        return str(address)
    except ValueError:
        return "unknown"
