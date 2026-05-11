from fastapi import APIRouter

from app.user.api.routes import user

router = APIRouter()
router.include_router(user.router)
