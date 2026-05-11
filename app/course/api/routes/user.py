from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commons.deps import get_current_user, pagination
from app.core.db import get_db
from app.course import crud
from app.course.schemas.course import CourseOut

router = APIRouter(
    prefix="/courses",
    tags=["courses"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[CourseOut])
def list_courses(
    page: pagination = Depends(),
    instructor_id: int | None = None,
    db: Session = Depends(get_db),
):
    return crud.list_courses(db, page=page, instructor_id=instructor_id)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = crud.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course
