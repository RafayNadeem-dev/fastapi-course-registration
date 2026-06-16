"""Create all tables defined on Base.metadata.

Run from project root:
    .\\venv\\Scripts\\python.exe -m app.scripts.init_db

Pass `--reset` to drop all tables before recreating. Use this when schema
changes are incompatible with existing tables (e.g., after the course
versioning refactor that repointed FKs from courses to course_versions).

This is fine for development. For schema evolution in production, use Alembic.
"""

import sys

from app.core.config import settings
from app.core.db import Base, engine

import app.user.models  # noqa: F401
import app.course.models  # noqa: F401


def main() -> None:
    print(f"Connecting to: {settings.DATABASE_URL}")
    if "--reset" in sys.argv:
        print("Dropping existing tables...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Tables created:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


if __name__ == "__main__":
    main()
