"""Ops-only authenticated bundle publication; never imported by API."""

import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import asyncpg

from opengym_platform.backup import read_private
from opengym_platform.core.platform_settings import PLATFORM_LOCK_KEY, load_database


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("BACKUP_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise ValueError("BACKUP_FILE_TYPE_INVALID")
    return os.fdopen(fd, "rb")


def record(path, name):
    with regular(path) as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError("BACKUP_FILE_CHANGED")
        return {"path": name, "size": before.st_size, "sha256": digest}


def stamp(path):
    info = path.lstat()
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_nlink,
    )


def safe_name(name):
    if not isinstance(name, str):
        raise TypeError("BACKUP_ARCHIVE_PATH_INVALID")
    path = PurePosixPath(name)
    if (
        not isinstance(name, str)
        or not name
        or path.is_absolute()
        or str(path) != name
        or ".." in path.parts
        or "\\" in name
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError("BACKUP_ARCHIVE_PATH_INVALID")


class BundleEntry(tarfile.TarInfo):
    @classmethod
    def frombuf(cls, buf, encoding, errors):
        entry = super().frombuf(buf, encoding, errors)
        # USTAR only: reject extension headers before tarfile allocates their payload.
        if entry.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
            raise ValueError("BACKUP_ARCHIVE_ENTRY_INVALID")
        return entry


def verify(path, identity, expected, destination=None):
    process = subprocess.Popen(
        ["age", "--decrypt", "--identity", str(identity), str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        with tarfile.open(
            fileobj=process.stdout, mode="r|", tarinfo=BundleEntry
        ) as archive:
            first = archive.next()
            if (
                first is None
                or first.name != "manifest.json"
                or not first.isfile()
                or first.size > 32 * 1024 * 1024
            ):
                raise ValueError("BACKUP_MANIFEST_INVALID")
            manifest = json.load(archive.extractfile(first), object_pairs_hook=unique)
            if not isinstance(manifest, dict) or (
                expected is not None and manifest != expected
            ):
                raise ValueError("BACKUP_MANIFEST_INVALID")
            if (
                not isinstance(manifest.get("files"), list)
                or len(manifest["files"]) > 100_000
            ):
                raise ValueError("BACKUP_MANIFEST_INVALID")
            for item in manifest["files"]:
                safe_name(item["path"])
                if item["path"] == "manifest.json" or item["path"].count("/") > 64:
                    raise ValueError("BACKUP_ARCHIVE_PATH_INVALID")
                if item.get("directory") is True:
                    if set(item) != {"path", "directory"}:
                        raise ValueError("BACKUP_MANIFEST_INVALID")
                elif (
                    set(item) != {"path", "size", "sha256"}
                    or type(item["size"]) is not int
                    or item["size"] < 0
                    or not isinstance(item["sha256"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
                ):
                    raise ValueError("BACKUP_MANIFEST_INVALID")
            entries = {item["path"]: item for item in manifest["files"]}
            if len(entries) != len(manifest["files"]):
                raise ValueError("BACKUP_DUPLICATE_FILE")
            seen = {"manifest.json"}
            for member in archive:
                # Streaming iteration includes the already-read first member.
                if member is first:
                    continue
                safe_name(member.name)
                if member.name in seen or member.name not in entries:
                    raise ValueError("BACKUP_ARCHIVE_ENTRY_INVALID")
                seen.add(member.name)
                item = entries[member.name]
                if destination is not None:
                    tarfile.data_filter(member, str(destination))
                    target = destination / member.name
                    # Every ancestor must be an explicit directory in the manifest.
                    for parent in reversed(
                        target.relative_to(destination).parents[:-1]
                    ):
                        ancestor = destination / parent
                        if entries.get(parent.as_posix()) != {
                            "path": parent.as_posix(),
                            "directory": True,
                        }:
                            raise ValueError("BACKUP_ARCHIVE_PATH_INVALID")
                        ancestor.mkdir(mode=0o700, exist_ok=True)
                if item.get("directory"):
                    if not member.isdir() or member.size != 0:
                        raise ValueError("BACKUP_ARCHIVE_ENTRY_INVALID")
                    if destination is not None:
                        target.mkdir(mode=0o700, exist_ok=True)
                else:
                    if not member.isfile() or member.size != item["size"]:
                        raise ValueError("BACKUP_ARCHIVE_ENTRY_INVALID")
                    with archive.extractfile(member) as stream:
                        if destination is None:
                            digest = hashlib.file_digest(stream, "sha256").hexdigest()
                        else:
                            digestor = hashlib.sha256()
                            with target.open("xb") as output:
                                os.chmod(output.fileno(), 0o600)
                                while chunk := stream.read(1024 * 1024):
                                    digestor.update(chunk)
                                    output.write(chunk)
                                output.flush()
                                os.fsync(output.fileno())
                            digest = digestor.hexdigest()
                    if digest != item["sha256"]:
                        raise ValueError("BACKUP_CHECKSUM_INVALID")
            if seen != {"manifest.json", *entries}:
                raise ValueError("BACKUP_ARCHIVE_INCOMPLETE")
        # tar EOF is not age EOF: drain and require authentication of the final chunk.
        while process.stdout.read(1024 * 1024):
            pass
        if process.wait(timeout=30) != 0:
            raise ValueError("BACKUP_AUTHENTICATION_FAILED")
        return manifest
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=30)


def durable_json(path, value):
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(stream.fileno(), 0o600)
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare(settings, proof):
    root = Path(settings["staging_root"])
    destination = Path(settings["destination"])
    identity = Path(settings["identity_file"])
    operation = settings["operation"]
    process = None
    try:
        captured = root / operation
        if captured.is_symlink() or not captured.is_dir():
            raise ValueError("BACKUP_CAPTURE_INVALID")
        if (
            identity.is_relative_to(root)
            or identity.is_relative_to(destination)
            or destination.is_relative_to(root)
            or root.is_relative_to(destination)
        ):
            raise ValueError("BACKUP_PATH_OVERLAP")
        with regular(captured / "capture.json") as stream:
            if os.fstat(stream.fileno()).st_size > 32 * 1024 * 1024:
                raise ValueError("BACKUP_MANIFEST_LIMIT")
            capture = json.load(stream, object_pairs_hook=unique)
        if (
            capture["operation"] != operation
            or capture["instance_id"] != settings["instance_id"]
            or capture["snapshot_at"] != proof["snapshot_at"]
            or capture["sources"] != proof["capture_sources"]
        ):
            raise ValueError("BACKUP_CAPTURE_INVALID")
        files = []
        allowed = {item["path"] for item in capture["files"]}
        if (
            len(allowed) != len(capture["files"])
            or not {"data", "database.dump"} <= allowed
        ):
            raise ValueError("BACKUP_CAPTURE_INVALID")
        allowed.update({"capture.json", "host-journal.json"})
        for parent, directories, names in os.walk(captured, followlinks=False):
            for name in sorted(directories + names):
                path = Path(parent) / name
                relative = path.relative_to(captured).as_posix()
                safe_name(relative)
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    files.append({"path": relative, "directory": True})
                elif relative in allowed:
                    files.append(record(path, relative))
                else:
                    raise ValueError("BACKUP_UNEXPECTED_FILE")
        indexed = {item["path"]: item for item in files}
        for item in capture["files"]:
            if indexed.get(item["path"]) != item:
                raise ValueError("BACKUP_CAPTURE_CHANGED")
        versions = json.loads(Path("/app/versions.json").read_text())
        if (
            subprocess.check_output(
                ["age", "--version"], stderr=subprocess.DEVNULL, timeout=5
            )
            .decode()
            .strip()
            .removeprefix("v")
            != versions["age"]["version"]
        ):
            raise ValueError("BACKUP_TOOL_VERSION_INVALID")
        manifest = {
            "version": 1,
            "instance_id": settings["instance_id"],
            "operation": operation,
            "snapshot_at": capture["snapshot_at"],
            "schema": capture["schema"],
            "release": {
                "writers": proof["writers"],
                "ops": proof["ops_image"],
                "database": proof["database"],
            },
            "tools": {
                "age": versions["age"]["version"],
                "postgres": versions["postgres"],
            },
            "coverage": ["database", "data", "runtime-secrets", "configuration"],
            "files": files,
        }
        encoded = json.dumps(manifest, ensure_ascii=True).encode()
        if len(encoded) > 32 * 1024 * 1024:
            raise ValueError("BACKUP_MANIFEST_LIMIT")
        encrypted = captured / "bundle.age"
        with encrypted.open("xb") as output:
            os.chmod(output.fileno(), 0o600)
            process = subprocess.Popen(
                ["age", "--encrypt", "--recipient", settings["recipient"]],
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=subprocess.DEVNULL,
            )
            try:
                with tarfile.open(
                    fileobj=process.stdin, mode="w|", format=tarfile.USTAR_FORMAT
                ) as archive:
                    header = tarfile.TarInfo("manifest.json")
                    header.size = len(encoded)
                    header.mode = 0o600
                    archive.addfile(header, io.BytesIO(encoded))
                    for item in files:
                        header = tarfile.TarInfo(item["path"])
                        header.mode = 0o700 if item.get("directory") else 0o600
                        if item.get("directory"):
                            header.type = tarfile.DIRTYPE
                            archive.addfile(header)
                        else:
                            header.size = item["size"]
                            with regular(captured / item["path"]) as stream:
                                archive.addfile(header, stream)
            finally:
                process.stdin.close()
            if process.wait(timeout=300) != 0:
                raise ValueError("BACKUP_ENCRYPTION_FAILED")
            output.flush()
            os.fsync(output.fileno())
        partial = destination / f"{operation}.age.partial"
        final = destination / f"{operation}.age"
        if final.exists():
            raise ValueError("BACKUP_DESTINATION_EXISTS")
        with regular(encrypted) as source, partial.open("xb") as output:
            os.chmod(output.fileno(), 0o600)
            shutil.copyfileobj(source, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        ciphertext = record(partial, final.name)
        verify(partial, identity, manifest)
        if record(partial, final.name) != ciphertext:
            raise ValueError("BACKUP_FILE_CHANGED")
        unchanged = stamp(partial)
        receipt = {
            "version": 1,
            "instance_id": settings["instance_id"],
            "operation": operation,
            "verified": True,
            "snapshot_at": capture["snapshot_at"],
            "verified_at": datetime.now(UTC).isoformat(),
            "ciphertext": ciphertext,
            "cleanup_pending": True,
        }
        return partial, final, receipt, unchanged
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=30)


async def publish(config, reason):
    connection = None
    try:
        settings = read_private(config)
        if set(settings) != {
            "instance_id",
            "project",
            "staging_root",
            "operation",
            "destination",
            "identity_file",
            "recipient",
        }:
            raise ValueError("BACKUP_CONFIG_INVALID")
        if not isinstance(settings["recipient"], str) or not re.fullmatch(
            r"age1[0-9a-z]{58}", settings["recipient"]
        ):
            raise ValueError("BACKUP_RECIPIENT_INVALID")
        operation = settings["operation"]
        if not re.fullmatch(r"[a-f0-9]{32}", operation):
            raise ValueError("BACKUP_OPERATION_INVALID")
        root = Path(settings["staging_root"])
        destination = Path(settings["destination"])
        identity = Path(settings["identity_file"])
        proof = read_private(root / "journal.json")
        windows_acl = proof.get("host_platform") == "win32"
        for directory in (root, destination):
            if (
                not directory.is_absolute()
                or directory.is_symlink()
                or not directory.is_dir()
                or (not windows_acl and directory.stat().st_mode & 0o077)
            ):
                raise ValueError("BACKUP_DIRECTORY_INVALID")
        with regular(identity) as key:
            if not windows_acl and os.fstat(key.fileno()).st_mode & 0o077:
                raise ValueError("BACKUP_IDENTITY_INVALID")
        if (
            proof["operation"] != operation
            or proof["instance_id"] != settings["instance_id"]
            or proof["project"] != settings["project"]
            or proof["phase"] != "bundling"
            or proof["reason"] != reason
            or proof["verified"] is not False
            or not (root / "exclusive").is_dir()
        ):
            raise ValueError("BACKUP_WRITER_PROOF_REQUIRED")
        database = load_database("backup")
        connection = await asyncpg.connect(
            host=database.host,
            port=5432,
            database=database.database,
            user=database.user,
            password=database.password,
            ssl=False,
            timeout=5,
            command_timeout=5,
        )
        if not await connection.fetchval(
            "SELECT pg_try_advisory_lock($1)", PLATFORM_LOCK_KEY
        ):
            raise ValueError("BACKUP_DATABASE_LOCKED")
        partial, final, receipt, unchanged = await asyncio.to_thread(
            prepare, settings, proof
        )
        await connection.execute("SELECT 1")
        if stamp(partial) != unchanged:
            raise ValueError("BACKUP_FILE_CHANGED")
        os.rename(partial, final)
        sync_directory(destination)
        durable_json(root / "gate" / "backup.json", receipt)
        return 0, {"code": "BACKUP_VERIFIED", "operation": operation, "verified": True}
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        tarfile.TarError,
        asyncpg.PostgresError,
    ):
        return 1, {"code": "BACKUP_BUNDLE_BLOCKED"}
    finally:
        if connection is not None:
            try:
                await connection.close(timeout=5)
            except (OSError, asyncpg.PostgresError, TimeoutError):
                connection.terminate()
