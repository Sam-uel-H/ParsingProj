from __future__ import annotations

import asyncio
import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import BusinessValidationError, NotFoundError
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentProcessingStatus,
    ExtractionStatus,
)
from app.parsing.models import (
    InvocationStatus,
    LLMInvocation,
    ParsingJob,
    ParsingJobStatus,
    ParsingResult,
    ResultValidationStatus,
)
from app.parsing.schemas import ParsingJobCreate, ParsingJobRead, ParsingResultRead
from app.parsing.validators import validate_value
from app.providers.errors import ProviderError
from app.providers.llm import ExtractionRequest, LLMColumn, LLMProvider
from app.templates.models import (
    ColumnType,
    Template,
    TemplateColumn,
    TemplateVersion,
    TemplateVersionStatus,
)


def _json_value(value: str | None, column_type: ColumnType) -> str | int | bool | None:
    if value is None:
        return None
    if column_type == ColumnType.INTEGER:
        return int(value)
    if column_type == ColumnType.BOOLEAN:
        return value == "true"
    if column_type in {ColumnType.DECIMAL, ColumnType.CURRENCY}:
        return str(Decimal(value))
    return value


def _read_job(db: Session, job: ParsingJob) -> ParsingJobRead:
    version = db.get(TemplateVersion, job.template_version_id)
    if version is None:
        raise NotFoundError("Template version")
    rows = list(
        db.execute(
            select(ParsingResult, TemplateColumn)
            .join(TemplateColumn, TemplateColumn.id == ParsingResult.template_column_id)
            .where(ParsingResult.parsing_job_id == job.id)
            .order_by(TemplateColumn.display_order)
        )
    )
    return ParsingJobRead(
        id=job.id,
        document_id=job.document_id,
        template_id=version.template_id,
        template_version_id=job.template_version_id,
        status=job.status,
        domain_override=job.domain_override,
        started_by_id=job.started_by_id,
        started_at=job.started_at,
        completed_at=job.completed_at,
        results=[
            ParsingResultRead(
                id=result.id,
                template_column_id=result.template_column_id,
                column_name=column.name,
                column_type=column.column_type,
                enum_values=column.enum_values,
                raw_output=result.raw_output,
                canonical_value=result.canonical_value,
                reviewed_value=result.reviewed_value,
                current_value=result.reviewed_value or result.canonical_value,
                validation_status=result.validation_status,
                validation_message=result.validation_message,
                confidence=result.confidence,
                retry_count=result.retry_count,
                human_verified=result.human_verified,
                reviewed_by_id=result.reviewed_by_id,
                reviewed_at=result.reviewed_at,
            )
            for result, column in rows
        ],
    )


