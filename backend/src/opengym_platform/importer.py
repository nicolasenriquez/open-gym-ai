"""One-shot legacy import into an explicitly quarantined, empty platform target."""

import base64
import hashlib
import json
import math
import os
import re
import secrets
import stat
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import asyncpg

from opengym_platform.coach.secrets import SecretFiles
from opengym_platform.core.platform_settings import PLATFORM_LOCK_KEY, load_database
from opengym_platform.identity.passwords import name_key, parse

# Only the ops image receives this module and migration tooling. Never loaded by HTTP.
TABLES = {
    "identity.invitations": "code note created_by created_at consumed used_by used_at revoked",
    "identity.users": "id display_name created_at is_admin disabled session_version last_pull_at invited_by",
    "identity.login_aliases": "alias_key owner_id email_claim password_name_claim reset_name_until",
    "identity.password_credentials": "owner_id scrypt_hash set_at",
    "identity.password_resets": "owner_id code_digest expires_at issued_by",
    "identity.passkeys": "credential_id owner_id public_key counter transports label created_at last_used_at",
    "identity.device_links": "code_digest owner_id created_at expires_at",
    "training.documents": "owner_id document",
    "notifications.subscriptions": "endpoint owner_id p256dh auth device_id created_at",
    "notifications.delivery_state": "owner_id last_reminder_date last_nudge_date",
    "coach.provider_settings": "provider model options secret_ref bound_owner_id",
    "coach.settings": "id enabled provider auth_mode community per_profile_daily instance_daily max_message_len max_output_tokens",
    "coach.profile_state": "owner_id sharing forget_generation",
    "coach.daily_usage": "owner_id day count",
    "coach.instance_daily_usage": "day count",
    "coach.history_events": "event_id owner_id job_id kind outcome error_class occurred_at details",
    "coach.instance_results": "event_id occurred_at kind trigger outcome error_class duration_ms summary",
    "coach.pending_proposals": "owner_id document",
    "coach.jobs": "owner_id job_id kind trigger state started_at forget_generation",
    "audit.events": "id occurred_at event ok actor_id target_id actor_name target_name message action ip",
}
SEQUENCES = {
    "audit.events": ("id", "audit.events_id_seq"),
    "coach.history_events": ("event_id", "coach.history_events_event_id_seq"),
    "coach.instance_results": ("event_id", "coach.instance_results_event_id_seq"),
}
PROVIDERS = (
    "fixture",
    "claude",
    "codex",
    "anthropic",
    "openai",
    "gemini",
    "compatible",
)
DEFERRED = {"claude", "codex"}
JSON_COLUMNS = {"document", "details", "summary", "options"}


class Blocked(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Blocked(code)


def shape(value, allowed, required=()):
    require(
        isinstance(value, dict)
        and set(required) <= value.keys() <= set(allowed.split()),
        "FIELDS",
    )
    return value


def number(raw):
    value = float(raw)
    require(math.isfinite(value) and Decimal(str(value)) == Decimal(raw), "JSON_NUMBER")
    require(value != 0 or not raw.startswith("-"), "JSON_NUMBER")
    return int(raw) if re.fullmatch(r"-?[0-9]+", raw) else value


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_KEY")
        result[key] = value
    return result


def unicode_values(value):
    if isinstance(value, str):
        value.encode("utf-8", "strict")
        require("\x00" not in value, "JSON_UNICODE")
    elif isinstance(value, dict):
        for key, child in value.items():
            unicode_values(key)
            unicode_values(child)
    elif isinstance(value, list):
        for child in value:
            unicode_values(child)


def strict_json(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "strict")
    value = json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_int=number,
        parse_float=number,
        parse_constant=lambda _: require(False, "JSON_NUMBER"),
    )
    unicode_values(value)
    return value


def timestamp(value):
    if value is None:
        return None
    if type(value) in (int, float):
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=integer(value))
    require(isinstance(value, str), "TIMESTAMP")
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None and result.microsecond % 1000 == 0, "TIMESTAMP")
    return result.astimezone(UTC)


def day(value):
    if value is None:
        return None
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value),
        "DATE",
    )
    return date.fromisoformat(value)


def integer(value, maximum=9007199254740991):
    require(
        type(value) in (int, float) and 0 <= value <= maximum and value == int(value),
        "INTEGER",
    )
    return int(value)


def boolean(value):
    require(type(value) is bool, "BOOLEAN")
    return value


def text(value):
    require(isinstance(value, str) and bool(value), "TEXT")
    return value


