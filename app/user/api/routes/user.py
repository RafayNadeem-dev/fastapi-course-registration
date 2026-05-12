from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.commons.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token
from app.user import crud
from app.user.models import User, UserRolesEnum
from app.user.schemas.user import UserCreate, UserOut, UserCreate, UserUpdate

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    payload = UserCreate(
        email=data.email,
        full_name=data.full_name,
        password=data.password,
        role=UserRolesEnum.STUDENT,
    )
    try:
        return crud.create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/auth/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = crud.authenticate_user(db, email=form.username, password=form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.id, extra_claims={"role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/users/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/users/me", response_model=UserOut)
def update_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.role is not None and data.role.value != current_user.role:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Cannot change your own role",
        )
    try:
        return crud.update_user(db, current_user, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