async def run_job(
    db: Session,
    data: ParsingJobCreate,
    actor: User,
    provider: LLMProvider,
    retry_limit: int,
    timeout_seconds: float,
) -> ParsingJobRead:
    document = db.get(Document, data.document_id)
    template = db.get(Template, data.template_id)
    if document is None:
        raise NotFoundError("Document")
    if template is None:
        raise NotFoundError("Template")
    if template.archived_at is not None:
        raise BusinessValidationError("Archived templates cannot start new parsing jobs.")
    version = db.scalar(
        select(TemplateVersion)
        .where(
            TemplateVersion.template_id == template.id,
            TemplateVersion.status == TemplateVersionStatus.PUBLISHED,
        )
        .order_by(TemplateVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise BusinessValidationError("The selected template is not published.")
    if document.processing_status != DocumentProcessingStatus.SUCCEEDED:
        raise BusinessValidationError("The document must finish extraction before parsing.")
    extraction = db.get(DocumentExtraction, document.active_extraction_id)
    if extraction is None or extraction.status != ExtractionStatus.SUCCEEDED:
        raise BusinessValidationError("The document has no successful active extraction.")
    mismatch = document.domain_id != template.domain_id
    if mismatch and not data.confirm_domain_override:
        raise BusinessValidationError(
            "Document and template domains differ. Explicit confirmation is required.",
            details={"requires_domain_override": True},
        )
    columns = list(
        db.scalars(
            select(TemplateColumn)
            .where(TemplateColumn.template_version_id == version.id)
            .order_by(TemplateColumn.display_order)
        )
    )
    job = ParsingJob(
        document_id=document.id,
        template_version_id=version.id,
        status=ParsingJobStatus.RUNNING,
        domain_override=mismatch,
        started_by_id=actor.id,
    )
    db.add(job)
    db.flush()

    warning = False
    for column in columns:
        canonical: str | None = None
        message: str | None = None
        raw: str | None = None
        confidence: float | None = None
        attempts = 0
        for attempt in range(retry_limit + 1):
            attempts = attempt
            llm_column = LLMColumn(
                column.name,
                column.description or "",
                column.column_type.value,
                column.prompt_text or "",
                tuple(column.enum_values or []),
            )
            try:
                response = await asyncio.wait_for(
                    provider.extract(
                        ExtractionRequest(
                            document_text=extraction.full_text or "",
                            columns=(llm_column,),
                            correction_instruction=message,
                        )
                    ),
                    timeout_seconds,
                )
                value = response.values[0] if response.values else None
                raw = value.raw_output if value else None
                confidence = value.confidence if value else None
                db.add(
                    LLMInvocation(
                        parsing_job_id=job.id,
                        template_column_id=column.id,
                        attempt_number=attempt + 1,
                        status=InvocationStatus.SUCCEEDED,
                        provider_name=response.metadata.provider,
                        model_name=response.metadata.model,
                        raw_output=raw,
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        latency_ms=response.usage.latency_ms,
                    )
                )
                canonical, message = validate_value(
                    value.value if value else None, column.column_type, column.enum_values
                )
                if message is None:
                    break
            except (TimeoutError, ProviderError) as exc:
                message = "LLM provider timed out." if isinstance(exc, TimeoutError) else str(exc)
                db.add(
                    LLMInvocation(
                        parsing_job_id=job.id,
                        template_column_id=column.id,
                        attempt_number=attempt + 1,
                        status=InvocationStatus.FAILED,
                        error_message=message,
                    )
                )
        valid = message is None
        warning = warning or not valid
        db.add(
            ParsingResult(
                parsing_job_id=job.id,
                template_column_id=column.id,
                raw_output=raw,
                canonical_value=canonical,
                validation_status=(
                    ResultValidationStatus.VALID if valid else ResultValidationStatus.NEEDS_REVIEW
                ),
                validation_message=message,
                confidence=confidence,
                retry_count=attempts,
            )
        )
    job.status = ParsingJobStatus.COMPLETED_WITH_WARNINGS if warning else ParsingJobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    db.commit()
    return _read_job(db, job)


def get_job(db: Session, job_id: uuid.UUID) -> ParsingJobRead:
    job = db.get(ParsingJob, job_id)
    if job is None:
        raise NotFoundError("Parsing job")
    return _read_job(db, job)


def get_job_results(db: Session, job_id: uuid.UUID) -> list[ParsingResultRead]:
    return get_job(db, job_id).results


def correct_result(
    db: Session,
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    value: object,
    actor: User,
) -> ParsingResultRead:
    result = db.get(ParsingResult, result_id)
    if result is None or result.parsing_job_id != job_id:
        raise NotFoundError("Parsing result")
    column = db.get(TemplateColumn, result.template_column_id)
    if column is None:
        raise NotFoundError("Template column")
    canonical, message = validate_value(value, column.column_type, column.enum_values)
    if message is not None:
        raise BusinessValidationError(message)
    result.reviewed_value = canonical
    result.human_verified = True
    result.reviewed_by_id = actor.id
    result.reviewed_at = datetime.now(UTC)
    result.validation_status = ResultValidationStatus.VALID
    result.validation_message = None
    remaining_review = db.scalar(
        select(ParsingResult.id)
        .where(
            ParsingResult.parsing_job_id == job_id,
            ParsingResult.id != result_id,
            ParsingResult.validation_status == ResultValidationStatus.NEEDS_REVIEW,
        )
        .limit(1)
    )
    job = db.get(ParsingJob, job_id)
    if job is not None and job.status in {
        ParsingJobStatus.COMPLETED,
        ParsingJobStatus.COMPLETED_WITH_WARNINGS,
    }:
        job.status = (
            ParsingJobStatus.COMPLETED_WITH_WARNINGS
            if remaining_review is not None
            else ParsingJobStatus.COMPLETED
        )
    db.commit()
    return next(item for item in get_job_results(db, job_id) if item.id == result_id)


def export_job_csv(db: Session, job_id: uuid.UUID) -> str:
    results = get_job_results(db, job_id)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([result.column_name for result in results])
    writer.writerow([result.current_value or "" for result in results])
    return output.getvalue()


def export_job_json(db: Session, job_id: uuid.UUID) -> dict[str, object]:
    job = get_job(db, job_id)
    return {
        "job_id": str(job.id),
        "document_id": str(job.document_id),
        "template_id": str(job.template_id),
        "template_version_id": str(job.template_version_id),
        "results": [
            {
                "template_column_id": str(result.template_column_id),
                "column_name": result.column_name,
                "column_type": result.column_type,
                "value": _json_value(result.current_value, result.column_type),
                "validation_status": result.validation_status,
                "human_verified": result.human_verified,
                "reviewed_at": result.reviewed_at.isoformat() if result.reviewed_at else None,
            }
            for result in job.results
        ],
    }
