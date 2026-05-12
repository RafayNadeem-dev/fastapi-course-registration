from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.user.models import UserRolesEnum


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRolesEnum = UserRolesEnum.STUDENT
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=100)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
