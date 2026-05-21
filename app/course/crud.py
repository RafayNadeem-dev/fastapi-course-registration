from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.commons.deps import pagination
from app.course.models import (
    Course,
    CourseFile,
    CourseFileChunk,
    CourseVersion,
    CourseVersionStatusEnum,
    Enrollment,
    EnrollmentStatusEnum,
    FileParsingStatusEnum,
)
from app.course.parsing import ParsedChunk
from app.course.schemas.course import CourseCreate, CourseUpdate


class VersionNotEditableError(Exception):
    """Raised when an edit is attempted on a non-draft course version."""


def get_course(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def get_course_by_name(db: Session, name: str) -> Course | None:
    return db.execute(select(Course).where(Course.name == name)).scalar_one_or_none()


def list_courses(
    db: Session,
    page: pagination,
    instructor_id: int | None = None,
    require_published: bool = False,
) -> Sequence[Course]:
    stmt = select(Course)
    if instructor_id is not None:
        stmt = stmt.where(Course.instructor_id == instructor_id)
    if require_published:
        published_subq = (
            select(CourseVersion.course_id)
            .where(CourseVersion.status == CourseVersionStatusEnum.PUBLISHED.value)
            .distinct()
        )
        stmt = stmt.where(Course.id.in_(published_subq))
    offset = (page.page - 1) * page.size
    stmt = stmt.order_by(Course.id).offset(offset).limit(page.size)
    return db.execute(stmt).scalars().all()


def create_course(db: Session, data: CourseCreate) -> Course:
    if get_course_by_name(db, data.name):
        raise ValueError(f"Course with name {data.name!r} already exists")

    course = Course(
        name=data.name,
        description=data.description,
        instructor_id=data.instructor_id,
    )
    db.add(course)
    db.flush()

    draft = CourseVersion(
        course_id=course.id,
        version_number=1,
        status=CourseVersionStatusEnum.DRAFT.value,
    )
    db.add(draft)
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, course: Course, data: CourseUpdate) -> Course:
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != course.name:
        if get_course_by_name(db, update_data["name"]):
            raise ValueError(f"Course with name {update_data['name']!r} already exists")

    for field, value in update_data.items():
        setattr(course, field, value)

    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def delete_course(db: Session, course: Course) -> None:
    db.delete(course)
    db.commit()


def get_course_version(db: Session, version_id: int) -> CourseVersion | None:
    return db.get(CourseVersion, version_id)


def list_course_versions(db: Session, course_id: int) -> Sequence[CourseVersion]:
    return (
        db.execute(
            select(CourseVersion)
            .where(CourseVersion.course_id == course_id)
            .order_by(CourseVersion.version_number)
        )
        .scalars()
        .all()
    )


def get_latest_published_version(
    db: Session, course_id: int
) -> CourseVersion | None:
    return db.execute(
        select(CourseVersion)
        .where(
            CourseVersion.course_id == course_id,
            CourseVersion.status == CourseVersionStatusEnum.PUBLISHED.value,
        )
        .order_by(CourseVersion.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_active_draft(db: Session, course_id: int) -> CourseVersion | None:
    return db.execute(
        select(CourseVersion).where(
            CourseVersion.course_id == course_id,
            CourseVersion.status == CourseVersionStatusEnum.DRAFT.value,
        )
    ).scalar_one_or_none()


def ensure_draft_for_edit(db: Session, course_id: int) -> CourseVersion:
    """Return active draft if exists; otherwise create empty DRAFT vN+1."""
    existing = get_active_draft(db, course_id)
    if existing is not None:
        return existing

    max_version = db.execute(
        select(func.max(CourseVersion.version_number)).where(
            CourseVersion.course_id == course_id
        )
    ).scalar()
    next_number = (max_version or 0) + 1

    draft = CourseVersion(
        course_id=course_id,
        version_number=next_number,
        status=CourseVersionStatusEnum.DRAFT.value,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def assert_version_editable(version: CourseVersion) -> None:
    if version.status != CourseVersionStatusEnum.DRAFT.value:
        raise VersionNotEditableError(
            f"Course version {version.id} is {version.status}, not editable"
        )


def publish_version(db: Session, version: CourseVersion) -> CourseVersion:
    if version.status != CourseVersionStatusEnum.DRAFT.value:
        raise ValueError(
            f"Course version {version.id} is {version.status}, cannot publish"
        )

    prior_published = (
        db.execute(
            select(CourseVersion).where(
                CourseVersion.course_id == version.course_id,
                CourseVersion.status == CourseVersionStatusEnum.PUBLISHED.value,
            )
        )
        .scalars()
        .all()
    )
    for prior in prior_published:
        prior.status = CourseVersionStatusEnum.ARCHIVED.value
        db.add(prior)

    version.status = CourseVersionStatusEnum.PUBLISHED.value
    version.published_at = datetime.now(timezone.utc)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def get_enrollment_for_course(
    db: Session, student_id: int, course_id: int
) -> Enrollment | None:
    return db.execute(
        select(Enrollment)
        .join(CourseVersion, Enrollment.course_version_id == CourseVersion.id)
        .where(
            Enrollment.student_id == student_id,
            CourseVersion.course_id == course_id,
        )
    ).scalar_one_or_none()


def get_enrollment(
    db: Session, student_id: int, course_version_id: int
) -> Enrollment | None:
    return db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_version_id == course_version_id,
        )
    ).scalar_one_or_none()


def list_enrollments_for_student(
    db: Session,
    student_id: int,
    page: pagination,
) -> Sequence[Enrollment]:
    offset = (page.page - 1) * page.size
    stmt = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.id)
        .offset(offset)
        .limit(page.size)
    )
    return db.execute(stmt).scalars().all()


