import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.getenv("POSTGRES_DSN"),
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