"""Synthetic Database implementation in incremental 4.2 delivery."""

import asyncio
import os
import ssl
from contextlib import asynccontextmanager

import asyncpg
from pydantic import BaseModel, ConfigDict, Field, SecretStr

_DRIVER_ERRORS = (
    asyncpg.PostgresError,
    asyncpg.InterfaceError,
    asyncpg.InternalClientError,
    OSError,
    ValueError,
    TypeError,
    RuntimeError,
)


class _Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)

    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1, max_length=63)
    user: str = Field(min_length=1, max_length=63)
    password: SecretStr
    tls: bool = True
    ca_file: str | None = None
    min_size: int = Field(default=1, ge=1, le=16)
    max_size: int = Field(default=4, ge=1, le=16)
    connect_timeout: float = Field(default=5, gt=0, le=30)
    acquire_timeout: float = Field(default=5, gt=0, le=30)
    statement_timeout: float = Field(default=5, gt=0, le=30)
    command_timeout: float = Field(default=6, gt=0, le=60)
    lock_timeout: float = Field(default=2, gt=0, le=30)
    close_timeout: float = Field(default=10, gt=0, le=30)


def _configuration(raw):
    try:
        settings = _Settings.model_validate(raw)
        if settings.min_size > settings.max_size:
            raise ValueError
        synthetic = (
            os.environ.get("FOUNDATION_DB_HOST") == "foundation-db"
            and os.environ.get("FOUNDATION_DB_NAME") == "python_foundation_test"
            and settings.database == "python_foundation_test"
        )
        private_destination = (
            settings.host == "foundation-db" and settings.port == 5432
        ) or (
            settings.host == "127.0.0.1"
            and settings.user == "python_foundation_pool_runtime"
        )
        if not settings.tls and (
            not synthetic or not private_destination or settings.ca_file is not None
        ):
            raise ValueError
        context = (
            ssl.create_default_context(cafile=settings.ca_file)
            if settings.tls
            else False
        )
        return settings, context
    except ValueError, OSError:
        pass
    raise ValueError("DATABASE_CONFIG_INVALID")


class DatabaseError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code
        if code == "DATABASE_COMMIT_OUTCOME_UNKNOWN":
            self.commit_outcome = "unknown"


def _discard(connection):
    try:
        connection.terminate()
    except asyncpg.InterfaceError:
        # A broken transport may already have detached this pool proxy.
        pass


class _Handle:
    def __init__(self, connection):
        self._connection = connection
        self._failed = False
        self._active = True

    async def _query(self, operation, sql, args):
        if not self._active:
            raise DatabaseError("DATABASE_HANDLE_EXPIRED")
        if self._failed:
            raise DatabaseError("DATABASE_TRANSACTION_ABORTED")
        try:
            return await operation(sql, *args)
        except asyncio.CancelledError:
            self._failed = True
            raise
        except _DRIVER_ERRORS:
            self._failed = True
        raise DatabaseError("DATABASE_QUERY_FAILED")

    async def execute(self, sql, *args):
        return await self._query(self._connection.execute, sql, args)

    async def fetch(self, sql, *args):
        return await self._query(self._connection.fetch, sql, args)