def create_course_file(
    db: Session,
    course_version_id: int,
    filename: str,
    stored_path: str,
    mime_type: str,
    size_bytes: int,
) -> CourseFile:
    course_file = CourseFile(
        course_version_id=course_version_id,
        filename=filename,
        stored_path=stored_path,
        mime_type=mime_type,
        size_bytes=size_bytes,
    )
    db.add(course_file)
    db.commit()
    db.refresh(course_file)
    return course_file


def list_course_files(
    db: Session, course_version_id: int
) -> Sequence[CourseFile]:
    return db.execute(
        select(CourseFile)
        .where(CourseFile.course_version_id == course_version_id)
        .order_by(CourseFile.id)
    ).scalars().all()


def get_course_file(db: Session, file_id: int) -> CourseFile | None:
    return db.get(CourseFile, file_id)


def delete_course_file(db: Session, course_file: CourseFile) -> None:
    db.delete(course_file)
    db.commit()


def update_file_parsing_status(
    db: Session,
    file_id: int,
    status: FileParsingStatusEnum,
    error: str | None = None,
) -> None:
    course_file = db.get(CourseFile, file_id)
    if course_file is None:
        raise LookupError(f"CourseFile {file_id} not found")
    course_file.parsing_status = status.value
    course_file.parsing_error = error
    db.add(course_file)
    db.commit()


def replace_file_chunks(
    db: Session, file_id: int, chunks: Sequence[ParsedChunk]
) -> int:
    """Atomic wipe+insert. Idempotent under Temporal activity retries."""
    db.execute(
        delete(CourseFileChunk).where(CourseFileChunk.course_file_id == file_id)
    )
    db.add_all(
        [
            CourseFileChunk(
                course_file_id=file_id,
                chunk_index=c.chunk_index,
                text=c.text,
                page_number=c.page_number,
                char_count=c.char_count,
                chunk_metadata=c.metadata,
            )
            for c in chunks
        ]
    )
    db.commit()
    return len(chunks)


def list_file_chunks(
    db: Session, file_id: int, page: pagination
) -> Sequence[CourseFileChunk]:
    offset = (page.page - 1) * page.size
    stmt = (
        select(CourseFileChunk)
        .where(CourseFileChunk.course_file_id == file_id)
        .order_by(CourseFileChunk.chunk_index)
        .offset(offset)
        .limit(page.size)
    )
    return db.execute(stmt).scalars().all()


def enroll_student(
    db: Session, student_id: int, course_id: int
) -> Enrollment:
    if get_course(db, course_id) is None:
        raise LookupError(f"Course {course_id} not found")

    published = get_latest_published_version(db, course_id)
    if published is None:
        raise ValueError(
            f"Course {course_id} has no published version available for enrollment"
        )

    existing = get_enrollment_for_course(db, student_id, course_id)
    if existing is not None:
        if existing.status == EnrollmentStatusEnum.ENROLLED.value:
            raise ValueError("Student already enrolled in this course")
        if existing.status == EnrollmentStatusEnum.COMPLETED.value:
            raise ValueError("Student already completed this course")

    enrollment = Enrollment(
        student_id=student_id,
        course_version_id=published.id,
        status=EnrollmentStatusEnum.ENROLLED.value,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment
