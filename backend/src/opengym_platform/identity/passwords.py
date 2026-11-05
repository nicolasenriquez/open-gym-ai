"""Node-compatible scrypt and Unicode; bounded crypto outside database leases."""

import asyncio
import base64
import hashlib
import hmac
import math
import os
import re
import unicodedata
from decimal import Decimal

# ECMAScript trim differs from Python strip (notably BOM and U+0085).
SPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
PATTERN = re.compile(
    r"\$scrypt\$v=1\$ln=(\d{1,2}),r=(\d{1,2}),p=(\d{1,2})\$([A-Za-z0-9+/]+=*)\$([A-Za-z0-9+/]+=*)",
    re.ASCII,
)


def normalize(password):
    # Node's UTF-8 encoding replaces unpaired UTF-16 surrogates with U+FFFD.
    return (
        unicodedata.normalize("NFKC", password)
        .encode("utf-16", "surrogatepass")
        .decode("utf-16", "replace")
    )


def identifier_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    number = float(value)
    if not math.isfinite(number):
        return "Infinity" if number > 0 else "-Infinity" if number < 0 else "NaN"
    if not number:
        return "0"
    if 1e-6 <= abs(number) < 1e21:
        return (
            format(Decimal(str(number)), "f").rstrip("0").rstrip(".")
            if not number.is_integer()
            else str(int(number))
        )
    return re.sub(r"e([+-])0+", r"e\1", str(number).replace(".0e", "e"))


def name_key(value):
    return unicodedata.normalize("NFKC", value).strip(SPACE).lower()


def parse(stored):
    match = PATTERN.fullmatch(stored or "")
    if not match:
        return None
    ln, r, p = map(int, match.group(1, 2, 3))
    if (
        not (10 <= ln <= 17 and 1 <= r <= 16 and 1 <= p <= 16)
        or 128 * 2**ln * r > 256 * 1024 * 1024
    ):
        return None

    # Buffer.from(base64) accepts missing/excess padding and trailing single sextets.
    def decode(value):
        value = value.rstrip("=")
        if len(value) % 4 == 1:
            value = value[:-1]
        return base64.b64decode(value + "=" * (-len(value) % 4))

    salt, key = map(decode, match.group(4, 5))
    if len(salt) < 8 or not 16 <= len(key) <= 128:
        return None
    return ln, r, p, salt, key


def derive(password, material):
    ln, r, p, salt, key = material
    return hashlib.scrypt(
        normalize(password).encode(),
        salt=salt,
        n=2**ln,
        r=r,
        p=p,
        dklen=len(key),
        maxmem=128 * 2**ln * r * p + 16 * 1024 * 1024,
    )


def make_hash(password):
    salt = os.urandom(16)
    key = derive(password, (15, 8, 1, salt, bytes(32)))
    return (
        "$scrypt$v=1$ln=15,r=8,p=1$"
        + base64.b64encode(salt).decode()
        + "$"
        + base64.b64encode(key).decode()
    )


class BusyError(Exception):
    """Both crypto workers and their bounded queue are occupied."""


class Passwords:
    def __init__(self):
        self.slots = asyncio.Semaphore(2)
        self.pending = 0
        self.dummy = None

    async def warm_up(self):
        self.dummy = parse(await asyncio.to_thread(make_hash, os.urandom(24).hex()))

    async def run(self, function, *args):
        if self.pending >= 34:
            raise BusyError
        self.pending += 1

        async def work():
            async with self.slots:
                return await asyncio.to_thread(function, *args)

        task = asyncio.create_task(work())

        def finished(task):
            self.pending -= 1
            if not task.cancelled():
                task.exception()

        task.add_done_callback(finished)
        # Cancellation of HTTP must not release a slot while its thread still runs.
        return await asyncio.shield(task)

    async def verify(self, password, stored):
        if len(normalize(password)) > 256:
            return False
        real = parse(stored)
        if self.dummy is None:
            await self.warm_up()
        key = await self.run(derive, password, real or self.dummy)
        return real is not None and hmac.compare_digest(key, real[4])

    async def rehash(self, password, stored):
        material = parse(stored)
        if material and material[:3] != (15, 8, 1):
            return await self.run(make_hash, password)
        return None
