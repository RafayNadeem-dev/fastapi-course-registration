from pydantic import BaseModel, ConfigDict


class EnrollmentCreate(BaseModel):
    course_id: int


class EnrollmentOut(BaseModel):
    id: int
    student_id: int
    course_version_id: int
    status: str

    model_config = ConfigDict(from_attributes=True)
