"""Tree-related DB helpers."""
from typing import List, Optional
import asyncpg


async def get_available_trees(pool: asyncpg.pool.Pool) -> List[dict]:
    """Return list of trees where stock_available > persons_ordered."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, stock_available, persons_ordered, created_at, updated_at
            FROM trees
            WHERE stock_available > persons_ordered
            ORDER BY id
            """
        )
        return [dict(r) for r in rows]
