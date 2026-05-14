from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commons.deps import pagination, require_student
from app.core.db import get_db
from app.course import crud
from app.course.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.user.models import User

router = APIRouter(
    prefix="/enrollments",
    tags=["enrollments"],
)


@router.get("", response_model=list[EnrollmentOut])
def list_my_enrollments(
    page: pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    return crud.list_enrollments_for_student(db, current_user.id, page=page)


@router.post("", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED)
def create_enrollment(
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    try:
        return crud.enroll_student(db, current_user.id, data.course_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
