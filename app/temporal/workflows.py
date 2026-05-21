from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import (
        convert_file_to_markdown,
        init_module_progress,
        mark_file_completed,
        mark_file_failed,
        mark_file_processing,
        parse_and_chunk_file,
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


@workflow.defn
class CourseFileIngestWorkflow:
    @workflow.run
    async def run(self, course_file_id: int) -> dict:
        workflow.logger.info(
            "CourseFileIngestWorkflow started course_file_id=%s", course_file_id
        )

        short_timeout = timedelta(seconds=10)
        short_retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )
        parse_retry = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
            backoff_coefficient=2.0,
            non_retryable_error_types=[
                "ParsingPermanentError",
                "EmptyDocumentError",
                "CorruptDocumentError",
                "FileNotFoundError"
                ],
        )

        try:
            await workflow.execute_activity(
                mark_file_processing,
                args=[course_file_id],
                start_to_close_timeout=short_timeout,
                retry_policy=short_retry,
            )

            md_path = await workflow.execute_activity(
                convert_file_to_markdown,
                args=[course_file_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=parse_retry,
            )

            chunk_count = await workflow.execute_activity(
                parse_and_chunk_file,
                args=[course_file_id, md_path],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=parse_retry,
            )

            await workflow.execute_activity(
                mark_file_completed,
                args=[course_file_id, chunk_count],
                start_to_close_timeout=short_timeout,
                retry_policy=short_retry,
            )

            workflow.logger.info(
                "CourseFileIngestWorkflow finished course_file_id=%s chunks=%d",
                course_file_id,
                chunk_count,
            )
            return {"course_file_id": course_file_id, "chunks": chunk_count}

        except ActivityError as exc:
            cause = exc.cause
            error_message = str(cause) if cause is not None else str(exc)
            await workflow.execute_activity(
                mark_file_failed,
                args=[course_file_id, error_message],
                start_to_close_timeout=short_timeout,
                retry_policy=short_retry,
            )
            workflow.logger.error(
                "CourseFileIngestWorkflow failed course_file_id=%s error=%s",
                course_file_id,
                error_message,
            )
            raise
