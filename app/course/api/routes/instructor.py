import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from temporalio.client import Client

from app.commons.deps import pagination, require_instructor
from app.commons.storage import delete_stored_file, save_course_file
from app.core.config import settings
from app.core.db import get_db
from app.course import crud
from app.course.schemas.course import CourseOut, CourseUpdate
from app.course.schemas.course_file import CourseFileChunkOut, CourseFileOut
from app.temporal.client import get_temporal_client
from app.temporal.workflows import CourseFileIngestWorkflow
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


def _get_owned_course(
    db: Session, course_id: int, current_user: User
):
    course = crud.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.instructor_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="You do not own this course"
        )
    return course


@router.post(
    "/{course_id}/files",
    response_model=CourseFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_course_file(
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
    temporal: Client = Depends(get_temporal_client),
):
    _get_owned_course(db, course_id, current_user)

    stored_path, size_bytes, mime, original_filename = save_course_file(
        course_id, file
    )
    try:
        course_file = crud.create_course_file(
            db,
            course_id=course_id,
            filename=original_filename,
            stored_path=str(stored_path),
            mime_type=mime,
            size_bytes=size_bytes,
        )
    except Exception:
        delete_stored_file(str(stored_path))
        raise

    workflow_id = f"ingest-file-{course_file.id}-{uuid.uuid4()}"
    await temporal.start_workflow(
        CourseFileIngestWorkflow.run,
        args=[course_file.id],
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    return course_file


@router.get("/{course_id}/files", response_model=list[CourseFileOut])
def list_course_files(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    _get_owned_course(db, course_id, current_user)
    return crud.list_course_files(db, course_id)


@router.delete(
    "/{course_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_course_file(
    course_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    _get_owned_course(db, course_id, current_user)

    course_file = crud.get_course_file(db, file_id)
    if course_file is None or course_file.course_id != course_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    stored_path = course_file.stored_path
    crud.delete_course_file(db, course_file)
    delete_stored_file(stored_path)


@router.post(
    "/{course_id}/files/{file_id}/reparse",
    status_code=status.HTTP_202_ACCEPTED,
)
async def reparse_course_file(
    course_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
    temporal: Client = Depends(get_temporal_client),
):
    _get_owned_course(db, course_id, current_user)

    course_file = crud.get_course_file(db, file_id)
    if course_file is None or course_file.course_id != course_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    workflow_id = f"ingest-file-{course_file.id}-{uuid.uuid4()}"
    handle = await temporal.start_workflow(
        CourseFileIngestWorkflow.run,
        args=[course_file.id],
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    return {
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
        "task_queue": settings.TEMPORAL_TASK_QUEUE,
        "status": "scheduled",
    }


@router.get(
    "/{course_id}/files/{file_id}/chunks",
    response_model=list[CourseFileChunkOut],
)
def list_course_file_chunks(
    course_id: int,
    file_id: int,
    page: pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    _get_owned_course(db, course_id, current_user)

    course_file = crud.get_course_file(db, file_id)
    if course_file is None or course_file.course_id != course_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    return crud.list_file_chunks(db, file_id, page=page)
