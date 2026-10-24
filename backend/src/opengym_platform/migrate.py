"""Controlled migrations for the private disposable Foundation database only."""

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

# Session lock shared by bootstrap and up, held until the dedicated connection closes.
LOCK_KEY = 728322


def _validate_target():
    expected = {
        "FOUNDATION_DB_HOST": "foundation-db",
        "FOUNDATION_DB_PORT": "5432",
        "FOUNDATION_DB_NAME": "python_foundation_test",
        "FOUNDATION_DB_USER": "python_foundation_bootstrap",
        "FOUNDATION_DB_PASSWORD": "synthetic-python-foundation-only",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise ValueError("FOUNDATION_MIGRATION_TARGET_REJECTED")


async def _bootstrap():
    connection = await asyncpg.connect(
        host="foundation-db",
        port=5432,
        database="python_foundation_test",
        user="python_foundation_bootstrap",
        password="synthetic-python-foundation-only",
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        if not await connection.fetchval("SELECT pg_try_advisory_lock($1)", LOCK_KEY):
            raise ValueError("FOUNDATION_MIGRATION_LOCKED")
        async with connection.transaction():
            await connection.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'python_foundation_migrator') THEN
                        CREATE ROLE python_foundation_migrator LOGIN PASSWORD 'synthetic-python-foundation-migrator-only';
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'python_foundation_runtime') THEN
                        CREATE ROLE python_foundation_runtime LOGIN PASSWORD 'synthetic-python-foundation-runtime-only';
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'python_foundation_training') THEN
                        CREATE ROLE python_foundation_training LOGIN PASSWORD 'synthetic-python-foundation-training-only';
                    END IF;
                END $$;
                ALTER ROLE python_foundation_migrator NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
                ALTER ROLE python_foundation_runtime NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
                ALTER ROLE python_foundation_training NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
                REVOKE ALL ON DATABASE python_foundation_test FROM PUBLIC,
                    python_foundation_migrator, python_foundation_runtime, python_foundation_training;
                REVOKE ALL ON SCHEMA public FROM PUBLIC,
                    python_foundation_runtime, python_foundation_training;
                DO $$ BEGIN
                    IF to_regnamespace('foundation') IS NOT NULL THEN
                        REVOKE ALL ON SCHEMA foundation FROM PUBLIC,
                            python_foundation_runtime, python_foundation_training;
                        GRANT USAGE ON SCHEMA foundation TO
                            python_foundation_runtime, python_foundation_training;
                    END IF;
                END $$;
                DO $$ BEGIN
                    IF to_regclass('public.alembic_version') IS NOT NULL THEN
                        REVOKE ALL ON TABLE public.alembic_version FROM PUBLIC,
                            python_foundation_runtime, python_foundation_training;
                        IF EXISTS (SELECT FROM public.alembic_version
                            WHERE version_num = '0002_health_readiness') THEN
                            GRANT USAGE ON SCHEMA public TO python_foundation_runtime;
                            GRANT SELECT ON TABLE public.alembic_version TO python_foundation_runtime;
                        END IF;
                    END IF;
                END $$;
                ALTER SCHEMA public OWNER TO python_foundation_migrator;
                GRANT CONNECT, CREATE ON DATABASE python_foundation_test TO python_foundation_migrator;
                GRANT CONNECT ON DATABASE python_foundation_test TO python_foundation_runtime, python_foundation_training;
            """)
            memberships = await connection.fetchval("""
                SELECT count(*) FROM pg_auth_members
                WHERE member IN (SELECT oid FROM pg_roles WHERE rolname IN (
                    'python_foundation_migrator', 'python_foundation_runtime', 'python_foundation_training'
                ))
            """)
            if memberships:
                raise ValueError("FOUNDATION_MIGRATION_ROLES_REJECTED")
    finally:
        await connection.close(timeout=5)


def _upgrade(connection):
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).with_name("migrations"))
    )
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def _up():
    from sqlalchemy import URL, text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        URL.create(
            "postgresql+asyncpg",
            username="python_foundation_migrator",
            password="synthetic-python-foundation-migrator-only",
            host="foundation-db",
            port=5432,
            database="python_foundation_test",
        ),
        poolclass=NullPool,
        connect_args={
            "ssl": False,
            "timeout": 5,
            "command_timeout": 6,
            "server_settings": {
                "statement_timeout": "5000",
                "lock_timeout": "2000",
                "application_name": "opengym-foundation-migrate",
            },
        },
    )
    try:
        async with engine.connect() as connection:
            locked = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
            )
            if not locked:
                raise ValueError("FOUNDATION_MIGRATION_LOCKED")
            # End SQLAlchemy's implicit transaction, not the session advisory lock.
            await connection.commit()
            await connection.run_sync(_upgrade)
    finally:
        await engine.dispose()


async def _run(action):
    async with asyncio.timeout(30):
        await (_bootstrap() if action == "bootstrap" else _up())


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("bootstrap", "up"):
        print(json.dumps({"code": "FOUNDATION_MIGRATION_ARGUMENTS_REJECTED"}))
        return 1
    try:
        _validate_target()
        asyncio.run(_run(sys.argv[1]))
    except ValueError as error:
        allowed = {
            "FOUNDATION_MIGRATION_TARGET_REJECTED",
            "FOUNDATION_MIGRATION_LOCKED",
            "FOUNDATION_MIGRATION_ROLES_REJECTED",
        }
        code = str(error) if str(error) in allowed else "FOUNDATION_MIGRATION_FAILED"
        print(json.dumps({"code": code}))
        return 1
    except Exception:  # noqa: BLE001
        # CLI boundary: arbitrary Alembic revision errors must never expose SQL/secrets.
        print(json.dumps({"code": "FOUNDATION_MIGRATION_FAILED"}))
        return 1
    print(json.dumps({"code": f"FOUNDATION_MIGRATION_{sys.argv[1].upper()}_OK"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
