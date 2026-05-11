from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import BaseModel

if TYPE_CHECKING:
    from app.course.models import Course, Enrollment


class UserRolesEnum(Enum):
    """
    Roles for users in the system.
    """

    STUDENT = "student"
    ADMIN = "admin"
    INSTRUCTOR = "instructor"


class User(BaseModel):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default=UserRolesEnum.STUDENT.value)
    hashed_password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(default=True)

    courses: Mapped[list["Course"]] = relationship(back_populates="instructor")
    enrolled_courses: Mapped[list["Enrollment"]] = relationship(back_populates="student")
