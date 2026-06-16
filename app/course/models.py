from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
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


class FileParsingStatusEnum(Enum):
    """Lifecycle states for parsing an uploaded course file into chunks."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CourseVersionStatusEnum(Enum):
    """Lifecycle states for a course version revision."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


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
    versions: Mapped[list["CourseVersion"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseVersion.version_number",
    )


class CourseVersion(BaseModel):
    __tablename__ = "course_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        default=CourseVersionStatusEnum.DRAFT.value,
        server_default=CourseVersionStatusEnum.DRAFT.value,
        nullable=False,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    course: Mapped["Course"] = relationship(back_populates="versions")
    modules: Mapped[list["Module"]] = relationship(
        back_populates="course_version",
        cascade="all, delete-orphan",
        order_by="Module.order",
    )
    files: Mapped[list["CourseFile"]] = relationship(
        back_populates="course_version",
        cascade="all, delete-orphan",
        order_by="CourseFile.id",
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="course_version",
    )

    __table_args__ = (
        UniqueConstraint(
            "course_id", "version_number", name="uq_course_version_number"
        ),
        Index(
            "uq_course_single_draft",
            "course_id",
            unique=True,
            postgresql_where=sa_text("status = 'draft'"),
        ),
    )


class Enrollment(BaseModel):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_version_id: Mapped[int] = mapped_column(
        ForeignKey("course_versions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String, default=EnrollmentStatusEnum.ENROLLED.value, nullable=False
    )

    student: Mapped["User"] = relationship(back_populates="enrolled_courses")
    course_version: Mapped["CourseVersion"] = relationship(back_populates="enrollments")
    module_progress: Mapped[list["ModuleProgress"]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id", "course_version_id", name="uq_enrollment_student_version"
        ),
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
    course_version_id: Mapped[int] = mapped_column(
        ForeignKey("course_versions.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(default=0, nullable=False)

    course_version: Mapped["CourseVersion"] = relationship(back_populates="modules")
    progress_entries: Mapped[list["ModuleProgress"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "course_version_id", "order", name="uq_module_version_order"
        ),
    )


class CourseFile(BaseModel):
    __tablename__ = "course_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_version_id: Mapped[int] = mapped_column(
        ForeignKey("course_versions.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_path: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parsing_status: Mapped[str] = mapped_column(
        String,
        default=FileParsingStatusEnum.PENDING.value,
        server_default=FileParsingStatusEnum.PENDING.value,
        nullable=False,
        index=True,
    )
    parsing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    course_version: Mapped["CourseVersion"] = relationship(back_populates="files")
    chunks: Mapped[list["CourseFileChunk"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="CourseFileChunk.chunk_index",
    )


class CourseFileChunk(BaseModel):
    __tablename__ = "course_file_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_file_id: Mapped[int] = mapped_column(
        ForeignKey("course_files.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )

    file: Mapped["CourseFile"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint(
            "course_file_id", "chunk_index", name="uq_chunk_file_index"
        ),
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
