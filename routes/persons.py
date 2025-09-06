from fastapi import APIRouter, HTTPException, Query, Form, UploadFile, File
from typing import List
from pydantic import EmailStr

import db
from services.persons import email_exists as svc_email_exists, insert_person
from models.persons import PersonOut, PersonCreate, EmailExistsOut, PersonWithTreeOut

from models.persons import PersonHasOrderOut
from models.persons import AddressCreate, AddressInsertOut, AddressOut
from typing import Optional

from services.persons_pic import upload_person_pic, get_person_pic_url

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/email-exists", response_model=EmailExistsOut)
async def email_exists(email: EmailStr = Query(..., description="Email to check for existence")):
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    exists = await svc_email_exists(pool, str(email))
    return EmailExistsOut(exists=bool(exists))


@router.post("/", response_model=PersonOut, status_code=201)
async def create_person(
    first_name: str = Form(...),
    last_name: Optional[str] = Form(None),
    email: Optional[EmailStr] = Form(None),
    phone: Optional[str] = Form(None),
    file: UploadFile = File(None),
):
    """Create a person. Optionally accepts a picture file in the same multipart/form-data request.

    If a file is provided, the picture will be uploaded (S3 or local) and the person's
    `picture_filename` column will be updated.
    """
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    if email:
        exists = await svc_email_exists(pool, str(email))
        if exists:
            raise HTTPException(status_code=409, detail="Email already exists")

    try:
        created = await insert_person(pool, first_name, last_name, str(email) if email else None, phone)

        # If a picture file was provided, upload and save filename
        if file is not None:
            # ensure column exists (same idempotent SQL as in the picture endpoint)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                       WHERE table_name='persons' AND column_name='picture_filename') THEN
                            ALTER TABLE persons ADD COLUMN picture_filename TEXT;
                        END IF;
                    END
                    $$;
                    """
                )

            filename = f"persons/person_{created.get('id')}_{file.filename}"
            result = upload_person_pic(file, filename)
            if result.get("status") != "uploaded":
                raise HTTPException(status_code=500, detail=result.get("error", "upload failed"))

            # store filename in DB
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE persons SET picture_filename=$1, updated_at=now() WHERE id=$2",
                    filename,
                    created.get("id"),
                )

            # re-fetch to return updated object
            from services.persons import get_person_by_id

            created = await get_person_by_id(pool, created.get("id"))

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



@router.post("/{person_id}/picture", status_code=201)
async def upload_person_picture(person_id: int, file: UploadFile = File(...)):
    """Upload a person's picture. Saves filename in persons.picture_filename (creates column if missing).

    Uses services.persons_pic to perform the upload (S3 or local fallback).
    """
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    # verify person exists
    from services.persons import get_person_by_id

    person = await get_person_by_id(pool, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    # ensure column exists (safe, idempotent)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name='persons' AND column_name='picture_filename') THEN
                    ALTER TABLE persons ADD COLUMN picture_filename TEXT;
                END IF;
            END
            $$;
            """
        )

    # build filename inside 'persons/' prefix so S3 objects are stored in a persons/ folder
    # local fallback will therefore write to uploads/persons/...
    # build filename (simple, could be improved)
    filename = f"persons/person_{person_id}_{file.filename}"

    # call service (UploadFile has .file file-like)
    result = upload_person_pic(file, filename)
    if result.get("status") != "uploaded":
        raise HTTPException(status_code=500, detail=result.get("error", "upload failed"))

    # store filename in DB
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE persons SET picture_filename=$1, updated_at=now() WHERE id=$2",
            filename,
            person_id,
        )

    return {"status": "ok", "storage": result.get("storage"), "filename": filename}


@router.get("/{person_id}/picture-url")
async def get_person_picture_url(person_id: int):
    """Return a presigned URL or local file path for the person's picture."""
    pool = db.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not initialized")

    from services.persons import get_person_by_id

    person = await get_person_by_id(pool, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    filename = person.get("picture_filename")
    if not filename:
        raise HTTPException(status_code=404, detail="No picture for person")

    url = get_person_pic_url(filename)
    if isinstance(url, dict) and url.get("error"):
        raise HTTPException(status_code=500, detail=url.get("error"))

    return {"url": url}
