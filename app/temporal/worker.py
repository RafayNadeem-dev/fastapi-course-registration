import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import settings
from app.temporal.activities import (
    init_module_progress,
    record_enrollment,
    send_welcome_notification,
)
from app.temporal.workflows import StudentEnrollmentWorkflow


async def main() -> None:
    client = await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
    )
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
