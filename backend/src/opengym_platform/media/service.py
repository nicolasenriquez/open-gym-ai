"""Stream private files outside SQL; publish under a freshly verified actor lock."""

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import secrets
import time
from pathlib import Path

from opengym_platform.core.platform_settings import environment_number
from opengym_platform.identity.sessions import authorize
from opengym_platform.media.formats import TYPES, movie_duration, sniff
from opengym_platform.training.references import media_references, referenced_hashes


class Refused(Exception):
    def __init__(self, status, code, error, **extra):
        self.status, self.body = status, {"error": error, "code": code, **extra}


class Media:
    def __init__(self, config):
        self.config = config
        self.root = Path(os.environ.get("DATA_DIR", "/data")) / "uploads"
        self.reserved = {}
        self.inflight = {}
        self.windows = {}
        self.sizes = {}
        self.hourly = math.floor(environment_number("MEDIA_UPLOADS_PER_HOUR", 600, 1))
        self.min_free = environment_number("MEDIA_MIN_FREE_MB", 512, 0) * 1048576

    def directory(self, owner):
        name = re.sub(r"[^a-zA-Z0-9_-]", "", owner)
        if not name:
            raise ValueError("PLATFORM_MEDIA_OWNER_INVALID")
        return self.root / name

    def file(self, owner, digest):
        for mime, (extension, _) in TYPES.items():
            path = self.directory(owner) / f"{digest}.{extension}"
            if path.is_file() and path.stat().st_size:
                return path, mime
        return None

    def cap(self, kind):
        megabytes = self.config[kind + "MB"]
        return int(megabytes * 1024 * 1024 + 0.5), megabytes

    def check_size(self, size, kind):
        cap, megabytes = self.cap(kind)
        if size > cap:
            raise Refused(
                413, "media-too-large", "that file is too large", maxMB=megabytes
            )

    def inventory(self, owner):
        directory = self.directory(owner)
        if not directory.exists():
            return {}
        files = {}
        for path in directory.iterdir():
            if (
                re.fullmatch(r"[0-9a-f]{64}", path.stem)
                and path.suffix[1:] in {entry[0] for entry in TYPES.values()}
                and path.is_file()
                and not path.is_symlink()
            ):
                size = path.stat().st_size
                if size:
                    files.setdefault(path.stem, size)
        known = self.sizes.setdefault(owner, {})
        self.sizes[owner] = {
            digest: known.get(digest, size) for digest, size in files.items()
        }
        return files

    async def missing(self, database, session, hashes):
        async with database.transaction() as handle:
            if not await authorize(handle, session):
                return 401, {"error": "not signed in"}
            if (
                not isinstance(hashes, list)
                or len(hashes) > 1000
                or any(
                    not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h)
                    for h in hashes
                )
            ):
                raise Refused(
                    400,
                    "bad-request",
                    "hashes must be a list of at most 1000 lowercase sha256 hex strings",
                )
            files = self.inventory(session.owner)
            return 200, {
                "missing": [
                    h
                    for h in dict.fromkeys(hashes)
                    if h not in files or files[h] != self.sizes[session.owner][h]
                ],
                "usage": {
                    "bytes": sum(files.values()),
                    "count": len(files),
                    "quotaBytes": int(self.config["quotaMB"] * 1048576 + 0.5),
                },
            }

    def reconcile(self, owner, references, refresh=None):
        directory = self.directory(owner)
        if not directory.exists():
            return
        try:
            raw = json.loads((directory / ".gc.json").read_text())
            marks = (
                {
                    key: value
                    for key, value in raw.items()
                    if type(value) in (int, float) and math.isfinite(value)
                }
                if isinstance(raw, dict)
                else {}
            )
        except (OSError, ValueError):
            marks = {}
        hashes = {
            path.stem
            for path in directory.iterdir()
            if path.suffix[1:] in {entry[0] for entry in TYPES.values()}
            and re.fullmatch(r"[0-9a-f]{64}", path.stem)
        }
        now = int(time.time() * 1000)
        marks = {
            digest: now if digest == refresh else marks.get(digest, now)
            for digest in hashes - references
        }
        temporary = directory / ".gc.json.tmp"
        try:
            with os.fdopen(
                os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
            ) as output:
                json.dump(marks, output)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(directory / ".gc.json")
            sync_directory(directory)
        finally:
            temporary.unlink(missing_ok=True)
        return marks

    def reclaim_quota(self, owner, references):
        # No readable Training document means no authority to delete any blob.
        if references is None:
            return
        try:
            marks = self.reconcile(owner, references)
            if marks is None:
                return
            cutoff = time.time() * 1000 - 3600000
            for digest, marked in marks.items():
                if marked <= cutoff:
                    found = self.file(owner, digest)
                    if found:
                        found[0].unlink()
            sync_directory(self.directory(owner))
            self.reconcile(owner, references)
        except OSError:
            logging.getLogger(__name__).warning("PLATFORM_MEDIA_QUOTA_CLEANUP_FAILED")

    async def note_state(self, owner, document):
        self.reconcile(owner, referenced_hashes(document))

    def clean_temporaries(self, age=0):
        try:
            if self.root.is_symlink() or not self.root.exists():
                return
            for directory in self.root.iterdir():
                if (
                    directory.is_symlink()
                    or not directory.is_dir()
                    or directory.name.startswith(".")
                ):
                    continue
                temporary = directory / ".tmp"
                paths = (
                    list(temporary.iterdir())
                    if temporary.is_dir() and not temporary.is_symlink()
                    else []
                )
                paths.append(directory / ".gc.json.tmp")
                for path in paths:
                    try:
                        if (
                            not path.is_symlink()
                            and path.is_file()
                            and (not age or time.time() - path.stat().st_mtime >= age)
                        ):
                            path.unlink()
                    except OSError:
                        logging.getLogger(__name__).warning(
                            "PLATFORM_MEDIA_TEMP_CLEANUP_FAILED"
                        )
        except OSError:
            logging.getLogger(__name__).warning("PLATFORM_MEDIA_TEMP_CLEANUP_FAILED")

    async def maintain_temporaries(self):
        while True:
            await asyncio.sleep(3600)
            self.clean_temporaries(3600)

    async def receive(self, database, session, digest, request):
        reservation = {"bytes": 0, "entered": False}
        try:
            return await self._receive(database, session, digest, request, reservation)
        finally:
            if reservation["entered"]:
                active = self.inflight[session.owner] - 1
                if active:
                    self.inflight[session.owner] = active
                else:
                    del self.inflight[session.owner]
            remaining = self.reserved.get(session.owner, 0) - reservation["bytes"]
            if remaining:
                self.reserved[session.owner] = remaining
            else:
                self.reserved.pop(session.owner, None)

    async def _receive(self, database, session, digest, request, reservation):
        async with database.transaction() as handle:
            if not await authorize(handle, session):
                return 401, {"error": "not signed in"}
            now = time.monotonic()
            self.windows = {k: v for k, v in self.windows.items() if now - v[0] < 3600}
            window = self.windows.setdefault(session.owner, [now, 0])
            window[1] += 1
            if window[1] > self.hourly:
                raise Refused(
                    429,
                    "locked",
                    "too many uploads, try again later",
                    retryAfter=max(1, math.ceil(window[0] + 3600 - now)),
                )
            if self.inflight.get(session.owner, 0) >= 2:
                raise Refused(
                    429,
                    "busy",
                    "too many uploads at once, try again in a moment",
                    retryAfter=5,
                )
            self.inflight[session.owner] = self.inflight.get(session.owner, 0) + 1
            reservation["entered"] = True
            declared = (
                request.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            if declared not in TYPES:
                raise Refused(415, "media-type", "that file type is not accepted")
            kind = TYPES[declared][1]
            length = request.headers.get("content-length")
            if length and length.isdecimal():
                self.check_size(int(length), kind)
            have = self.file(session.owner, digest)
            if (
                have
                and self.sizes.get(session.owner, {}).get(
                    digest, have[0].stat().st_size
                )
                != have[0].stat().st_size
            ):
                have = None
            if have and (not length or int(length) == have[0].stat().st_size):
                references = await media_references(handle, session.owner)
                self.note_upload(session.owner, references, digest)
                return self.stored(
                    digest, have[1], have[0].stat().st_size, existed=True
                )
            need = int(length) if length and length.isdecimal() else self.cap(kind)[0]
            used = sum(self.inventory(session.owner).values())
            quota = int(self.config["quotaMB"] * 1048576 + 0.5)
            if quota and used + self.reserved.get(session.owner, 0) + need > quota:
                references = await media_references(handle, session.owner)
                self.reclaim_quota(session.owner, references)
                used = sum(self.inventory(session.owner).values())
            if quota and used + self.reserved.get(session.owner, 0) + need > quota:
                raise Refused(
                    413,
                    "media-quota",
                    "your space for photos and videos is full",
                    usedMB=math.floor(used / 1048576 * 10 + 0.5) / 10,
                    quotaMB=self.config["quotaMB"],
                )
            self.reserved[session.owner] = self.reserved.get(session.owner, 0) + need
            reservation["bytes"] = need
        directory = self.directory(session.owner)
        for path in (self.root, directory, directory / ".tmp"):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        temporary = directory / ".tmp" / secrets.token_hex(12)
        try:
            if self.min_free:
                try:
                    space = os.statvfs(directory)
                except OSError:
                    space = None
                if (
                    space is not None
                    and space.f_bavail * space.f_frsize - reservation["bytes"]
                    < self.min_free
                ):
                    raise Refused(
                        507, "storage-full", "the server is running out of disk space"
                    )
            digestor = hashlib.sha256()
            head, size = b"", 0
            with temporary.open("xb") as output:
                temporary.chmod(0o600)
                async with asyncio.timeout(1800):
                    stream = request.stream().__aiter__()
                    while True:
                        try:
                            async with asyncio.timeout(60):
                                chunk = await anext(stream)
                        except StopAsyncIteration:
                            break
                        size += len(chunk)
                        self.check_size(size, kind)
                        output.write(chunk)
                        digestor.update(chunk)
                        head += chunk[: 64 - len(head)]
                output.flush()
                os.fsync(output.fileno())
            if digestor.hexdigest() != digest:
                raise Refused(400, "hash-mismatch", "the file does not match its name")
            mime = sniff(head)
            if mime is None or (TYPES[mime][1] == "video") != (kind == "video"):
                raise Refused(415, "media-type", "that file type is not accepted")
            extension, actual_kind = TYPES[mime]
            self.check_size(size, actual_kind)
            if extension in {"mp4", "mov"}:
                try:
                    with temporary.open("rb") as source:
                        duration = movie_duration(source, size)
                except ValueError:
                    raise Refused(
                        415, "media-invalid", "that video could not be read"
                    ) from None
                if duration is not None and duration > self.config["videoSec"] + 1:
                    raise Refused(
                        413,
                        "media-too-long",
                        "that video is too long",
                        maxSec=self.config["videoSec"],
                    )
            async with database.transaction() as handle:
                if not await authorize(handle, session):
                    return 401, {"error": "not signed in"}
                references = await media_references(handle, session.owner)
                existed = self.file(session.owner, digest)
                if existed and existed[0].stat().st_size != size:
                    existed = None
                if not existed:
                    temporary.replace(directory / f"{digest}.{extension}")
                    sync_directory(directory)
                self.sizes.setdefault(session.owner, {})[digest] = size
                self.note_upload(session.owner, references, digest)
            return self.stored(digest, mime, size, existed=bool(existed))
        except TimeoutError:
            raise Refused(408, "timeout", "the upload stalled") from None
        finally:
            temporary.unlink(missing_ok=True)

    def stored(self, digest, mime, size, *, existed):
        return (200 if existed else 201), {
            "ok": True,
            "hash": digest,
            "mime": mime,
            "size": size,
            "existed": bool(existed),
        }

    def note_upload(self, owner, references, digest):
        try:
            self.reconcile(owner, references or set(), refresh=digest)
        except OSError:
            logging.getLogger(__name__).warning("PLATFORM_MEDIA_MARK_FAILED")

    async def download(self, database, session, digest):
        async with database.transaction() as handle:
            if not await authorize(handle, session):
                return None
            found = self.file(session.owner, digest)
            if not found:
                raise Refused(404, "media-missing", "no such file")
            path, mime = found
        try:
            source = path.open("rb")
        except FileNotFoundError:
            raise Refused(404, "media-missing", "no such file") from None
        return source, mime, path.suffix[1:]


def sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
