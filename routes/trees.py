from fastapi import APIRouter, HTTPException
from typing import List

import db
from services.trees import get_available_trees
from models.persons import TreeOut

router = APIRouter(prefix="/trees", tags=["trees"])


@router.get("/available", response_model=List[TreeOut])
async def available_trees():
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    rows = await get_available_trees(pool)
    return rows
