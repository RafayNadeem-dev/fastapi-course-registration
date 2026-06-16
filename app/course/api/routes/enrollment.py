import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from temporalio.client import Client

from app.commons.deps import pagination, require_student
from app.core.config import settings
from app.core.db import get_db
from app.course import crud
from app.course.models import EnrollmentStatusEnum
from app.course.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.temporal.client import get_temporal_client
from app.temporal.workflows import StudentEnrollmentWorkflow
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


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_enrollment(
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
    temporal: Client = Depends(get_temporal_client),
):
    if crud.get_course(db, data.course_id) is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Course {data.course_id} not found"
        )

    published = crud.get_latest_published_version(db, data.course_id)
    if published is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Course {data.course_id} has no published version available for enrollment",
        )

    existing = crud.get_enrollment_for_course(db, current_user.id, data.course_id)
    if existing is not None:
        if existing.status == EnrollmentStatusEnum.ENROLLED.value:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Student already enrolled in this course",
            )
        if existing.status == EnrollmentStatusEnum.COMPLETED.value:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Student already completed this course",
            )

    workflow_id = f"enroll-{current_user.id}-{published.id}-{uuid.uuid4()}"
    handle = await temporal.start_workflow(
        StudentEnrollmentWorkflow.run,
        args=[current_user.id, published.id],
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    return {
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
        "course_version_id": published.id,
        "task_queue": settings.TEMPORAL_TASK_QUEUE,
        "status": "scheduled",
    }
