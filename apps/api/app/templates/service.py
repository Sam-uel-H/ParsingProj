from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
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
from app.parsing.models import ParsingJob
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


@dataclass(frozen=True, slots=True)
class TemplateListItem:
    aggregate: TemplateAggregate
    created_by_name: str


def _get_template(db: Session, template_id: uuid.UUID) -> Template:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template")
    return template


def _get_template_for_update(db: Session, template_id: uuid.UUID) -> Template:
    template = db.scalar(select(Template).where(Template.id == template_id).with_for_update())
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


def _require_active(template: Template) -> None:
    if template.archived_at is not None:
        raise InvalidOperationError("Archived templates are read-only.")


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


def list_templates(
    db: Session,
    *,
    domain_id: uuid.UUID | None = None,
    search: str | None = None,
    author: str | None = None,
    status: str | None = None,
) -> list[TemplateListItem]:
    latest_versions = (
        select(
            TemplateVersion.template_id,
            func.max(TemplateVersion.version_number).label("version_number"),
        )
        .group_by(TemplateVersion.template_id)
        .subquery()
    )
    statement = (
        select(Template, TemplateVersion, User)
        .join(latest_versions, latest_versions.c.template_id == Template.id)
        .join(
            TemplateVersion,
            (TemplateVersion.template_id == Template.id)
            & (TemplateVersion.version_number == latest_versions.c.version_number),
        )
        .join(User, User.id == Template.created_by_id)
        .order_by(Template.updated_at.desc(), Template.id)
    )
    if domain_id is not None:
        statement = statement.where(Template.domain_id == domain_id)
    if search:
        pattern = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(TemplateVersion.name).like(pattern),
                func.lower(func.coalesce(TemplateVersion.description, "")).like(pattern),
            )
        )
    if author:
        author_pattern = f"%{author.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(User.display_name).like(author_pattern),
                func.lower(User.email).like(author_pattern),
            )
        )
    if status == "archived":
        statement = statement.where(Template.archived_at.is_not(None))
    elif status in {"draft", "published"}:
        statement = statement.where(
            Template.archived_at.is_(None), TemplateVersion.status == status
        )

    return [
        TemplateListItem(
            TemplateAggregate(template, version, _get_columns(db, version.id)),
            actor.display_name,
        )
        for template, version, actor in db.execute(statement)
    ]


def list_template_versions(db: Session, template_id: uuid.UUID) -> list[TemplateAggregate]:
    template = _get_template(db, template_id)
    versions = db.scalars(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template.id)
        .order_by(TemplateVersion.version_number.desc())
    )
    return [
        TemplateAggregate(template, version, _get_columns(db, version.id)) for version in versions
    ]


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
    _require_active(template)
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
    _require_active(template)
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
    _require_active(template)
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
    _require_active(template)
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
    _require_active(template)
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


def _published_source(
    db: Session,
    template_id: uuid.UUID,
    source_version_id: uuid.UUID | None,
) -> TemplateVersion:
    statement = select(TemplateVersion).where(
        TemplateVersion.template_id == template_id,
        TemplateVersion.status == TemplateVersionStatus.PUBLISHED,
    )
    if source_version_id is not None:
        statement = statement.where(TemplateVersion.id == source_version_id)
    else:
        statement = statement.order_by(TemplateVersion.version_number.desc()).limit(1)
    source = db.scalar(statement)
    if source is None:
        raise BusinessValidationError("A published template version is required.")
    return source


def _copy_columns(
    db: Session,
    source_version_id: uuid.UUID,
    destination_version_id: uuid.UUID,
    actor: User,
) -> None:
    for column in _get_columns(db, source_version_id):
        db.add(
            TemplateColumn(
                template_version_id=destination_version_id,
                name=column.name,
                description=column.description,
                column_type=column.column_type,
                enum_values=column.enum_values,
                prompt_text=column.prompt_text,
                display_order=column.display_order,
                created_by_id=actor.id,
                updated_by_id=actor.id,
            )
        )


def create_template_version(
    db: Session,
    template_id: uuid.UUID,
    actor: User,
    source_version_id: uuid.UUID | None = None,
) -> TemplateAggregate:
    template = _get_template_for_update(db, template_id)
    _require_active(template)
    existing_draft = db.scalar(
        select(TemplateVersion.id).where(
            TemplateVersion.template_id == template.id,
            TemplateVersion.status == TemplateVersionStatus.DRAFT,
        )
    )
    if existing_draft is not None:
        raise InvalidOperationError("This template already has a draft version.")

    source = _published_source(db, template.id, source_version_id)
    next_number = (
        db.scalar(
            select(func.max(TemplateVersion.version_number)).where(
                TemplateVersion.template_id == template.id
            )
        )
        or 0
    ) + 1
    version = TemplateVersion(
        template_id=template.id,
        version_number=next_number,
        status=TemplateVersionStatus.DRAFT,
        name=source.name,
        description=source.description,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(version)
    db.flush()
    _copy_columns(db, source.id, version.id, actor)
    template.updated_by_id = actor.id
    template.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A new template version could not be created.") from exc
    return get_template(db, template.id)


def clone_template(
    db: Session,
    template_id: uuid.UUID,
    name: str,
    actor: User,
    source_version_id: uuid.UUID | None = None,
) -> TemplateAggregate:
    source_template = _get_template(db, template_id)
    source = _published_source(db, source_template.id, source_version_id)
    template = Template(
        domain_id=source_template.domain_id,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(template)
    db.flush()
    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        status=TemplateVersionStatus.DRAFT,
        name=name,
        description=source.description,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(version)
    db.flush()
    _copy_columns(db, source.id, version.id, actor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The template could not be cloned.") from exc
    return get_template(db, template.id)


def archive_template(db: Session, template_id: uuid.UUID, actor: User) -> TemplateAggregate:
    template = _get_template_for_update(db, template_id)
    _require_active(template)
    template.archived_at = datetime.now(UTC)
    template.archived_by_id = actor.id
    template.updated_by_id = actor.id
    template.updated_at = datetime.now(UTC)
    db.commit()
    return get_template(db, template.id)


def delete_template(db: Session, template_id: uuid.UUID) -> None:
    template = _get_template_for_update(db, template_id)
    used_by_job = db.scalar(
        select(ParsingJob.id)
        .join(TemplateVersion, TemplateVersion.id == ParsingJob.template_version_id)
        .where(TemplateVersion.template_id == template.id)
        .limit(1)
    )
    if used_by_job is not None:
        raise ConflictError("Templates used by parsing jobs cannot be deleted.")
    db.delete(template)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The template cannot be deleted because it is in use.") from exc


def reorder_columns(
    db: Session,
    template_id: uuid.UUID,
    column_ids: list[uuid.UUID],
    expected_lock_version: int,
    actor: User,
) -> TemplateAggregate:
    template = _get_template(db, template_id)
    _require_active(template)
    version = _get_current_version(db, template.id, for_update=True)
    _require_draft(version)
    _check_lock(version, expected_lock_version)
    columns = _get_columns(db, version.id)
    existing_ids = {column.id for column in columns}
    if len(column_ids) != len(columns) or set(column_ids) != existing_ids:
        raise BusinessValidationError(
            "Column ordering must include every draft column exactly once."
        )
    by_id = {column.id: column for column in columns}
    for display_order, column_id in enumerate(column_ids):
        column = by_id[column_id]
        column.display_order = display_order
        column.updated_by_id = actor.id
    _touch(template, version, actor)
    db.commit()
    return get_template(db, template.id)
