"""One controlled migration chain; explicit deployment and synthetic entry guards."""

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

from opengym_platform.core.platform_settings import DatabaseTarget, load_database

# Session lock shared with migrator/import/restore for the whole platform.
LOCK_KEY = 728322
DATABASE = "opengym_platform_test"
BOOTSTRAP_USER = "opengym_platform_bootstrap"
BOOTSTRAP_PASSWORD = "synthetic-opengym-platform-only"
SCHEMA_OWNER = "opengym_schema_owner"
MIGRATOR = "opengym_migrator"
MIGRATOR_PASSWORD = "synthetic-opengym-platform-migrator-only"
RUNTIME = "opengym_api_runtime"
RUNTIME_PASSWORD = "synthetic-opengym-platform-runtime-only"


def _validate_target():
    expected = {
        "PLATFORM_DB_HOST": "platform-db",
        "PLATFORM_DB_PORT": "5432",
        "PLATFORM_DB_NAME": DATABASE,
        "PLATFORM_DB_USER": BOOTSTRAP_USER,
        "PLATFORM_DB_PASSWORD": BOOTSTRAP_PASSWORD,
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise ValueError("PLATFORM_MIGRATION_TARGET_REJECTED")


async def _bootstrap(target):
    database = target.database
    connection = await asyncpg.connect(
        host=target.host,
        port=5432,
        database=database,
        user=target.user,
        password=target.password,
        ssl=False,
        timeout=5,
        command_timeout=5,
    )
    try:
        if not await connection.fetchval("SELECT pg_try_advisory_lock($1)", LOCK_KEY):
            raise ValueError("PLATFORM_MIGRATION_LOCKED")
        async with connection.transaction():
            existing = {
                row["rolname"]
                for row in await connection.fetch(
                    "SELECT rolname FROM pg_roles WHERE rolname = ANY($1::text[])",
                    [MIGRATOR, RUNTIME],
                )
            }
            await connection.execute(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{SCHEMA_OWNER}') THEN
                        CREATE ROLE {SCHEMA_OWNER} NOLOGIN;
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opengym_identity_executor') THEN
                        CREATE ROLE opengym_identity_executor NOLOGIN;
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opengym_coach_executor') THEN
                        CREATE ROLE opengym_coach_executor NOLOGIN;
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{MIGRATOR}') THEN
                        CREATE ROLE {MIGRATOR} LOGIN;
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{RUNTIME}') THEN
                        CREATE ROLE {RUNTIME} LOGIN;
                    END IF;
                END $$;
                ALTER ROLE {SCHEMA_OWNER} NOSUPERUSER NOBYPASSRLS NOCREATEDB
                    NOCREATEROLE NOREPLICATION NOINHERIT;
                ALTER ROLE opengym_identity_executor NOLOGIN NOSUPERUSER NOBYPASSRLS
                    NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
                GRANT opengym_identity_executor TO {SCHEMA_OWNER};
                ALTER ROLE opengym_coach_executor NOLOGIN NOSUPERUSER NOBYPASSRLS
                    NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
                GRANT opengym_coach_executor TO {SCHEMA_OWNER};
                ALTER ROLE {MIGRATOR} NOSUPERUSER NOBYPASSRLS NOCREATEDB
                    NOCREATEROLE NOREPLICATION NOINHERIT;
                ALTER ROLE {RUNTIME} NOSUPERUSER NOBYPASSRLS NOCREATEDB
                    NOCREATEROLE NOREPLICATION NOINHERIT;
                REVOKE ALL ON DATABASE {database} FROM PUBLIC,
                    {SCHEMA_OWNER}, {MIGRATOR}, {RUNTIME};
                REVOKE ALL ON SCHEMA public FROM PUBLIC, {RUNTIME};
                ALTER SCHEMA public OWNER TO {SCHEMA_OWNER};
                GRANT CONNECT, CREATE ON DATABASE {database} TO {SCHEMA_OWNER};
                GRANT CONNECT ON DATABASE {database} TO {MIGRATOR}, {RUNTIME};
                GRANT {SCHEMA_OWNER} TO {MIGRATOR};
                DO $$ BEGIN
                    IF to_regclass('public.alembic_version') IS NOT NULL THEN
                        REVOKE ALL ON TABLE public.alembic_version FROM {RUNTIME};
                        GRANT USAGE ON SCHEMA public TO {RUNTIME};
                        GRANT SELECT ON TABLE public.alembic_version TO {RUNTIME};
                    END IF;
                END $$;
            """)
            for role, password in (
                (MIGRATOR, target.migrator_password),
                (RUNTIME, target.runtime_password),
            ):
                if role not in existing:
                    statement = await connection.fetchval(
                        "SELECT format('ALTER ROLE %I PASSWORD %L', $1::text, $2::text)",
                        role,
                        password,
                    )
                    await connection.execute(statement)
            memberships = await connection.fetchval(f"""
                SELECT count(*) FROM pg_auth_members m
                JOIN pg_roles member ON member.oid = m.member
                WHERE member.rolname IN ('{SCHEMA_OWNER}', '{MIGRATOR}', '{RUNTIME}',
                    'opengym_identity_executor', 'opengym_coach_executor')
                  AND NOT (member.rolname = '{MIGRATOR}' AND m.roleid = (
                      SELECT oid FROM pg_roles WHERE rolname = '{SCHEMA_OWNER}'
                  ))
                  AND NOT (member.rolname = '{SCHEMA_OWNER}' AND m.roleid IN (
                      SELECT oid FROM pg_roles WHERE rolname IN
                          ('opengym_identity_executor', 'opengym_coach_executor')
                  ))
            """)
            if memberships:
                raise ValueError("PLATFORM_MIGRATION_ROLES_REJECTED")
    finally:
        await connection.close(timeout=5)


def _upgrade(connection):
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).with_name("platform_migrations"))
    )
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def _up(target):
    from sqlalchemy import URL, text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        URL.create(
            "postgresql+asyncpg",
            username=target.user,
            password=target.password,
            host=target.host,
            port=5432,
            database=target.database,
        ),
        poolclass=NullPool,
        connect_args={
            "ssl": False,
            "timeout": 5,
            "command_timeout": 6,
            "server_settings": {
                "statement_timeout": "5000",
                "lock_timeout": "2000",
                "application_name": "opengym-platform-migrate",
            },
        },
    )
    try:
        async with engine.connect() as connection:
            locked = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
            )
            if not locked:
                raise ValueError("PLATFORM_MIGRATION_LOCKED")
            # End SQLAlchemy's implicit transaction, not the session advisory lock.
            await connection.commit()
            await connection.execute(text(f"SET ROLE {SCHEMA_OWNER}"))
            await connection.commit()
            await connection.run_sync(_upgrade)
    finally:
        await engine.dispose()


async def _run(action, target):
    async with asyncio.timeout(30):
        await (_bootstrap(target) if action == "bootstrap" else _up(target))


def main() -> int:
    arguments = sys.argv[1:]
    deployment = arguments[:1] == ["--deployment"]
    if deployment:
        arguments = arguments[1:]
    if len(arguments) != 1 or arguments[0] not in ("bootstrap", "up"):
        print(json.dumps({"code": "PLATFORM_MIGRATION_ARGUMENTS_REJECTED"}))
        return 1
    try:
        action = arguments[0]
        if deployment:
            target = load_database("bootstrap" if action == "bootstrap" else "migrator")
        else:
            _validate_target()
            target = DatabaseTarget(
                "platform-db",
                DATABASE,
                BOOTSTRAP_USER if action == "bootstrap" else MIGRATOR,
                BOOTSTRAP_PASSWORD if action == "bootstrap" else MIGRATOR_PASSWORD,
                MIGRATOR_PASSWORD,
                RUNTIME_PASSWORD,
            )
        asyncio.run(_run(action, target))
    except ValueError as error:
        allowed = {
            "PLATFORM_MIGRATION_TARGET_REJECTED",
            "PLATFORM_DATABASE_CONFIG_INVALID",
            "PLATFORM_MIGRATION_LOCKED",
            "PLATFORM_MIGRATION_ROLES_REJECTED",
        }
        code = str(error) if str(error) in allowed else "PLATFORM_MIGRATION_FAILED"
        print(json.dumps({"code": code}))
        return 1
    except Exception:  # noqa: BLE001
        # CLI boundary: arbitrary Alembic revision errors must never expose SQL/secrets.
        print(json.dumps({"code": "PLATFORM_MIGRATION_FAILED"}))
        return 1
    print(json.dumps({"code": f"PLATFORM_MIGRATION_{arguments[0].upper()}_OK"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