def digest(value):
    require(
        isinstance(value, str) and re.fullmatch(r"[a-fA-F0-9]{64}", value), "DIGEST"
    )
    return bytes.fromhex(value)


def b64url(value):
    require(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value), "CREDENTIAL"
    )
    result = base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )
    require(
        base64.urlsafe_b64encode(result).decode().rstrip("=") == value, "CREDENTIAL"
    )
    return result


def private_directory(path):
    require(path.is_absolute() and path.resolve() == path, "PATH")
    info = path.stat(follow_symlinks=False)
    require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o700,
        "DIRECTORY",
    )


def inventory(source):
    require(source.is_absolute() and source.resolve() == source, "SOURCE_PATH")
    require(os.statvfs(source).f_flag & os.ST_RDONLY, "SOURCE_NOT_FROZEN")
    files = {}
    total = 0

    def unreadable(error):
        raise error

    for parent, directories, names in os.walk(
        source, followlinks=False, onerror=unreadable
    ):
        for name in directories + names:
            path = Path(parent) / name
            info = path.stat(follow_symlinks=False)
            require(
                not stat.S_ISLNK(info.st_mode)
                and (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)),
                "SOURCE_LINK",
            )
            require(os.statvfs(path).f_flag & os.ST_RDONLY, "SOURCE_NOT_FROZEN")
            if stat.S_ISDIR(info.st_mode):
                continue
            require(
                info.st_nlink == 1 and info.st_size <= 64 * 1024 * 1024, "SOURCE_FILE"
            )
            total += info.st_size
            require(total <= 512 * 1024 * 1024, "SOURCE_SIZE")
            with path.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            files[path.relative_to(source).as_posix()] = checksum
    require("db.json" in files and "secret" in files, "SOURCE_MISSING")
    return files


