from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.documents.models import DocumentExtraction, ExtractionStatus
from app.jobs.models import BackgroundTask
from app.parsing.models import (
    InvocationStatus,
    LLMInvocation,
    ParsingJob,
    ParsingJobStatus,
    ParsingResult,
    ResultValidationStatus,
)
from app.parsing.validators import validate_value
from app.providers.errors import ProviderError, RetryableProviderError
from app.providers.llm import ExtractionRequest, LLMColumn, LLMProvider
from app.templates.models import TemplateColumn


def select_context(text: str, columns: list[TemplateColumn], limit: int) -> str:
    overhead = 2048 + sum(
        len(c.prompt_text or "")
        + len(c.name)
        + len(c.description or "")
        + len(str(c.enum_values or []))
        for c in columns
    )
    budget = limit - overhead
    if budget < 256:
        raise ProviderError("Column prompts exceed the configured context budget.")
    if len(text) <= budget:
        return text
    # Provider-neutral character budget; prioritize field-name windows, then the document start.
    ranges: list[tuple[int, int]] = []
    lower = text.lower()
    window = max(128, budget // max(len(columns), 1) // 2)
    for column in columns:
        start = lower.find(column.name.lower())
        if start >= 0:
            ranges.append((max(0, start - window // 4), min(len(text), start + window)))
    ranges.append((0, min(len(text), budget)))
    pieces: list[str] = []
    covered: list[tuple[int, int]] = []
    for start, end in ranges:
        if any(a <= start and end <= b for a, b in covered):
            continue
        remaining = budget - sum(len(piece) for piece in pieces) - len(pieces) * 5
        if remaining <= 0:
            break
        pieces.append(text[start : min(end, start + remaining)])
        covered.append((start, end))
    return "\n...\n".join(pieces)


@dataclass
class GroupOutcome:
    results: list[ParsingResult] = field(default_factory=list[ParsingResult])
    invocations: list[LLMInvocation] = field(default_factory=list[LLMInvocation])
    retry_error: Exception | None = None


async def extract_group(
    job_id: uuid.UUID,
    text: str,
    columns: list[TemplateColumn],
    attempt_numbers: dict[uuid.UUID, int],
    provider: LLMProvider,
    settings: Settings,
    semaphore: asyncio.Semaphore,
) -> GroupOutcome:
    outcome = GroupOutcome()
    pending = list(columns)
    correction: str | None = None
    for validation_attempt in range(settings.validation_retry_limit + 1):
        request = ExtractionRequest(
            document_text=select_context(text, pending, settings.parsing_context_characters),
            columns=tuple(
                LLMColumn(
                    c.name,
                    c.description or "",
                    c.column_type.value,
                    c.prompt_text or "",
                    tuple(c.enum_values or []),
                )
                for c in pending
            ),
            correction_instruction=correction,
        )
        try:
            async with semaphore:
                response = await asyncio.wait_for(
                    provider.extract(request), settings.llm_timeout_seconds
                )
        except (TimeoutError, ProviderError, OSError) as exc:
            retryable = isinstance(exc, (TimeoutError, RetryableProviderError, OSError))
            for column in pending:
                attempt_numbers[column.id] = attempt_numbers.get(column.id, 0) + 1
                outcome.invocations.append(
                    LLMInvocation(
                        parsing_job_id=job_id,
                        template_column_id=column.id,
                        attempt_number=attempt_numbers[column.id],
                        status=InvocationStatus.FAILED,
                        error_message="Transient provider error."
                        if retryable
                        else "Provider rejected extraction.",
                    )
                )
                if not retryable:
                    outcome.results.append(
                        ParsingResult(
                            parsing_job_id=job_id,
                            template_column_id=column.id,
                            validation_status=ResultValidationStatus.NEEDS_REVIEW,
                            validation_message="Provider rejected this column. Review is required.",
                            retry_count=validation_attempt,
                        )
                    )
            if retryable:
                outcome.retry_error = exc
            return outcome
        remaining: list[TemplateColumn] = []
        for index, column in enumerate(pending):
            matches = [v for v in response.values if v.column_name == column.name]
            value = matches[0] if len(matches) == 1 else None
            raw = value.raw_output if value else None
            canonical, message = validate_value(
                value.value if value else None, column.column_type, column.enum_values
            )
            attempt_numbers[column.id] = attempt_numbers.get(column.id, 0) + 1
            outcome.invocations.append(
                LLMInvocation(
                    parsing_job_id=job_id,
                    template_column_id=column.id,
                    attempt_number=attempt_numbers[column.id],
                    status=InvocationStatus.SUCCEEDED,
                    provider_name=response.metadata.provider,
                    model_name=response.metadata.model,
                    raw_output=raw,
                    input_tokens=response.usage.input_tokens if index == 0 else 0,
                    output_tokens=response.usage.output_tokens if index == 0 else 0,
                    latency_ms=response.usage.latency_ms,
                )
            )
            if message is not None and validation_attempt < settings.validation_retry_limit:
                remaining.append(column)
            else:
                outcome.results.append(
                    ParsingResult(
                        parsing_job_id=job_id,
                        template_column_id=column.id,
                        raw_output=raw,
                        canonical_value=canonical,
                        validation_status=ResultValidationStatus.NEEDS_REVIEW
                        if message
                        else ResultValidationStatus.VALID,
                        validation_message=message,
                        confidence=value.confidence if value else None,
                        retry_count=validation_attempt,
                    )
                )
        pending = remaining
        if not pending:
            break
        correction = (
            "Return valid typed values for each requested column; "
            "previous values failed validation."
        )
    return outcome


async def execute_parsing(
    db: Session,
    job: ParsingJob,
    task: BackgroundTask,
    provider: LLMProvider,
    settings: Settings,
) -> None:
    extraction = db.get(DocumentExtraction, job.document_extraction_id)
    if extraction is None or extraction.status != ExtractionStatus.SUCCEEDED:
        raise ProviderError("The pinned extraction is not available.")
    completed = set(
        db.scalars(
            select(ParsingResult.template_column_id).where(ParsingResult.parsing_job_id == job.id)
        )
    )
    columns = list(
        db.scalars(
            select(TemplateColumn)
            .where(TemplateColumn.template_version_id == job.template_version_id)
            .order_by(TemplateColumn.display_order)
        )
    )
    remaining = [c for c in columns if c.id not in completed]
    attempts = dict(
        db.execute(
            select(LLMInvocation.template_column_id, func.max(LLMInvocation.attempt_number))
            .where(LLMInvocation.parsing_job_id == job.id)
            .group_by(LLMInvocation.template_column_id)
        )
        .tuples()
        .all()
    )
    group_size = settings.parsing_batch_size if job.strategy == "batch" else 1
    semaphore = asyncio.Semaphore(settings.parsing_concurrency)
    work = [
        asyncio.create_task(
            extract_group(
                job.id,
                extraction.full_text or "",
                remaining[index : index + group_size],
                attempts,
                provider,
                settings,
                semaphore,
            )
        )
        for index in range(0, len(remaining), group_size)
    ]
    retry_error: Exception | None = None
    try:
        for future in asyncio.as_completed(work):
            outcome = await future
            db.add_all(outcome.invocations)
            db.add_all(outcome.results)
            task.completed_units += len(outcome.results)
            db.commit()
            if outcome.retry_error:
                retry_error = outcome.retry_error
    finally:
        for future in work:
            if not future.done():
                future.cancel()
        await asyncio.gather(*work, return_exceptions=True)
    if retry_error:
        raise retry_error
    warning = (
        db.scalar(
            select(ParsingResult.id)
            .where(
                ParsingResult.parsing_job_id == job.id,
                ParsingResult.validation_status == ResultValidationStatus.NEEDS_REVIEW,
            )
            .limit(1)
        )
        is not None
    )
    job.status = ParsingJobStatus.COMPLETED_WITH_WARNINGS if warning else ParsingJobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
