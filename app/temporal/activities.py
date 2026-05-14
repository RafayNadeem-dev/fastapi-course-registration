from sqlalchemy import select
from temporalio import activity

from app.core.db import sessionLocal
from app.course.models import (
    Course,
    Enrollment,
    EnrollmentStatusEnum,
    Module,
    ModuleProgress,
    ModuleStatusEnum,
)


@activity.defn
def record_enrollment(student_id: int, course_id: int) -> int:
    """Insert Enrollment row. Idempotent: returns existing id if already enrolled."""
    db = sessionLocal()
    try:
        existing = db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id

        enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            status=EnrollmentStatusEnum.ENROLLED.value,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment.id
    finally:
        db.close()


@activity.defn
def init_module_progress(enrollment_id: int, course_id: int) -> int:
    """Create ModuleProgress rows for each course module. Returns count created."""
    db = sessionLocal()
    try:
        modules = (
            db.execute(select(Module).where(Module.course_id == course_id))
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


@activity.defn
def send_welcome_notification(student_id: int, course_id: int) -> dict:
    """Emit welcome notification. Real impl would call email/push provider."""
    db = sessionLocal()
    try:
        course = db.get(Course, course_id)
        course_name = course.name if course else f"#{course_id}"
    finally:
        db.close()

    message = f"Welcome to course {course_name!r}!"
    activity.logger.info(f"notification student={student_id}: {message}")
    return {
        "student_id": student_id,
        "course_id": course_id,
        "message": message,
        "channel": "log",
    }