def plan(source, files, admin_uids):
    rows = {table: [] for table in TABLES}
    copies = {}
    records = {}
    consumed = {"db.json", "secret"}

    def read(name):
        consumed.add(name)
        return strict_json((source / name).read_bytes())

    def add(table, *values):
        rows[table].append(values)

    db = shape(read("db.json"), "users creds subs invites deviceLinks", ("users",))
    for name in ("users", "creds", "subs", "invites", "deviceLinks"):
        require(isinstance(db.get(name, []), list), "DB_LIST")
    users = {text(user["id"]) for user in db["users"]}
    require(len(users) == len(db["users"]) and set(admin_uids) <= users, "OWNERSHIP")
    aliases = {}
    for invitation in db.get("invites", []):
        shape(
            invitation,
            "code note createdBy created usedBy usedAt revoked",
            ("code", "createdBy"),
        )
        add(
            "identity.invitations",
            text(invitation["code"]),
            invitation.get("note", ""),
            text(invitation["createdBy"]),
            timestamp(invitation.get("created")),
            bool(invitation.get("usedBy")),
            invitation.get("usedBy"),
            timestamp(invitation.get("usedAt")),
            boolean(invitation.get("revoked", False)),
        )
    for user in db["users"]:
        shape(
            user,
            "id name created admin disabled sv lastPull invitedBy pw email pwReset lastReminder lastNudge",
            ("id", "name"),
        )
        owner = user["id"]
        add(
            "identity.users",
            owner,
            text(user["name"]),
            timestamp(user.get("created")),
            boolean(user.get("admin", False)) or owner in admin_uids,
            boolean(user.get("disabled", False)),
            integer(user.get("sv", 0)),
            timestamp(user.get("lastPull")),
            user.get("invitedBy"),
        )
        password = user.get("pw")
        reset = user.get("pwReset")
        if password is not None:
            shape(password, "h set", ("h",))
            require(parse(password["h"]) is not None, "PASSWORD")
            add(
                "identity.password_credentials",
                owner,
                password["h"],
                timestamp(password.get("set")),
            )
        if reset is not None:
            shape(reset, "h exp by", ("h", "exp", "by"))
            add(
                "identity.password_resets",
                owner,
                digest(reset["h"]),
                timestamp(reset["exp"]),
                text(reset["by"]),
            )
        for key, email_claim, password_claim, until in (
            (user.get("email"), True, False, None),
            (
                name_key(user["name"]) if password or reset else None,
                False,
                password is not None,
                timestamp(reset["exp"]) if reset else None,
            ),
        ):
            if key is None:
                continue
            require(
                isinstance(key, str) and key == name_key(key) and bool(key), "ALIAS"
            )
            previous = aliases.setdefault(key, [owner, False, False, None])
            require(previous[0] == owner, "ALIAS_COLLISION")
            previous[1] |= email_claim
            previous[2] |= password_claim
            previous[3] = until or previous[3]
        if "lastReminder" in user or "lastNudge" in user:
            add(
                "notifications.delivery_state",
                owner,
                day(user.get("lastReminder")),
                day(user.get("lastNudge")),
            )
        safe = re.sub(r"[^A-Za-z0-9_-]", "", owner)
        require(
            safe
            and sum(re.sub(r"[^A-Za-z0-9_-]", "", uid) == safe for uid in users) == 1,
            "OWNER_PATH_COLLISION",
        )
        state_name = f"state-{safe}.json"
        if state_name in files:
            document = read(state_name)
            require(isinstance(document, dict), "TRAINING_OBJECT")
            revision = document.get("_rev")
            if revision is not None:
                integer(revision)
            require(
                document.get("_wid") is None or isinstance(document["_wid"], str),
                "TRAINING_WRITE_ID",
            )
            add("training.documents", owner, document)
        coach_name = f"coach/{safe}.json"
        if coach_name in files:
            records[owner] = shape(
                read(coach_name), "daily current pending history share"
            )
    rows["identity.login_aliases"] = [(key, *value) for key, value in aliases.items()]
    for credential in db.get("creds", []):
        shape(
            credential,
            "id userId publicKey counter transports name created lastUsed",
            ("id", "userId", "publicKey", "counter"),
        )
        b64url(credential["id"])
        public_key = b64url(credential["publicKey"])
        from webauthn.helpers import decode_credential_public_key

        decode_credential_public_key(public_key)
        transports = credential.get("transports", [])
        require(
            isinstance(transports, list)
            and len(transports) <= 8
            and all(isinstance(v, str) and len(v) <= 16 for v in transports),
            "TRANSPORTS",
        )
        add(
            "identity.passkeys",
            credential["id"],
            credential["userId"],
            public_key,
            integer(credential["counter"], 4294967295),
            transports,
            credential.get("name"),
            timestamp(credential.get("created")),
            timestamp(credential.get("lastUsed")),
        )
    for link in db.get("deviceLinks", []):
        shape(link, "h userId created exp", ("h", "userId", "created", "exp"))
        add(
            "identity.device_links",
            digest(link["h"]),
            link["userId"],
            timestamp(link["created"]),
            timestamp(link["exp"]),
        )
    for sub in db.get("subs", []):
        shape(
            sub,
            "userId endpoint keys deviceId created",
            ("userId", "endpoint", "keys", "created"),
        )
        shape(sub["keys"], "p256dh auth", ("p256dh", "auth"))
        add(
            "notifications.subscriptions",
            text(sub["endpoint"]),
            sub["userId"],
            text(sub["keys"]["p256dh"]),
            text(sub["keys"]["auth"]),
            sub.get("deviceId"),
            timestamp(sub["created"]),
        )

    cfg = (
        shape(
            read("coach.json"),
            "enabled provider authMode community caps maxMessageLen maxOutputTokens auth models model providerOptions boundUid daily log",
        )
        if "coach.json" in files
        else {}
    )
    selected = cfg.get("provider", "fixture")
    require(selected in PROVIDERS, "PROVIDER")
    caps = shape(cfg.get("caps", {}), "perProfileDaily instanceDaily")
    auth = cfg.get("auth", {})
    if isinstance(auth, dict) and "data" in auth:
        auth = {selected: auth}
    bound = cfg.get("boundUid", {})
    if isinstance(bound, str):
        bound = {selected: bound}
    models = dict(shape(cfg.get("models", {}), " ".join(PROVIDERS)))
    if "model" in cfg:
        models.setdefault(selected, cfg["model"])
    shape(auth, " ".join(PROVIDERS))
    shape(bound, " ".join(PROVIDERS))
    options = shape(cfg.get("providerOptions", {}), " ".join(PROVIDERS))
    secret_bytes = (source / "secret").read_bytes()
    secret_value = secret_bytes.decode("utf-8").rstrip("\n")
    require(
        32 <= len(secret_bytes) <= 4096
        and 32 <= len(secret_value) <= 4096
        and not any(c in secret_value for c in ("\x00", "\n", "\r")),
        "SECRET",
    )
    secret = secret_value.strip()
    require(len(secret) >= 32, "SECRET")
    # The key is preserved separately from future session signing-key rotation (Q1).
    copies["coach-secret"] = "secret"
    copies["session-secret"] = "secret"
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    secret_files = SecretFiles(
        key=HKDF(
            algorithm=hashes.SHA256(), length=32, salt=b"", info=b"opengym-coach-v1"
        ).derive(secret.encode())
    )
    for provider in PROVIDERS:
        reference = None
        opts = shape(options.get(provider, {}), "baseUrl headers")
        if provider in auth and provider not in DEFERRED:
            record = auth[provider]
            require(
                record.get("type") == "apikey"
                and secret_files.decrypt(record) is not None,
                "COACH_CREDENTIAL",
            )
            reference = f"coach-key-{hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:32]}.json"
            copies[f"data/{reference}"] = record
        add(
            "coach.provider_settings",
            provider,
            models.get(provider),
            opts,
            reference,
            bound.get(provider),
        )
    add(
        "coach.settings",
        1,
        boolean(cfg.get("enabled", False)),
        selected,
        cfg.get("authMode", "instance"),
        boolean(cfg.get("community", False)),
        integer(caps.get("perProfileDaily", 10)),
        integer(caps.get("instanceDaily", 0)),
        integer(cfg.get("maxMessageLen", 1000)),
        integer(cfg.get("maxOutputTokens", 16000)),
    )

    def usage(table, value, owner=()):
        if value is not None:
            shape(value, "date count", ("date", "count"))
            add(table, *owner, day(value["date"]), integer(value["count"]))

    usage("coach.instance_daily_usage", cfg.get("daily"))
    for owner, record in records.items():
        add("coach.profile_state", owner, boolean(record.get("share", False)), 0)
        usage("coach.daily_usage", record.get("daily"), (owner,))
        history = record.get("history", [])
        require(isinstance(history, list) and len(history) <= 20, "COACH_HISTORY")
        for event in history:
            shape(
                event,
                "id kind trigger outcome errorClass at reading accepted rejected",
                ("kind", "outcome", "at"),
            )
            details = {
                key: event[key]
                for key in ("trigger", "reading", "accepted", "rejected")
                if key in event
            }
            add(
                "coach.history_events",
                len(rows["coach.history_events"]) + 1,
                owner,
                event.get("id"),
                event["kind"],
                event["outcome"],
                event.get("errorClass"),
                timestamp(event["at"]),
                details,
            )
        if record.get("current") is not None:
            job = shape(
                record["current"],
                "id kind state startedAt trigger",
                ("id", "kind", "state", "startedAt"),
            )
            # Node's durable current record omits trigger; no invented manual/scheduled value.
            require("trigger" in job, "JOB_TRIGGER_UNREPRESENTABLE")
            add(
                "coach.jobs",
                owner,
                job["id"],
                job["kind"],
                job["trigger"],
                job["state"],
                timestamp(job["startedAt"]),
                0,
            )
        if record.get("pending") is not None:
            pending = record["pending"]
            require(
                isinstance(pending, dict)
                and "createdAt" in pending
                and "planHash" in pending
                and "iteration" in pending,
                "PROPOSAL",
            )
            integer(pending["createdAt"])
            integer(pending["expiresAt"])
            integer(pending["iteration"])
            add("coach.pending_proposals", owner, pending)
    log = cfg.get("log", [])
    require(isinstance(log, list) and len(log) <= 100, "COACH_LOG")
    for event in log:
        shape(
            event,
            "at kind trigger outcome errorClass ms detail uid",
            ("at", "kind", "trigger", "outcome", "ms"),
        )
        # The delivered SQL result contract intentionally has no personal UID/detail storage.
        require(
            event.get("uid") is None and event.get("detail") in (None, {}),
            "INSTANCE_RESULT_UNREPRESENTABLE",
        )
        add(
            "coach.instance_results",
            len(rows["coach.instance_results"]) + 1,
            timestamp(event["at"]),
            event["kind"],
            event["trigger"],
            event["outcome"],
            event.get("errorClass"),
            integer(event["ms"]),
            {},
        )
    if "audit.log" in files:
        consumed.add("audit.log")
        for line in (source / "audit.log").read_bytes().splitlines():
            if not line:
                continue
            event = shape(
                strict_json(line),
                "id ts ev ok uid tgt name tname msg act ip",
                ("id", "ts", "ev", "ok"),
            )
            add(
                "audit.events",
                integer(event["id"]),
                timestamp(event["ts"]),
                text(event["ev"]),
                boolean(event["ok"]),
                *(
                    event.get(key)
                    for key in ("uid", "tgt", "name", "tname", "msg", "act", "ip")
                ),
            )
    for name in files:
        if name.startswith("coach-auth-") and name.endswith(".json"):
            owner = name[11:-5]
            require(
                owner in users and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", owner),
                "SECRET_OWNER",
            )
            record = read(name)
            if selected not in DEFERRED:
                require(
                    record.get("type") == "apikey"
                    and secret_files.decrypt(record) is not None,
                    "COACH_CREDENTIAL",
                )
                copies[f"data/{name}"] = name
        elif name == "vapid.json":
            record = shape(
                read(name), "publicKey privateKey", ("publicKey", "privateKey")
            )
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                PublicFormat,
            )

            private_bytes = b64url(record["privateKey"])
            require(len(private_bytes) == 32, "VAPID")
            private = ec.derive_private_key(
                int.from_bytes(private_bytes, "big"), ec.SECP256R1()
            )
            require(
                private.public_key().public_bytes(
                    Encoding.X962, PublicFormat.UncompressedPoint
                )
                == b64url(record["publicKey"]),
                "VAPID",
            )
            copies[f"data/{name}"] = name
        elif name.startswith("uploads/"):
            parts = name.split("/")
            require(
                len(parts) == 3
                and parts[1] in users
                and re.fullmatch(r"[A-Za-z0-9_-]+", parts[1]),
                "MEDIA_OWNER",
            )
            if parts[2] == ".gc.json":
                require(isinstance(read(name), dict), "MEDIA_GC")
            else:
                match = re.fullmatch(
                    r"([a-f0-9]{64})\.(jpg|png|gif|webp|mp4|webm)", parts[2]
                )
                require(match is not None and match[1] == files[name], "MEDIA_HASH")
                consumed.add(name)
            copies[f"data/{name}"] = name
        elif name in {"db.json.bak"}:
            # Retained only in the protected origin, never an alternate live authority.
            consumed.add(name)
    require(consumed == files.keys(), "UNMAPPED_FILE")
    return rows, copies


