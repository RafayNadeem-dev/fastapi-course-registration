from fastapi import APIRouter

from app.course.api.routes import instructor, user

router = APIRouter()
router.include_router(user.router)
router.include_router(instructor.router)
