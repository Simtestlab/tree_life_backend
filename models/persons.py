from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, EmailStr


class PersonOut(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    ordered_tree: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class PersonCreate(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class EmailExistsOut(BaseModel):
    exists: bool


class TreeOut(BaseModel):
    id: int
    name: str
    stock_available: int
    persons_ordered: int
    created_at: datetime
    updated_at: datetime


class AddressOut(BaseModel):
    id: int
    person_id: int
    city: Optional[str] = None
    pin_code: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PersonWithTreeOut(BaseModel):
    person: PersonOut
    tree: Optional[TreeOut] = None
    addresses: List[AddressOut] = []


class PersonHasOrderOut(BaseModel):
    hasOrdered: bool
    treeId: Optional[int] = None


class AddressCreate(BaseModel):
    city: Optional[str] = None
    pin_code: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    tree_name: Optional[str] = None


class AddressInsertOut(BaseModel):
    addressId: int
    treeOrdered: bool
    message: Optional[str] = None
