from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.commons.deps import pagination, require_instructor
from app.core.db import get_db
from app.course import crud
from app.course.schemas.course import CourseOut, CourseUpdate
from app.user.models import User

router = APIRouter(
    prefix="/instructor/courses",
    tags=["instructor-courses"],
)


class InstructorCourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


@router.get("", response_model=list[CourseOut])
def list_my_courses(
    page: pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    return crud.list_courses(db, page=page, instructor_id=current_user.id)


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_my_course(
    data: InstructorCourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    from app.course.schemas.course import CourseCreate

    payload = CourseCreate(
        name=data.name,
        description=data.description,
        instructor_id=current_user.id,
    )
    try:
        return crud.create_course(db, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch("/{course_id}", response_model=CourseOut)
def update_my_course(
    course_id: int,
    data: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    course = crud.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.instructor_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="You do not own this course"
        )
    if data.instructor_id is not None and data.instructor_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Cannot reassign instructor",
        )
    try:
        return crud.update_course(db, course, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    course = crud.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.instructor_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="You do not own this course"
        )
    crud.delete_course(db, course)
