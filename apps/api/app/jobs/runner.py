from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.db.session import SessionFactory, engine
from app.documents.dependencies import get_document_extractor, get_object_storage
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentProcessingStatus,
    ExtractionStatus,
)
from app.jobs.models import ACTIVE_STATES, BackgroundTask
from app.parsing.dependencies import get_llm_provider
from app.parsing.models import ParsingJob, ParsingJobStatus
from app.providers.document_extraction import DocumentExtractionProvider
from app.providers.errors import ProviderError, RateLimitProviderError, RetryableProviderError
from app.providers.llm import LLMProvider
from app.providers.object_storage import ObjectStorage


def classify_error(exc: Exception) -> tuple[str, str, bool]:
    if isinstance(exc, RateLimitProviderError):
        return "provider_rate_limited", "Provider rate limit reached.", True
    if isinstance(exc, TimeoutError):
        return "provider_timeout", "Provider request timed out.", True
    if isinstance(exc, (RetryableProviderError, OSError)):
        return "provider_transient", "Provider temporarily unavailable.", True
    if isinstance(exc, (ProviderError, ValueError)):
        return "provider_terminal", "Provider could not process this document.", False
    return "worker_error", "Worker interrupted. The job will retry when possible.", True


async def process_task(
    task_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    storage: ObjectStorage | None = None,
    extractor: DocumentExtractionProvider | None = None,
    provider: LLMProvider | None = None,
) -> None:
    from app.documents.extraction_service import execute_extraction
    from app.parsing.execution import execute_parsing

    settings = settings or get_settings()
    # A session advisory lock spans commits and is released by PostgreSQL on worker death.
    # Duplicate deliveries never run the same job concurrently, including during recovery.
    lock_id = int.from_bytes(task_id.bytes[:8], "big", signed=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}):
            return
        try:
            with SessionFactory() as db:
                task = db.get(BackgroundTask, task_id)
                if task is None or task.state not in ACTIVE_STATES:
                    return
                if task.available_at > datetime.now(UTC):
                    return
                extraction = (
                    db.get(DocumentExtraction, task.extraction_id) if task.extraction_id else None
                )
                job = db.get(ParsingJob, task.parsing_job_id) if task.parsing_job_id else None
                document = db.get(Document, extraction.document_id) if extraction else None
                try:
                    if task.attempts >= task.max_attempts:
                        raise ProviderError("Job exhausted its recovery attempts.")
                    task.attempts += 1
                    task.state = "extracting" if extraction else "parsing"
                    task.started_at = datetime.now(UTC)
                    task.error_code = task.error_message = None
                    task.retryable = False
                    if extraction and document:
                        extraction.status = ExtractionStatus.PROCESSING
                        document.processing_status = DocumentProcessingStatus.PROCESSING
                    if job:
                        job.status = ParsingJobStatus.PARSING
                    db.commit()
                    if extraction:
                        await execute_extraction(
                            db,
                            extraction.id,
                            storage or get_object_storage(),
                            extractor or get_document_extractor(),
                            settings.extraction_timeout_seconds,
                        )
                        task.completed_units = task.total_units
                        task.state = "completed"
                    elif job:
                        await execute_parsing(
                            db, job, task, provider or get_llm_provider(), settings
                        )
                        task.state = job.status.value
                    else:
                        raise ProviderError("Missing task target.")
                    task.completed_at = datetime.now(UTC)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    code, message, retryable = classify_error(exc)
                    task.error_code, task.error_message, task.retryable = code, message, retryable
                    retry = retryable and task.attempts < task.max_attempts
                    task.state = "queued" if retry else "failed"
                    delay = min(
                        settings.job_retry_max_seconds,
                        settings.job_retry_base_seconds * 2 ** max(task.attempts - 1, 0),
                    )
                    if isinstance(exc, RateLimitProviderError) and exc.retry_after is not None:
                        delay = max(delay, min(exc.retry_after, settings.job_retry_max_seconds))
                    task.available_at = datetime.now(UTC) + timedelta(seconds=delay)
                    task.dispatched_at = None
                    if not retry:
                        task.completed_at = datetime.now(UTC)
                    if extraction and document:
                        extraction.status = (
                            ExtractionStatus.QUEUED if retry else ExtractionStatus.FAILED
                        )
                        extraction.error_code = (
                            "extraction_timeout"
                            if isinstance(exc, TimeoutError)
                            else "extraction_failed"
                        )
                        extraction.error_message = message
                        document.processing_status = (
                            DocumentProcessingStatus.QUEUED
                            if retry
                            else DocumentProcessingStatus.FAILED
                        )
                        if not retry:
                            extraction.completed_at = task.completed_at
                    if job:
                        job.status = ParsingJobStatus.QUEUED if retry else ParsingJobStatus.FAILED
                        if not retry:
                            job.completed_at = task.completed_at
                    db.commit()
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
