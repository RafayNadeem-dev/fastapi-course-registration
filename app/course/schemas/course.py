from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CourseBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None


class CourseCreate(CourseBase):
    instructor_id: int


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    instructor_id: Optional[int] = None


class CourseVersionOut(BaseModel):
    id: int
    course_id: int
    version_number: int
    status: str
    published_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CourseOut(CourseBase):
    id: int
    instructor_id: int
    latest_published_version: Optional[CourseVersionOut] = None

    model_config = ConfigDict(from_attributes=True)
