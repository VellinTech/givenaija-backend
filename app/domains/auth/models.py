from enum import Enum
from typing import Optional
from uuid import UUID
from sqlmodel import Field, SQLModel
from app.db.base import BaseUUIDModel


class UserRole(str, Enum):

    DONOR = "donor"
    FINANCE = "finance"
    ADMIN = "admin"


class User(BaseUUIDModel, table=True):

    __tablename__ = "users"

    email: str = Field(unique=True, index=True, nullable=False)
    password_hash: str = Field(nullable=False)
    role: str = Field(default=UserRole.DONOR.value, nullable=False)


class Member(BaseUUIDModel, table=True):
  
    __tablename__ = "members"

    user_id: UUID = Field(foreign_key="users.id", unique=True, nullable=False)
    phone: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None)




class UserRegister(SQLModel):

    email: str
    password: str
    phone: Optional[str] = None
    bio: Optional[str] = None


class UserLogin(SQLModel):
   
    email: str
    password: str


class UserRead(SQLModel):
   
    id: UUID
    email: str
    role: str


class Token(SQLModel):

    access_token: str
    token_type: str = "bearer"