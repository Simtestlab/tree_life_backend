"""Address-related DB helpers, including combined flow to optionally order a tree by name
and insert address only if ordering succeeds."""
from typing import Optional

import asyncpg

from services.persons import get_person_by_id, get_tree_by_id


async def insert_address(pool: asyncpg.pool.Pool, person_id: int, city: Optional[str], pin_code: Optional[str], state: Optional[str], district: Optional[str]) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO addresses (person_id, city, pin_code, state, district)
            VALUES ($1,$2,$3,$4,$5)
            RETURNING id
            """,
            person_id, city, pin_code, state, district,
        )
        return dict(row) if row is not None else {}


async def order_tree_by_name(pool: asyncpg.pool.Pool, tree_name: str, person_id: int) -> dict:
    """Resolve tree by name and perform a safe order operation.

    This is a simplified version that checks stock and updates counters in two steps; in production prefer a DB-side transaction/RPC.
    Returns dict with success flag and message.
    """
    async with pool.acquire() as conn:
        tree = await conn.fetchrow("SELECT id, stock_available, persons_ordered FROM trees WHERE name = $1", tree_name)
        if tree is None:
            return {"success": False, "message": "Tree not found"}
        tree_id = tree["id"]
        stock_available = tree["stock_available"]
        persons_ordered = tree["persons_ordered"]
        if stock_available <= persons_ordered:
            return {"success": False, "message": "Tree out of stock"}

        # perform update
        await conn.execute("UPDATE trees SET persons_ordered = persons_ordered + 1 WHERE id = $1", tree_id)
        # set ordered_tree on person
        await conn.execute("UPDATE persons SET ordered_tree = $1 WHERE id = $2", tree_id, person_id)
        return {"success": True, "tree_id": tree_id}
