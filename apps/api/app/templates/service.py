from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import (
    BusinessValidationError,
    ConflictError,
    InvalidOperationError,
    NotFoundError,
)
from app.domains.models import Domain
from app.templates.models import (
    ColumnType,
    Template,
    TemplateColumn,
    TemplateVersion,
    TemplateVersionStatus,
)
from app.templates.schemas import (
    TemplateColumnCreate,
    TemplateColumnUpdate,
    TemplateCreate,
    TemplateDraftUpdate,
)


@dataclass(frozen=True, slots=True)
class TemplateAggregate:
    template: Template
    version: TemplateVersion
    columns: list[TemplateColumn]


def _get_template(db: Session, template_id: uuid.UUID) -> Template:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template")
    return template


def _get_current_version(
    db: Session,
    template_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> TemplateVersion:
    statement = (
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    version = db.scalar(statement)
    if version is None:
        raise NotFoundError("Template version")
    return version


def _get_columns(db: Session, version_id: uuid.UUID) -> list[TemplateColumn]:
    return list(
        db.scalars(
            select(TemplateColumn)
            .where(TemplateColumn.template_version_id == version_id)
            .order_by(TemplateColumn.display_order, TemplateColumn.id)
        )
    )


def _require_draft(version: TemplateVersion) -> None:
    if version.status != TemplateVersionStatus.DRAFT:
        raise InvalidOperationError("Published template versions are immutable.")


def _check_lock(version: TemplateVersion, expected_lock_version: int | None) -> None:
    if expected_lock_version is not None and version.lock_version != expected_lock_version:
        raise ConflictError(
            "The draft changed since it was loaded. Refresh and try again.",
            details={"current_lock_version": version.lock_version},
        )


def _touch(template: Template, version: TemplateVersion, actor: User) -> None:
    template.updated_by_id = actor.id
    template.updated_at = datetime.now(UTC)
    version.updated_by_id = actor.id
    version.lock_version += 1


def get_template(db: Session, template_id: uuid.UUID) -> TemplateAggregate:
    template = _get_template(db, template_id)
    version = _get_current_version(db, template.id)
    return TemplateAggregate(template, version, _get_columns(db, version.id))


def list_templates(db: Session, domain_id: uuid.UUID | None = None) -> list[TemplateAggregate]:
    statement = select(Template).order_by(Template.updated_at.desc(), Template.id)
    if domain_id is not None:
        statement = statement.where(Template.domain_id == domain_id)
    return [get_template(db, template.id) for template in db.scalars(statement)]


def _new_column(data: TemplateColumnCreate, version_id: uuid.UUID, actor: User) -> TemplateColumn:
    return TemplateColumn(
        template_version_id=version_id,
        name=data.name,
        description=data.description,
        column_type=data.column_type,
        enum_values=data.enum_values,
        prompt_text=data.prompt_text,
        display_order=data.display_order,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )


def _assign_column(column: TemplateColumn, data: TemplateColumnCreate, actor: User) -> None:
    column.name = data.name
    column.description = data.description
    column.column_type = data.column_type
    column.enum_values = data.enum_values
    column.prompt_text = data.prompt_text
    column.display_order = data.display_order
    column.updated_by_id = actor.id


def create_template(db: Session, data: TemplateCreate, actor: User) -> TemplateAggregate:
    if db.get(Domain, data.domain_id) is None:
        raise NotFoundError("Domain")

    template = Template(
        domain_id=data.domain_id,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(template)
    db.flush()
    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        status=TemplateVersionStatus.DRAFT,
        name=data.name,
        description=data.description,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(version)
    db.flush()
    db.add_all([_new_column(column, version.id, actor) for column in data.columns])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Template data conflicts with an existing record.") from exc
    return get_template(db, template.id)


def update_draft(
    db: Session,
    template_id: uuid.UUID,
    data: TemplateDraftUpdate,
    actor: User,
) -> TemplateAggregate:
    template = _get_template(db, template_id)
    version = _get_current_version(db, template.id, for_update=True)
    _require_draft(version)
    _check_lock(version, data.expected_lock_version)
    if db.get(Domain, data.domain_id) is None:
        raise NotFoundError("Domain")

    existing = {column.id: column for column in _get_columns(db, version.id)}
    submitted_ids = {column.id for column in data.columns if column.id is not None}
    unknown_ids = submitted_ids.difference(existing)
    if unknown_ids:
        raise BusinessValidationError(
            "One or more columns do not belong to this draft.",
            details={"column_ids": sorted(str(column_id) for column_id in unknown_ids)},
        )

    for column_id, column in existing.items():
        if column_id not in submitted_ids:
            db.delete(column)
    db.flush()

    for column_data in data.columns:
        if column_data.id is None:
            db.add(_new_column(column_data, version.id, actor))
        else:
            _assign_column(existing[column_data.id], column_data, actor)

    template.domain_id = data.domain_id
    version.name = data.name
    version.description = data.description
    _touch(template, version, actor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Draft data conflicts with an existing column or database constraint."
        ) from exc
    return get_template(db, template.id)


def add_column(
    db: Session,
    template_id: uuid.UUID,
    data: TemplateColumnCreate,
    actor: User,
    expected_lock_version: int | None = None,
) -> TemplateAggregate:
    template = _get_template(db, template_id)
    version = _get_current_version(db, template.id, for_update=True)
    _require_draft(version)
    _check_lock(version, expected_lock_version)

    duplicate = db.scalar(
        select(TemplateColumn.id).where(
            TemplateColumn.template_version_id == version.id,
            TemplateColumn.name == data.name,
        )
    )
    if duplicate is not None:
        raise ConflictError(
            "A column with this name already exists in the draft version.",
            details={"field": "name"},
        )

    db.add(_new_column(data, version.id, actor))
    _touch(template, version, actor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A column with this name already exists in the draft version.",
            details={"field": "name"},
        ) from exc
    return get_template(db, template.id)


def update_column(
    db: Session,
    template_id: uuid.UUID,
    column_id: uuid.UUID,
    data: TemplateColumnUpdate,
    actor: User,
) -> TemplateAggregate:
    template = _get_template(db, template_id)
    version = _get_current_version(db, template.id, for_update=True)
    _require_draft(version)
    _check_lock(version, data.expected_lock_version)
    column = db.get(TemplateColumn, column_id)
    if column is None or column.template_version_id != version.id:
        raise NotFoundError("Template column")
    _assign_column(column, data, actor)
    _touch(template, version, actor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A column with this name already exists in the draft version.",
            details={"field": "name"},
        ) from exc
    return get_template(db, template.id)


def delete_column(
    db: Session,
    template_id: uuid.UUID,
    column_id: uuid.UUID,
    actor: User,
    expected_lock_version: int,
) -> TemplateAggregate:
    template = _get_template(db, template_id)
    version = _get_current_version(db, template.id, for_update=True)
    _require_draft(version)
    _check_lock(version, expected_lock_version)
    column = db.get(TemplateColumn, column_id)
    if column is None or column.template_version_id != version.id:
        raise NotFoundError("Template column")
    db.delete(column)
    _touch(template, version, actor)
    db.commit()
    return get_template(db, template.id)


def _validate_publish(columns: list[TemplateColumn]) -> None:
    problems: list[dict[str, str]] = []
    if not columns:
        problems.append({"path": "columns", "message": "Add at least one column."})
    for index, column in enumerate(columns):
        if not (column.prompt_text or "").strip():
            problems.append(
                {
                    "path": f"columns.{index}.prompt_text",
                    "message": "Prompt text is required before publishing.",
                }
            )
        if column.column_type == ColumnType.ENUM and not column.enum_values:
            problems.append(
                {
                    "path": f"columns.{index}.enum_values",
                    "message": "Enum columns require allowed values.",
                }
            )
    if problems:
        raise BusinessValidationError(
            "Template is not ready to publish.", details={"fields": problems}
        )


def publish_template(
    db: Session,
    template_id: uuid.UUID,
    actor: User,
    expected_lock_version: int,
) -> TemplateAggregate:
    template = _get_template(db, template_id)
    version = _get_current_version(db, template.id, for_update=True)
    _require_draft(version)
    _check_lock(version, expected_lock_version)
    columns = _get_columns(db, version.id)
    _validate_publish(columns)

    version.status = TemplateVersionStatus.PUBLISHED
    version.published_at = datetime.now(UTC)
    version.published_by_id = actor.id
    _touch(template, version, actor)
    db.commit()
    return get_template(db, template.id)
