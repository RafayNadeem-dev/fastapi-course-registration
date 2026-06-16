from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commons.deps import get_current_user, pagination
from app.core.db import get_db
from app.course import crud
from app.course.models import Course
from app.course.schemas.course import CourseOut, CourseVersionOut

router = APIRouter(
    prefix="/courses",
    tags=["courses"],
    dependencies=[Depends(get_current_user)],
)


def _course_out(db: Session, course: Course) -> CourseOut:
    pub = crud.get_latest_published_version(db, course.id)
    return CourseOut(
        id=course.id,
        name=course.name,
        description=course.description,
        instructor_id=course.instructor_id,
        latest_published_version=(
            CourseVersionOut.model_validate(pub) if pub is not None else None
        ),
    )


@router.get("", response_model=list[CourseOut])
def list_courses(
    page: pagination = Depends(),
    instructor_id: int | None = None,
    db: Session = Depends(get_db),
):
    courses = crud.list_courses(
        db, page=page, instructor_id=instructor_id, require_published=True
    )
    return [_course_out(db, c) for c in courses]


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = crud.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    pub = crud.get_latest_published_version(db, course_id)
    if pub is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Course has no published version"
        )
    return _course_out(db, course)
