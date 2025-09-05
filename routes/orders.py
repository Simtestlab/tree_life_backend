from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db
from services.orders import order_tree_safely, cancel_tree_order

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderRequest(BaseModel):
    tree_name: str
    person_id: int


class CancelRequest(BaseModel):
    person_id: int


@router.post("/tree", status_code=200)
async def place_order(req: OrderRequest):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    res = await order_tree_safely(pool, req.tree_name, req.person_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return {"success": True, "tree_id": res.get("tree_id")}


@router.delete("/cancel/{person_id}", status_code=200)
async def cancel_order(person_id: int):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    res = await cancel_tree_order(pool, person_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return {"success": True, "tree_id": res.get("tree_id")}
