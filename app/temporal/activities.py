from pathlib import Path

from sqlalchemy import delete, select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.core.config import settings
from app.core.db import sessionLocal
from app.course import crud
from app.course.models import (
    Course,
    CourseFile,
    CourseVersion,
    Enrollment,
    EnrollmentStatusEnum,
    FileParsingStatusEnum,
    Module,
    ModuleProgress,
    ModuleStatusEnum,
)
from app.course.parsing import ParsingError, chunk_markdown, convert_to_markdown


@activity.defn
def record_enrollment(student_id: int, course_version_id: int) -> int:
    """Insert Enrollment row. Idempotent: returns existing id if already enrolled."""
    db = sessionLocal()
    try:
        existing = db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.course_version_id == course_version_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id

        enrollment = Enrollment(
            student_id=student_id,
            course_version_id=course_version_id,
            status=EnrollmentStatusEnum.ENROLLED.value,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment.id
    finally:
        db.close()


@activity.defn
def init_module_progress(enrollment_id: int, course_version_id: int) -> int:
    """Create ModuleProgress rows for each module of the course version."""
    db = sessionLocal()
    try:
        modules = (
            db.execute(
                select(Module).where(Module.course_version_id == course_version_id)
            )
            .scalars()
            .all()
        )
        existing_module_ids = {
            row.module_id
            for row in db.execute(
                select(ModuleProgress).where(
                    ModuleProgress.enrollment_id == enrollment_id
                )
            )
            .scalars()
            .all()
        }
        created = 0
        for m in modules:
            if m.id in existing_module_ids:
                continue
            db.add(
                ModuleProgress(
                    enrollment_id=enrollment_id,
                    module_id=m.id,
                    status=ModuleStatusEnum.NOT_STARTED.value,
                )
            )
            created += 1
        db.commit()
        return created
    finally:
        db.close()


# --- compensating activities (saga rollback) ---------------------------------
# Each undoes a step of StudentEnrollmentWorkflow. They are idempotent: a DELETE
# of already-absent rows is a no-op, so they are safe under Temporal retries and
# safe to invoke even if the forward step partially applied.


@activity.defn
def delete_module_progress(enrollment_id: int) -> int:
    """Compensate init_module_progress: remove ModuleProgress rows for enrollment."""
    db = sessionLocal()
    try:
        result = db.execute(
            delete(ModuleProgress).where(
                ModuleProgress.enrollment_id == enrollment_id
            )
        )
        db.commit()
        return result.rowcount or 0
    finally:
        db.close()


@activity.defn
def delete_enrollment(enrollment_id: int) -> None:
    """Compensate record_enrollment: remove the Enrollment row."""
    db = sessionLocal()
    try:
        db.execute(delete(Enrollment).where(Enrollment.id == enrollment_id))
        db.commit()
    finally:
        db.close()


@activity.defn
def mark_file_processing(file_id: int) -> None:
    db = sessionLocal()
    try:
        crud.update_file_parsing_status(
            db, file_id, FileParsingStatusEnum.PROCESSING, error=None
        )
    finally:
        db.close()


@activity.defn
def convert_file_to_markdown(file_id: int) -> str:
    """Convert source file to markdown on disk. Returns md path.

    Idempotent: skips conversion when `.md` sibling already exists.
    """
    db = sessionLocal()
    try:
        course_file = db.get(CourseFile, file_id)
        if course_file is None:
            raise ApplicationError(
                f"CourseFile {file_id} not found",
                type="ParsingPermanentError",
                non_retryable=True,
            )
        stored_path = course_file.stored_path
        mime_type = course_file.mime_type
    finally:
        db.close()

    try:
        md_path = convert_to_markdown(stored_path, mime_type)
    except FileNotFoundError as exc:
        raise ApplicationError(
            str(exc), type="ParsingPermanentError", non_retryable=True
        ) from exc
    except ParsingError as exc:
        raise ApplicationError(
            str(exc), type=type(exc).__name__, non_retryable=True
        ) from exc
    return str(md_path)


@activity.defn
def parse_and_chunk_file(file_id: int, md_path: str) -> int:
    """Chunk the converted markdown and replace chunks atomically.

    Idempotent under Temporal activity retries: re-runs wipe prior chunks
    and re-insert the full set in one transaction. Permanent failures raise
    ParsingPermanentError.
    """
    try:
        chunks = chunk_markdown(
            Path(md_path),
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
    except FileNotFoundError as exc:
        raise ApplicationError(
            str(exc), type="ParsingPermanentError", non_retryable=True
        ) from exc
    except ParsingError as exc:
        raise ApplicationError(
            str(exc), type=type(exc).__name__, non_retryable=True
        ) from exc

    db = sessionLocal()
    try:
        return crud.replace_file_chunks(db, file_id, chunks)
    finally:
        db.close()


@activity.defn
def mark_file_completed(file_id: int, chunk_count: int) -> int:
    db = sessionLocal()
    try:
        crud.update_file_parsing_status(
            db, file_id, FileParsingStatusEnum.COMPLETED, error=None
        )
        return chunk_count
    finally:
        db.close()


@activity.defn
def mark_file_failed(file_id: int, error: str) -> None:
    db = sessionLocal()
    try:
        crud.update_file_parsing_status(
            db, file_id, FileParsingStatusEnum.FAILED, error=error
        )
    finally:
        db.close()


@activity.defn
def send_welcome_notification(student_id: int, course_version_id: int) -> dict:
    """Emit welcome notification. Real impl would call email/push provider."""
    db = sessionLocal()
    try:
        version = db.get(CourseVersion, course_version_id)
        if version is not None:
            course = db.get(Course, version.course_id)
            course_name = course.name if course else f"#{version.course_id}"
        else:
            course_name = f"version #{course_version_id}"
    finally:
        db.close()

    message = f"Welcome to course {course_name!r}!"
    activity.logger.info(f"notification student={student_id}: {message}")
    return {
        "student_id": student_id,
        "course_version_id": course_version_id,
        "message": message,
        "channel": "log",
    }