async def target_guard(connection, target_id, kind="import"):
    require(
        await connection.fetchval(
            "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"
        )
        == f"opengym-{kind}:{target_id}",
        "TARGET_OWNERSHIP",
    )
    require(
        not await connection.fetchval(
            "SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"
        ),
        "TARGET_EXPOSED",
    )
    require(
        await connection.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
        )
        == 0,
        "TARGET_IN_USE",
    )
    require(
        await connection.fetchval("SELECT version_num FROM public.alembic_version")
        == "p004_audit",
        "TARGET_SCHEMA",
    )
    for table in (*TABLES, "administration.deletion_tasks"):
        if table in {"coach.settings", "coach.provider_settings"}:
            continue
        require(
            not await connection.fetchval(f"SELECT EXISTS(SELECT 1 FROM {table})"),
            "TARGET_NOT_EMPTY",
        )
    require(
        await connection.fetchval(
            "SELECT count(*) FROM coach.settings WHERE id=1 AND NOT enabled AND provider='fixture' AND auth_mode='instance' AND NOT community AND per_profile_daily=10 AND instance_daily=0 AND max_message_len=1000 AND max_output_tokens=16000"
        )
        == 1,
        "TARGET_NOT_EMPTY",
    )
    require(
        await connection.fetchval(
            "SELECT count(*) FROM coach.provider_settings WHERE provider=ANY($1::text[]) AND model IS NULL AND options='{}' AND secret_ref IS NULL AND bound_owner_id IS NULL",
            list(PROVIDERS),
        )
        == 7,
        "TARGET_NOT_EMPTY",
    )


