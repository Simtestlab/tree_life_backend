from fastapi import APIRouter, HTTPException, Query
from typing import List
from pydantic import EmailStr

import db
from services.persons import email_exists as svc_email_exists, insert_person
from models.persons import PersonOut, PersonCreate, EmailExistsOut, PersonWithTreeOut

from models.persons import PersonHasOrderOut
from models.persons import AddressCreate, AddressInsertOut, AddressOut

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/email-exists", response_model=EmailExistsOut)
async def email_exists(email: EmailStr = Query(..., description="Email to check for existence")):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    exists = await svc_email_exists(pool, str(email))
    return EmailExistsOut(exists=bool(exists))


@router.post("/", response_model=PersonOut, status_code=201)
async def create_person(payload: PersonCreate):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    if payload.email:
        exists = await svc_email_exists(pool, str(payload.email))
        if exists:
            raise HTTPException(status_code=409, detail="Email already exists")

    try:
        created = await insert_person(
            pool, payload.first_name, payload.last_name, str(payload.email) if payload.email else None, payload.phone
        )
        return created
    except Exception as exc:
        if exc.__class__.__name__ == "UniqueViolationError":
            raise HTTPException(status_code=409, detail="Email already exists")
        raise HTTPException(status_code=500, detail=str(exc))



@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: int):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    from services.persons import get_person_by_id

    person = await get_person_by_id(pool, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person



@router.get("/{person_id}/tree", response_model=PersonWithTreeOut)
async def get_person_tree(person_id: int):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    from services.persons import get_person_with_tree

    result = await get_person_with_tree(pool, person_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return result



@router.get("/{person_id}/has-order", response_model=PersonHasOrderOut)
async def get_person_has_order(person_id: int):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    from services.persons import get_person_order_status

    status = await get_person_order_status(pool, person_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return status

@router.post("/{person_id}/addresses", response_model=AddressInsertOut, status_code=201)
async def create_address_for_person(person_id: int, payload: AddressCreate):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    # verify person exists
    from services.persons import get_person_by_id
    from services.addresses import order_tree_by_name, insert_address

    person = await get_person_by_id(pool, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    tree_ordered = False
    message = None
    if payload.tree_name:
        res = await order_tree_by_name(pool, payload.tree_name, person_id)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("message", "Failed to order tree"))
        tree_ordered = True

    inserted = await insert_address(pool, person_id, payload.city, payload.pin_code, payload.state, payload.district)
    return AddressInsertOut(addressId=inserted.get("id"), treeOrdered=tree_ordered, message=message)

@router.get("/{person_id}/addresses", response_model=List[AddressOut])
async def get_addresses(person_id: int):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    from services.persons import get_addresses_by_person

    rows = await get_addresses_by_person(pool, person_id)
    return rows
