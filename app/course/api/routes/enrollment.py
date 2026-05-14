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

    existing = crud.get_enrollment(db, current_user.id, data.course_id)
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

    workflow_id = f"enroll-{current_user.id}-{data.course_id}-{uuid.uuid4()}"
    handle = await temporal.start_workflow(
        StudentEnrollmentWorkflow.run,
        args=[current_user.id, data.course_id],
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    return {
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
        "task_queue": settings.TEMPORAL_TASK_QUEUE,
        "status": "scheduled",
    }
