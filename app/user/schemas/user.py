from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr

from app.user.models import UserRolesEnum


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRolesEnum = UserRolesEnum.STUDENT
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserRegister(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRolesEnum] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
