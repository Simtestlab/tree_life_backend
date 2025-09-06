"""Person-related DB service helpers.

Keep functions small, testable, and production-ready (connection injection, parameterized SQL).
"""
from typing import Optional
import asyncpg


async def email_exists(pool: asyncpg.pool.Pool, email: str) -> bool:
    """Return True if a person with the given email exists.

    Uses a fast EXISTS query and parameterized arguments to avoid SQL injection.
    """
    async with pool.acquire() as conn:
        # Use SELECT EXISTS for minimal overhead
        row = await conn.fetchrow("SELECT EXISTS(SELECT 1 FROM persons WHERE email = $1)", email)
        if row is None:
            return False
        return bool(row[0])


async def insert_person(
    pool: asyncpg.pool.Pool,
    first_name: str,
    last_name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
) -> dict:
    """Insert a new person and return the created record as a dict.

    Raises asyncpg.UniqueViolationError on duplicate email if the DB enforces uniqueness.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO persons (first_name, last_name, email, phone)
            VALUES ($1, $2, $3, $4)
            RETURNING id, first_name, last_name, email, phone, ordered_tree, picture_filename, created_at, updated_at
            """,
            first_name,
            last_name,
            email,
            phone,
        )
        return dict(row) if row is not None else {}


async def get_person_by_id(pool: asyncpg.pool.Pool, person_id: int) -> Optional[dict]:
    """Fetch a person by id and return as dict, or None if not found."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, first_name, last_name, email, phone, ordered_tree, picture_filename, created_at, updated_at
            FROM persons
            WHERE id = $1
            """,
            person_id,
        )
        return dict(row) if row is not None else None


async def get_tree_by_id(pool: asyncpg.pool.Pool, tree_id: int) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, stock_available, persons_ordered, created_at, updated_at
            FROM trees
            WHERE id = $1
            """,
            tree_id,
        )
        return dict(row) if row is not None else None


async def get_addresses_by_person(pool: asyncpg.pool.Pool, person_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, person_id, city, pin_code, state, district, created_at, updated_at
            FROM addresses
            WHERE person_id = $1
            ORDER BY id
            """,
            person_id,
        )
        return [dict(r) for r in rows]


async def get_person_with_tree(pool: asyncpg.pool.Pool, person_id: int) -> Optional[dict]:
    """Return a combined object: person, optional tree, and addresses."""
    person = await get_person_by_id(pool, person_id)
    if person is None:
        return None

    tree = None
    if person.get("ordered_tree"):
        tree = await get_tree_by_id(pool, person["ordered_tree"])

    addresses = await get_addresses_by_person(pool, person_id)

    return {"person": person, "tree": tree, "addresses": addresses}


async def get_person_order_status(pool: asyncpg.pool.Pool, person_id: int) -> Optional[dict]:
    """Return dict with ordered_tree id or None if person not found."""
    person = await get_person_by_id(pool, person_id)
    if person is None:
        return None
    return {"hasOrdered": bool(person.get("ordered_tree")), "treeId": person.get("ordered_tree")}