def sql_values(columns, row):
    return [
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        if column in JSON_COLUMNS
        else value
        for column, value in zip(columns, row, strict=True)
    ]


async def insert_compare(connection, rows):
    for table, fields in TABLES.items():
        columns = fields.split()
        if table in {"coach.settings", "coach.provider_settings"}:
            await connection.execute(f"DELETE FROM {table}")
        identity = " OVERRIDING SYSTEM VALUE" if table in SEQUENCES else ""
        placeholders = ",".join(f"${index + 1}" for index in range(len(columns)))
        for row in rows[table]:
            await connection.execute(
                f"INSERT INTO {table} ({','.join(columns)}){identity} VALUES ({placeholders})",
                *sql_values(columns, row),
            )
    for table, fields in TABLES.items():
        columns = fields.split()
        require(
            await connection.fetchval(f"SELECT count(*) FROM {table}")
            == len(rows[table]),
            "EQUIVALENCE",
        )
        # Native jsonb equality preserves types/nulls while accepting equivalent numeric notation.
        conditions = " AND ".join(
            f"{column} IS NOT DISTINCT FROM ${index + 1}"
            for index, column in enumerate(columns)
        )
        for row in rows[table]:
            require(
                await connection.fetchval(
                    f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {conditions})",
                    *sql_values(columns, row),
                ),
                "EQUIVALENCE",
            )
    for table, (column, sequence) in SEQUENCES.items():
        next_value = (
            await connection.fetchval(f"SELECT max({column}) FROM {table}") or 0
        ) + 1
        # Unlike setval, RESTART rolls back with the import transaction.
        await connection.execute(f"ALTER SEQUENCE {sequence} RESTART WITH {next_value}")


