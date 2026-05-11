from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import BaseModel

if TYPE_CHECKING:
    from app.user.models import User


class EnrollmentStatusEnum(Enum):
    """Lifecycle states for a student's enrollment in a course."""

    ENROLLED = "enrolled"
    COMPLETED = "completed"
    DROPPED = "dropped"


class Course(BaseModel):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    instructor: Mapped["User"] = relationship(back_populates="courses")
    pre_requisites: Mapped[list["CoursePreRequisite"]] = relationship(
        back_populates="course",
        foreign_keys="CoursePreRequisite.course_id",
        cascade="all, delete-orphan",
    )
    enrolled_students: Mapped[list["Enrollment"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )


class Enrollment(BaseModel):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String, default=EnrollmentStatusEnum.ENROLLED.value, nullable=False
    )

    student: Mapped["User"] = relationship(back_populates="enrolled_courses")
    course: Mapped["Course"] = relationship(back_populates="enrolled_students")

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
    )


class CoursePreRequisite(BaseModel):
    __tablename__ = "course_prerequisites"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    prerequisite_course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )

    course: Mapped["Course"] = relationship(
        back_populates="pre_requisites",
        foreign_keys=[course_id],
    )
    prerequisite_course: Mapped["Course"] = relationship(
        foreign_keys=[prerequisite_course_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "course_id", "prerequisite_course_id", name="uq_course_prerequisite"
        ),
        CheckConstraint(
            "course_id != prerequisite_course_id", name="ck_no_self_prerequisite"
        ),
    )
