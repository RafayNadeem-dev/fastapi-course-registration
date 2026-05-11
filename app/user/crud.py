from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commons.deps import pagination
from app.core.security import hash_password, verify_password
from app.user.models import User, UserRolesEnum
from app.user.schemas.user import UserCreate, UserUpdate


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def list_users(
    db: Session,
    page: pagination,
    role: UserRolesEnum | None = None,
    is_active: bool | None = None,
) -> Sequence[User]:
    user_list_query = select(User)
    if role is not None:
        user_list_query = user_list_query.where(User.role == role.value)
    if is_active is not None:
        user_list_query = user_list_query.where(User.is_active == is_active)
    offset = (page.page - 1) * page.size
    user_list_query = user_list_query.order_by(
        User.id).offset(offset).limit(page.size)
    return db.execute(user_list_query).scalars().all()


def create_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, data.email):
        raise ValueError(f"User with email {data.email} already exists")

    user = User(
        email=data.email,
        full_name=data.full_name,
        role=data.role.value,
        is_active=data.is_active,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data:
        password = update_data.pop("password")
        if password:
            user.hashed_password = hash_password(password)

    if "role" in update_data and update_data["role"] is not None:
        update_data["role"] = update_data["role"].value

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()


def deactivate_user(db: Session, user: User) -> User:
    user.is_active = False
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
