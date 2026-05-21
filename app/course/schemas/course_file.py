from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CourseFileOut(BaseModel):
    id: int
    course_version_id: int
    filename: str
    mime_type: str
    size_bytes: int
    parsing_status: str
    parsing_error: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseFileChunkOut(BaseModel):
    id: int
    course_file_id: int
    chunk_index: int
    text: str
    page_number: int | None
    char_count: int
    chunk_metadata: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
