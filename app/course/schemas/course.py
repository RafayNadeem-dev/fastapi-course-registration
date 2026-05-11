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


class CourseOut(CourseBase):
    id: int
    instructor_id: int

    model_config = ConfigDict(from_attributes=True)
