import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.getenv("POSTGRES_DSN")
        if not dsn:
            raise ValueError(
                "POSTGRES_DSN environment variable is not set. "
                "Set it to a valid PostgreSQL connection string, e.g.: "
                "postgresql://user:password@host:5432/dbname"
            )
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
    return _pool

async def close_pool(): 
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None