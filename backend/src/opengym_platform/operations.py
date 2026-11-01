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

    result = {
        "healthy": False,
        "database": "unavailable",
        "schema": "unknown",
        "audit_degraded": audit.degraded,
        "logging": await asyncio.to_thread(diagnostics.state),
        "pool": database.pool_status(),
        "backup": {"state": "missing", "verified": False},
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
    # Missing backup remains degraded until S10 supplies verified recovery evidence.
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
    parser.add_argument("command", choices=["diagnose"])
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    code, result = diagnose(args.config)
    print(json.dumps(result, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
