"""Seed the first admin account.

Idempotent: if a user with FIRST_ADMIN_EMAIL already exists, does nothing.
Safe to run on every startup and from multiple containers concurrently.

Run from project root:
    .\\venv\\Scripts\\python.exe -m app.scripts.seed_admin

Configure via env: FIRST_ADMIN_EMAIL, FIRST_ADMIN_PASSWORD.
"""

from app.core.config import settings
from app.core.db import sessionLocal
from app.user import crud
from app.user.models import UserRolesEnum
from app.user.schemas.user import UserCreate

# Import all model modules so SQLAlchemy can resolve cross-module relationships
# (User -> Course/Enrollment) when it configures mappers for the first query.
import app.user.models  # noqa: F401,E402
import app.course.models  # noqa: F401,E402


def main() -> None:
    db = sessionLocal()
    try:
        existing = crud.get_user_by_email(db, settings.FIRST_ADMIN_EMAIL)
        if existing is not None:
            print(f"Admin {settings.FIRST_ADMIN_EMAIL} already exists, skipping.")
            return

        crud.create_user(
            db,
            UserCreate(
                email=settings.FIRST_ADMIN_EMAIL,
                full_name="Administrator",
                password=settings.FIRST_ADMIN_PASSWORD,
                role=UserRolesEnum.ADMIN,
            ),
        )
        print(f"Created admin {settings.FIRST_ADMIN_EMAIL}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
