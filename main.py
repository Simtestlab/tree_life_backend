import os
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException

import db
from routes.persons import router as persons_router
from routes.trees import router as trees_router
from routes.orders import router as orders_router
from models.persons import PersonOut


app = FastAPI()

# include routers
app.include_router(persons_router)
app.include_router(trees_router)
app.include_router(orders_router)


@app.on_event("startup")
async def startup():
    # Read DATABASE_URL from env, fallback to your local postgres
    database_url = os.getenv("DATABASE_URL", "postgres://hari@localhost:5432/tree_life")
    await db.connect(database_url)


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.get("/", tags=["health"])
async def root():
    return {"message": "Hello World"}


@app.get("/users", response_model=List[PersonOut])
async def get_users():
    """Fetch all users (persons) from the database.

    Returns a list of persons with basic fields.
    """
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, first_name, last_name, email, phone, ordered_tree, created_at, updated_at
            FROM persons
            ORDER BY id
            """
        )

        # asyncpg Record is mapping-like, convert to dict
        return [dict(r) for r in rows]


# include routers
app.include_router(persons_router)

