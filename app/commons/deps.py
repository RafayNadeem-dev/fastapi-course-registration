from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.user.models import User, UserRolesEnum


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class pagination:
    def __init__(self, page: int = 1, size: int = 10):
        self.page = max(page, 1)
        self.size = max(min(size, 100), 1)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    from app.user import crud as user_crud

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exc

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise credentials_exc

    user = user_crud.get_user(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def require_role(*allowed_roles: UserRolesEnum):
    allowed = {r.value for r in allowed_roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


require_student = require_role(UserRolesEnum.STUDENT)
require_instructor = require_role(UserRolesEnum.INSTRUCTOR)
require_admin = require_role(UserRolesEnum.ADMIN)
