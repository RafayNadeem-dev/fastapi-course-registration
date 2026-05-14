from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import (
        init_module_progress,
        record_enrollment,
        send_welcome_notification,
    )


@workflow.defn
class StudentEnrollmentWorkflow:
    @workflow.run
    async def run(self, student_id: int, course_id: int) -> dict:
        workflow.logger.info(
            "StudentEnrollmentWorkflow started student_id=%s course_id=%s",
            student_id,
            course_id,
        )
        timeout = timedelta(seconds=10)
        retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )

        enrollment_id = await workflow.execute_activity(
            record_enrollment,
            args=[student_id, course_id],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        modules_created = await workflow.execute_activity(
            init_module_progress,
            args=[enrollment_id, course_id],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        notification = await workflow.execute_activity(
            send_welcome_notification,
            args=[student_id, course_id],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        result = {
            "enrollment_id": enrollment_id,
            "modules_initialized": modules_created,
            "notification": notification,
        }
        workflow.logger.info(
            "StudentEnrollmentWorkflow finished enrollment_id=%s modules=%d",
            enrollment_id,
            modules_created,
        )
        return result
