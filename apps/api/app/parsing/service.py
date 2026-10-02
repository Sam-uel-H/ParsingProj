from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import BusinessValidationError, InvalidOperationError, NotFoundError
from app.core.config import Settings
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentProcessingStatus,
    ExtractionStatus,
)
from app.jobs.models import BackgroundTask
from app.jobs.schemas import TaskProgress
from app.parsing.models import (
    ParsingJob,
    ParsingJobStatus,
    ParsingResult,
    ResultValidationStatus,
)
from app.parsing.schemas import ParsingJobCreate, ParsingJobRead, ParsingResultRead
from app.parsing.validators import validate_value
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
    task = db.scalar(select(BackgroundTask).where(BackgroundTask.parsing_job_id == job.id))
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
        document_extraction_id=job.document_extraction_id,
        strategy=job.strategy,
        progress=TaskProgress.model_validate(task) if task else None,
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


def queue_job(
    db: Session,
    data: ParsingJobCreate,
    actor: User,
    settings: Settings,
) -> tuple[ParsingJob, BackgroundTask]:
    document = db.scalar(select(Document).where(Document.id == data.document_id).with_for_update())
    strategy = data.strategy or settings.parsing_strategy
    if data.idempotency_key:
        existing = db.scalar(
            select(ParsingJob).where(
                ParsingJob.started_by_id == actor.id,
                ParsingJob.idempotency_key == data.idempotency_key,
            )
        )
        if existing:
            version = db.get(TemplateVersion, existing.template_version_id)
            if (
                existing.document_id != data.document_id
                or version is None
                or version.template_id != data.template_id
                or existing.strategy != strategy
            ):
                raise InvalidOperationError("Idempotency key was already used for a different job.")
            task = db.scalar(
                select(BackgroundTask).where(BackgroundTask.parsing_job_id == existing.id)
            )
            assert task is not None
            db.commit()
            return existing, task
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
        document_extraction_id=extraction.id,
        idempotency_key=data.idempotency_key,
        strategy=strategy,
        template_version_id=version.id,
        status=ParsingJobStatus.QUEUED,
        domain_override=mismatch,
        started_by_id=actor.id,
    )
    db.add(job)
    db.flush()

    task = BackgroundTask(
        parsing_job_id=job.id, max_attempts=settings.job_max_attempts, total_units=len(columns)
    )
    db.add(task)
    db.commit()
    return job, task


def list_jobs(db: Session, document_id: uuid.UUID | None = None) -> list[ParsingJobRead]:
    query = select(ParsingJob).order_by(ParsingJob.started_at.desc()).limit(100)
    if document_id:
        query = query.where(ParsingJob.document_id == document_id)
    return [_read_job(db, job) for job in db.scalars(query)]


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
    require_finished(db, job_id)
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
    require_finished(db, job_id)
    results = get_job_results(db, job_id)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([result.column_name for result in results])
    writer.writerow([result.current_value or "" for result in results])
    return output.getvalue()


def export_job_json(db: Session, job_id: uuid.UUID) -> dict[str, object]:
    require_finished(db, job_id)
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


def require_finished(db: Session, job_id: uuid.UUID) -> None:
    job = db.get(ParsingJob, job_id)
    if job is None:
        raise NotFoundError("Parsing job")
    if job.status not in {ParsingJobStatus.COMPLETED, ParsingJobStatus.COMPLETED_WITH_WARNINGS}:
        raise InvalidOperationError("Results can be reviewed or exported after the job completes.")
