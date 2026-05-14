from pydantic import BaseModel, ConfigDict


class EnrollmentBase(BaseModel):
    course_id: int


class EnrollmentCreate(EnrollmentBase):
    pass


class EnrollmentOut(EnrollmentBase):
    id: int
    student_id: int
    status: str

    model_config = ConfigDict(from_attributes=True)
