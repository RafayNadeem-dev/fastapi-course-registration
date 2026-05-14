import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import configure_mappers
from temporalio.client import Client
from temporalio.worker import Worker

# Eagerly import all model modules so SQLAlchemy mappers can resolve cross-module
# string refs (e.g. Course.instructor -> 'User'). Without this, the first ORM query
# in an activity raises "expression 'User' failed to locate a name".
import app.user.models  # noqa: F401
import app.course.models  # noqa: F401

# Force mapper configuration now so any registry issues surface at startup,
# not on the first activity query inside a thread.
configure_mappers()

from app.core.config import settings
from app.temporal.activities import (
    init_module_progress,
    record_enrollment,
    send_welcome_notification,
)
from app.temporal.workflows import StudentEnrollmentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("worker")


async def main() -> None:
    client = await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
    )
    log.info("worker ready task_queue=%s", settings.TEMPORAL_TASK_QUEUE)

    # Sync activities (DB I/O via SQLAlchemy) run in a thread pool.
    # Async activities would run on the worker's event loop instead.
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[StudentEnrollmentWorkflow],
        activities=[
            record_enrollment,
            init_module_progress,
            send_welcome_notification,
        ],
        activity_executor=ThreadPoolExecutor(max_workers=50),
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
