"""Order-related DB helpers that perform transactional, concurrency-safe operations."""
from typing import Optional
import asyncpg


async def order_tree_safely(pool: asyncpg.pool.Pool, tree_name: str, person_id: int) -> dict:
    """Resolve tree by name and order it for the person in a transaction.

    Returns {'success': bool, 'tree_id': int?, 'message': str?}
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock the tree row
            tree = await conn.fetchrow(
                "SELECT id, stock_available, persons_ordered FROM trees WHERE name = $1 FOR UPDATE",
                tree_name,
            )
            if tree is None:
                return {"success": False, "message": "Tree not found"}

            tree_id = tree["id"]
            if tree["stock_available"] <= tree["persons_ordered"]:
                return {"success": False, "message": "Tree out of stock"}

            # Lock the person row
            person = await conn.fetchrow(
                "SELECT id, ordered_tree FROM persons WHERE id = $1 FOR UPDATE",
                person_id,
            )
            if person is None:
                return {"success": False, "message": "Person not found"}

            if person["ordered_tree"] is not None:
                return {"success": False, "message": "Person already has an ordered tree"}

            # Perform updates
            await conn.execute("UPDATE trees SET persons_ordered = persons_ordered + 1 WHERE id = $1", tree_id)
            await conn.execute("UPDATE persons SET ordered_tree = $1 WHERE id = $2", tree_id, person_id)
            return {"success": True, "tree_id": tree_id}


async def cancel_tree_order(pool: asyncpg.pool.Pool, person_id: int) -> dict:
    """Cancel a person's tree order in a transaction.

    Returns {'success': bool, 'tree_id': int?, 'message': str?}
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            person = await conn.fetchrow(
                "SELECT ordered_tree FROM persons WHERE id = $1 FOR UPDATE",
                person_id,
            )
            if person is None:
                return {"success": False, "message": "Person not found"}

            tree_id = person["ordered_tree"]
            if tree_id is None:
                return {"success": False, "message": "No order to cancel"}

            # Lock tree row and decrement safely
            tree = await conn.fetchrow("SELECT persons_ordered FROM trees WHERE id = $1 FOR UPDATE", tree_id)
            if tree is None:
                # Tree missing; still clear person's ordered_tree
                await conn.execute("UPDATE persons SET ordered_tree = NULL WHERE id = $1", person_id)
                return {"success": True, "tree_id": tree_id, "message": "Order cancelled; tree record missing"}

            await conn.execute(
                "UPDATE trees SET persons_ordered = GREATEST(persons_ordered - 1, 0) WHERE id = $1", tree_id
            )
            await conn.execute("UPDATE persons SET ordered_tree = NULL WHERE id = $1", person_id)
            return {"success": True, "tree_id": tree_id}
