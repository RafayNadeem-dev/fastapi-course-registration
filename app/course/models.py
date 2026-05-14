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


class ModuleStatusEnum(Enum):
    """Per-student progress states for a course module."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


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
    modules: Mapped[list["Module"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Module.order",
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
    module_progress: Mapped[list["ModuleProgress"]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
    )

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


class Module(BaseModel):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(default=0, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="modules")
    progress_entries: Mapped[list["ModuleProgress"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("course_id", "order", name="uq_module_course_order"),
    )


class ModuleProgress(BaseModel):
    __tablename__ = "module_progress"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), index=True
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String, default=ModuleStatusEnum.NOT_STARTED.value, nullable=False
    )

    enrollment: Mapped["Enrollment"] = relationship(back_populates="module_progress")
    module: Mapped["Module"] = relationship(back_populates="progress_entries")

    __table_args__ = (
        UniqueConstraint(
            "enrollment_id", "module_id", name="uq_module_progress_enrollment_module"
        ),
    )
