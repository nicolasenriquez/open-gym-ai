"""Non-operational 4.1 RED scaffold: leased SQL only, NOT a transaction yet."""

from contextlib import asynccontextmanager

import asyncpg


class _Handle:
    def __init__(self, connection):
        self._connection = connection

    async def execute(self, sql, *args):
        return await self._connection.execute(sql, *args)

    async def fetch(self, sql, *args):
        return await self._connection.fetch(sql, *args)


class Database:
    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def open(cls, settings):
        # No arbitrary destinations or driver options in this RED-only scaffold.
        if settings != {"max_size": 1}:
            raise ValueError("DATABASE_FOUNDATION_SETTINGS_ONLY")
        pool = await asyncpg.create_pool(
            host="foundation-db",
            port=5432,
            database="python_foundation_test",
            user="python_foundation_pool_runtime",
            password="synthetic-python-foundation-pool-only",
            ssl=False,
            min_size=1,
            max_size=1,
            timeout=5,
            command_timeout=5,
        )
        return cls(pool)

    async def fetch(self, sql, *args):
        async with self._pool.acquire(timeout=5) as connection:
            return await connection.fetch(sql, *args)

    @asynccontextmanager
    async def transaction(self, owner_id=None):
        # shortcut: only leases; 4.2 must add transaction/owner/error/handle guarantees.
        async with self._pool.acquire(timeout=5) as connection:
            yield _Handle(connection)

    async def close(self):
        # RED fixture teardown only; bounded graceful shutdown belongs to 4.2.
        self._pool.terminate()
