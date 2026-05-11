"""Create all tables defined on Base.metadata.

Run from project root:
    .\\venv\\Scripts\\python.exe -m app.scripts.init_db

This is fine for development. For schema evolution in production, use Alembic.
"""

from app.core.config import settings
from app.core.db import Base, engine

import app.user.models
import app.course.models


def main() -> None:
    print(f"Connecting to: {settings.DATABASE_URL}")
    Base.metadata.create_all(bind=engine)
    print("Tables created:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


if __name__ == "__main__":
    main()
