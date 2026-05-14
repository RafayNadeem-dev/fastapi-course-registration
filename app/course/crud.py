from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commons.deps import pagination
from app.course.models import Course, Enrollment, EnrollmentStatusEnum
from app.course.schemas.course import CourseCreate, CourseUpdate


def get_course(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def get_course_by_name(db: Session, name: str) -> Course | None:
    return db.execute(select(Course).where(Course.name == name)).scalar_one_or_none()


def list_courses(
    db: Session,
    page: pagination,
    instructor_id: int | None = None,
) -> Sequence[Course]:
    stmt = select(Course)
    if instructor_id is not None:
        stmt = stmt.where(Course.instructor_id == instructor_id)
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


def get_enrollment(
    db: Session, student_id: int, course_id: int
) -> Enrollment | None:
    return db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
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


def enroll_student(db: Session, student_id: int, course_id: int) -> Enrollment:
    if get_course(db, course_id) is None:
        raise LookupError(f"Course {course_id} not found")

    existing = get_enrollment(db, student_id, course_id)
    if existing is not None:
        if existing.status == EnrollmentStatusEnum.ENROLLED.value:
            raise ValueError("Student already enrolled in this course")
        if existing.status == EnrollmentStatusEnum.COMPLETED.value:
            raise ValueError("Student already completed this course")

    enrollment = Enrollment(
        student_id=student_id,
        course_id=course_id,
        status=EnrollmentStatusEnum.ENROLLED.value,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment
