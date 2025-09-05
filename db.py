"""Async DB helper using asyncpg for connection pooling.

Provides connect(database_url), disconnect(), and a module-level `pool`.
"""
import asyncpg
from typing import Optional

pool: Optional[asyncpg.pool.Pool] = None


async def connect(database_url: str):
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)


async def disconnect():
    global pool
    if pool is not None:
        await pool.close()
        pool = None
