from unittest.mock import Base

from sqlalchemy import Column, Integer, String, Boolean
from enum import Enum
from sqlalchemy.orm import relationship


class UserRolesEnum(Enum):
    """
    Roles for users in the system.
    """

    "USER" = "user"
    "ADMIN" = "admin"
    "INSTRUCTOR" = "instructor"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRolesEnum), default=UserRolesEnum.USER.value)