class Database:
    def __init__(self, pool, settings):
        self._pool = pool
        self._settings = settings
        self._closing = False
        self._closed = asyncio.Event()

    @classmethod
    async def open(cls, settings):
        settings, context = _configuration(settings)
        return await cls._open(settings, context)

    @classmethod
    async def open_platform(cls):
        from opengym_platform.core.platform_settings import load_database

        target = load_database("runtime")
        settings = _Settings(
            host=target.host,
            port=5432,
            database=target.database,
            user=target.user,
            password=SecretStr(target.password),
            tls=False,
        )
        return await cls._open(settings, False)

    @classmethod
    async def _open(cls, settings, context):
        try:
            pool = await asyncpg.create_pool(
                host=settings.host,
                port=settings.port,
                database=settings.database,
                user=settings.user,
                password=settings.password.get_secret_value(),
                ssl=context,
                min_size=settings.min_size,
                max_size=settings.max_size,
                timeout=settings.connect_timeout,
                command_timeout=settings.command_timeout,
                server_settings={
                    "statement_timeout": str(
                        max(1, int(settings.statement_timeout * 1000))
                    ),
                    "lock_timeout": str(max(1, int(settings.lock_timeout * 1000))),
                },
            )
            return cls(pool, settings)
        except _DRIVER_ERRORS:
            code = "DATABASE_CONNECT_FAILED"
        raise DatabaseError(code)

    @asynccontextmanager
    async def _lease(self):
        if self._closing:
            raise DatabaseError("DATABASE_CLOSED")
        code = "DATABASE_ACQUIRE_FAILED"
        try:
            connection = await self._pool.acquire(
                timeout=self._settings.acquire_timeout
            )
        except TimeoutError:
            code = "DATABASE_ACQUIRE_TIMEOUT"
        except _DRIVER_ERRORS:
            code = "DATABASE_ACQUIRE_FAILED"
        else:
            try:
                if self._closing:
                    raise DatabaseError("DATABASE_CLOSED")
                yield connection
            finally:
                try:
                    await self._pool.release(
                        connection, timeout=self._settings.command_timeout
                    )
                except asyncio.CancelledError:
                    _discard(connection)
                    raise
                except _DRIVER_ERRORS:
                    # Discard reset failures without replacing the operation's known outcome.
                    _discard(connection)
            return
        raise DatabaseError(code)

    async def execute(self, sql, *args):
        async with self._lease() as connection:
            return await _Handle(connection).execute(sql, *args)

    async def fetch(self, sql, *args):
        async with self._lease() as connection:
            return await _Handle(connection).fetch(sql, *args)

    @asynccontextmanager
    async def transaction(self, owner_id=None):
        async with self._lease() as connection:
            transaction = connection.transaction()
            started = False
            try:
                await transaction.start()
                started = True
            except asyncio.CancelledError:
                _discard(connection)
                raise
            except _DRIVER_ERRORS:
                _discard(connection)
            if not started:
                raise DatabaseError("DATABASE_TRANSACTION_START_FAILED")
            handle = _Handle(connection)
            try:
                await handle.execute(
                    "SELECT set_config('app.owner_id', $1, true)", owner_id or ""
                )
                try:
                    yield handle
                    if handle._failed:
                        raise DatabaseError("DATABASE_TRANSACTION_ABORTED")
                finally:
                    handle._active = False
            except BaseException:
                try:
                    async with asyncio.timeout(self._settings.command_timeout):
                        await transaction.rollback()
                    if connection.is_in_transaction():
                        _discard(connection)
                except (asyncio.CancelledError, *_DRIVER_ERRORS):
                    _discard(connection)
                raise
            # A rollback attempt cannot establish the result after COMMIT was sent.
            code = "DATABASE_COMMIT_OUTCOME_UNKNOWN"
            try:
                await transaction.commit()
                return
            except asyncio.CancelledError as cancellation:
                _discard(connection)
                cancellation.commit_outcome = "unknown"  # type: ignore[attr-defined]
                raise
            except (
                asyncpg.IntegrityConstraintViolationError,
                asyncpg.SerializationError,
                asyncpg.DeadlockDetectedError,
            ):
                _discard(connection)
                code = "DATABASE_TRANSACTION_ABORTED"
            except _DRIVER_ERRORS:
                _discard(connection)
            raise DatabaseError(code)

    async def close(self):
        if self._closing:
            await self._closed.wait()
            return
        self._closing = True
        code = "DATABASE_CLOSE_FAILED"
        try:
            try:
                async with asyncio.timeout(self._settings.close_timeout):
                    await self._pool.close()
                return
            except asyncio.CancelledError:
                self._pool.terminate()
                raise
            except TimeoutError:
                code = "DATABASE_CLOSE_TIMEOUT"
            except _DRIVER_ERRORS:
                code = "DATABASE_CLOSE_FAILED"
            self._pool.terminate()
            raise DatabaseError(code)
        finally:
            self._closed.set()
