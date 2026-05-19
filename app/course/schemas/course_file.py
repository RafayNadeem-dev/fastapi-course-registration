from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CourseFileOut(BaseModel):
    id: int
    course_id: int
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
