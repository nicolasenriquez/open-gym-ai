"""Private operator commands; no public diagnostic HTTP endpoint."""

import argparse
import asyncio
import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path


def diagnose(config):
    try:
        settings = json.loads(Path(config).read_text())
    except (OSError, ValueError, TypeError):
        return 2, {"code": "DIAGNOSTIC_CONFIG_INVALID"}
    try:
        if not isinstance(settings, dict) or set(settings) != {"diagnostic_socket"}:
            return 2, {"code": "DIAGNOSTIC_CONFIG_INVALID"}
        path = settings["diagnostic_socket"]
        if not isinstance(path, str) or not path.startswith("/") or len(path) > 100:
            return 2, {"code": "DIAGNOSTIC_CONFIG_INVALID"}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(4)
            client.connect(path)
            raw = bytearray()
            while chunk := client.recv(4096):
                raw.extend(chunk)
                if len(raw) > 8192:
                    raise ValueError
        status = json.loads(raw)
        return (0 if status["healthy"] else 1), status
    except (OSError, ValueError, KeyError, TypeError):
        return 1, {"code": "DIAGNOSTIC_UNAVAILABLE"}


async def status(database, audit, schema, diagnostics):
    from opengym_platform.core.database import DatabaseError
    from opengym_platform.core.maintenance import backup_status

    result = {
        "healthy": False,
        "database": "unavailable",
        "schema": "unknown",
        "audit_degraded": audit.degraded,
        "logging": await asyncio.to_thread(diagnostics.state),
        "pool": database.pool_status(),
        "backup": await asyncio.to_thread(backup_status),
    }
    try:
        async with asyncio.timeout(3):
            rows = await database.fetch(
                "SELECT version_num, current_setting('transaction_read_only') = 'off' "
                "AND NOT pg_is_in_recovery() AS writable FROM public.alembic_version LIMIT 2"
            )
        result["database"] = "writable" if rows and rows[0]["writable"] else "read_only"
        result["schema"] = (
            "current"
            if [r["version_num"] for r in rows] == [schema]
            else "incompatible"
        )
    except (DatabaseError, TimeoutError):
        pass
    result["healthy"] = (
        result["database"] == "writable"
        and result["schema"] == "current"
        and not result["audit_degraded"]
        and result["backup"]["state"] == "current"
        and result["logging"]["configured"]
        and not result["logging"]["degraded"]
        and result["logging"]["sink"] == "space_available"
    )
    return result


@asynccontextmanager
async def serve_status(database, audit, schema, diagnostics):
    path = os.environ.get("PLATFORM_DIAGNOSTIC_SOCKET")
    if not path:
        yield
        return
    if os.path.lexists(path):
        raise ValueError("DIAGNOSTIC_SOCKET_EXISTS")

    async def reply(reader, writer):
        try:
            async with asyncio.timeout(3.5):
                writer.write(
                    json.dumps(
                        await status(database, audit, schema, diagnostics)
                    ).encode()
                )
                await writer.drain()
        except (OSError, TimeoutError):
            pass
        finally:
            writer.close()

    # A stale or foreign path is never removed implicitly.
    server = await asyncio.start_unix_server(reply, path=path, cleanup_socket=True)
    os.chmod(path, 0o600)
    try:
        yield
    finally:
        server.close()
        await server.wait_closed()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["diagnose", "import", "capture-sql", "backup", "restore"]
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--source")
    parser.add_argument("--bundle")
    parser.add_argument("--target")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--reason", choices=["scheduled", "startup", "pre-migration"])
    args = parser.parse_args()
    if (args.bundle is not None and args.command != "restore") or (
        args.reason is not None and args.command != "backup"
    ):
        code, result = 2, {"code": "OPERATION_ARGUMENTS_INVALID"}
    elif args.command == "backup":
        import importlib.util

        if args.source or args.target or args.check_only or args.reason is None:
            code, result = 2, {"code": "BACKUP_ARGUMENTS_INVALID"}
        elif importlib.util.find_spec("opengym_platform.bundle") is None:
            code, result = 2, {"code": "BACKUP_TOOL_UNAVAILABLE"}
        else:
            from opengym_platform.bundle import publish

            code, result = asyncio.run(publish(args.config, args.reason))
    elif args.command == "restore":
        import importlib.util

        if args.source or args.check_only or not args.bundle or not args.target:
            code, result = 2, {"code": "RESTORE_ARGUMENTS_INVALID"}
        elif importlib.util.find_spec("opengym_platform.restore") is None:
            code, result = 2, {"code": "RESTORE_TOOL_UNAVAILABLE"}
        else:
            from opengym_platform.restore import restore

            code, result = asyncio.run(restore(args.config, args.bundle, args.target))
    elif args.command == "capture-sql":
        import importlib.util

        if args.source or args.target:
            code, result = 2, {"code": "BACKUP_ARGUMENTS_INVALID"}
        elif importlib.util.find_spec("opengym_platform.backup") is None:
            code, result = 2, {"code": "BACKUP_TOOL_UNAVAILABLE"}
        else:
            from opengym_platform.backup import capture

            code, result = asyncio.run(capture(args.config, args.check_only))
    elif args.check_only:
        code, result = 2, {"code": "OPERATION_ARGUMENTS_INVALID"}
    elif args.command == "import":
        import importlib.util

        if importlib.util.find_spec("opengym_platform.importer") is None:
            code, result = 2, {"code": "IMPORT_TOOL_UNAVAILABLE"}
        elif not args.source or not args.target:
            code, result = 2, {"code": "IMPORT_ARGUMENTS_INVALID"}
        else:
            from opengym_platform.importer import import_source

            code, result = asyncio.run(
                import_source(args.config, args.source, args.target)
            )
    elif args.source or args.target:
        code, result = 2, {"code": "DIAGNOSTIC_CONFIG_INVALID"}
    else:
        code, result = diagnose(args.config)
    print(json.dumps(result, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