def write_file(path, data):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    require(path.read_bytes() == data, "FILE_EQUIVALENCE")
    for directory in (path.parent, *missing):
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


async def import_source(config_path, source_path, target_id):
    report_root = None
    configured = False
    result = {"code": "IMPORT_BLOCKED", "reason": "CONFIG"}
    try:
        require(
            isinstance(target_id, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", target_id),
            "TARGET_ID",
        )
        config = shape(
            strict_json(Path(config_path).read_bytes()),
            "target_id target_root admin_uids",
            ("target_id", "target_root", "admin_uids"),
        )
        require(
            config["target_id"] == target_id and isinstance(config["admin_uids"], list),
            "CONFIG",
        )
        root = Path(config["target_root"])
        private_directory(root)
        report_root = root
        configured = True
        destination = root / target_id
        require(not os.path.lexists(destination), "TARGET_EXISTS")
        source = Path(source_path)
        require(
            not source.is_relative_to(root) and not root.is_relative_to(source),
            "PATH_OVERLAP",
        )
        files = inventory(source)
        rows, copies = plan(source, files, config["admin_uids"])
        target = load_database("bootstrap")
        connection = await asyncpg.connect(
            host=target.host,
            database=target.database,
            user=target.user,
            password=target.password,
            ssl=False,
            timeout=5,
            command_timeout=10,
        )
        try:
            require(
                await connection.fetchval(
                    "SELECT pg_try_advisory_lock($1)", PLATFORM_LOCK_KEY
                ),
                "LOCKED",
            )
            async with connection.transaction():
                await target_guard(connection, target_id)
                # Settings references providers; clear its default row before replacing providers.
                await connection.execute("DELETE FROM coach.settings")
                await insert_compare(connection, rows)
                require(inventory(source) == files, "SOURCE_CHANGED")
                destination.mkdir(mode=0o700)
                for name, value in copies.items():
                    content = (
                        (source / value).read_bytes()
                        if isinstance(value, str)
                        else json.dumps(value).encode()
                    )
                    write_file(destination / name, content)
                require(inventory(source) == files, "SOURCE_CHANGED")
            # A crash or uncertain commit never writes this completion marker or opens access.
            result = {
                "code": "IMPORT_OK",
                "tables": {table: len(values) for table, values in rows.items()},
                "source_sha256": hashlib.sha256(
                    json.dumps(files, sort_keys=True).encode()
                ).hexdigest(),
                "access": "quarantined",
                "q6": "claude/codex unavailable",
            }
            write_file(destination / "import.json", json.dumps(result).encode())
        finally:
            await connection.close(timeout=5)
    except Blocked as error:
        result = {"code": "IMPORT_BLOCKED", "reason": str(error)}
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        UnicodeError,
        OverflowError,
        RecursionError,
    ):
        result = {"code": "IMPORT_BLOCKED", "reason": "UNREPRESENTABLE_OR_IO"}
    except Exception:  # noqa: BLE001 -- private CLI boundary, never SQL/values/paths
        result = {"code": "IMPORT_BLOCKED", "reason": "DATABASE_OR_CREDENTIAL"}
    if report_root is not None:
        try:
            write_file(
                report_root / f"import-report-{secrets.token_hex(8)}.json",
                json.dumps(result).encode(),
            )
        except OSError:
            return 1, {"code": "IMPORT_BLOCKED", "reason": "REPORT_IO"}
    return (0 if result["code"] == "IMPORT_OK" else 1 if configured else 2), {
        "code": result["code"],
        **({"reason": result["reason"]} if "reason" in result else {}),
    }
