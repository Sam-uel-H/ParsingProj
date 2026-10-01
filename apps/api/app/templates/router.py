from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.db.session import get_db
from app.templates import service
from app.templates.schemas import (
    CloneTemplateRequest,
    CreateTemplateVersionRequest,
    PublishTemplateRequest,
    ReorderTemplateColumnsRequest,
    TemplateColumnCreate,
    TemplateColumnRead,
    TemplateColumnUpdate,
    TemplateCreate,
    TemplateDraftUpdate,
    TemplateRead,
    TemplateSummary,
    TemplateVersionRead,
)

router = APIRouter(prefix="/templates", tags=["templates"])


def _read_version(aggregate: service.TemplateAggregate) -> TemplateVersionRead:
    version = aggregate.version
    return TemplateVersionRead(
        id=version.id,
        version_number=version.version_number,
        status=version.status,
        lock_version=version.lock_version,
        name=version.name,
        description=version.description,
        created_by_id=version.created_by_id,
        updated_by_id=version.updated_by_id,
        created_at=version.created_at,
        updated_at=version.updated_at,
        published_at=version.published_at,
        published_by_id=version.published_by_id,
        columns=[
            TemplateColumnRead.model_validate(column, from_attributes=True)
            for column in aggregate.columns
        ],
    )


def _read_aggregate(aggregate: service.TemplateAggregate) -> TemplateRead:
    template = aggregate.template
    return TemplateRead(
        id=template.id,
        domain_id=template.domain_id,
        created_by_id=template.created_by_id,
        updated_by_id=template.updated_by_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
        archived_at=template.archived_at,
        archived_by_id=template.archived_by_id,
        current_version=_read_version(aggregate),
    )


@router.get("", response_model=list[TemplateSummary], summary="List templates")
def list_templates(
    domain_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=200),
    author: str | None = Query(default=None, max_length=320),
    status_filter: Literal["draft", "published", "archived"] | None = Query(
        default=None, alias="status"
    ),
    db: Session = Depends(get_db),
) -> list[TemplateSummary]:
    return [
        TemplateSummary(
            id=item.aggregate.template.id,
            domain_id=item.aggregate.template.domain_id,
            name=item.aggregate.version.name,
            description=item.aggregate.version.description,
            version_number=item.aggregate.version.version_number,
            status=(
                "archived"
                if item.aggregate.template.archived_at is not None
                else item.aggregate.version.status.value
            ),
            lock_version=item.aggregate.version.lock_version,
            published_at=item.aggregate.version.published_at,
            created_by_id=item.aggregate.template.created_by_id,
            created_by_name=item.created_by_name,
            archived_at=item.aggregate.template.archived_at,
            updated_at=item.aggregate.template.updated_at,
        )
        for item in service.list_templates(
            db,
            domain_id=domain_id,
            search=search,
            author=author,
            status=status_filter,
        )
    ]


@router.post(
    "",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft template",
)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(service.create_template(db, data, actor))


@router.get("/{template_id}", response_model=TemplateRead, summary="Get a template")
def get_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> TemplateRead:
    return _read_aggregate(service.get_template(db, template_id))


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unused template",
)
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    service.delete_template(db, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{template_id}/versions",
    response_model=list[TemplateVersionRead],
    summary="List template version history",
)
def list_template_versions(
    template_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[TemplateVersionRead]:
    return [
        _read_version(aggregate) for aggregate in service.list_template_versions(db, template_id)
    ]


@router.post(
    "/{template_id}/versions",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft from a published template version",
)
def create_template_version(
    template_id: uuid.UUID,
    data: CreateTemplateVersionRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(
        service.create_template_version(
            db,
            template_id,
            actor,
            data.source_version_id if data else None,
        )
    )


@router.post(
    "/{template_id}/clone",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a published template into a new draft",
)
def clone_template(
    template_id: uuid.UUID,
    data: CloneTemplateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(
        service.clone_template(db, template_id, data.name, actor, data.source_version_id)
    )


@router.post(
    "/{template_id}/archive",
    response_model=TemplateRead,
    summary="Archive a template",
)
def archive_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(service.archive_template(db, template_id, actor))


@router.post(
    "/{template_id}/columns",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a column to a draft template",
)
def add_column(
    template_id: uuid.UUID,
    data: TemplateColumnCreate,
    expected_lock_version: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(service.add_column(db, template_id, data, actor, expected_lock_version))


@router.put(
    "/{template_id}/columns/order",
    response_model=TemplateRead,
    summary="Reorder all columns in a draft template",
)
def reorder_columns(
    template_id: uuid.UUID,
    data: ReorderTemplateColumnsRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(
        service.reorder_columns(
            db,
            template_id,
            data.column_ids,
            data.expected_lock_version,
            actor,
        )
    )


@router.put(
    "/{template_id}/draft",
    response_model=TemplateRead,
    summary="Save a complete draft template",
)
def update_draft(
    template_id: uuid.UUID,
    data: TemplateDraftUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(service.update_draft(db, template_id, data, actor))


@router.patch(
    "/{template_id}/columns/{column_id}",
    response_model=TemplateRead,
    summary="Update a column in a draft template",
)
def update_column(
    template_id: uuid.UUID,
    column_id: uuid.UUID,
    data: TemplateColumnUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(service.update_column(db, template_id, column_id, data, actor))


@router.delete(
    "/{template_id}/columns/{column_id}",
    response_model=TemplateRead,
    summary="Delete a column from a draft template",
)
def delete_column(
    template_id: uuid.UUID,
    column_id: uuid.UUID,
    expected_lock_version: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(
        service.delete_column(db, template_id, column_id, actor, expected_lock_version)
    )


@router.post(
    "/{template_id}/publish",
    response_model=TemplateRead,
    summary="Publish a complete draft template",
)
def publish_template(
    template_id: uuid.UUID,
    data: PublishTemplateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TemplateRead:
    return _read_aggregate(
        service.publish_template(db, template_id, actor, data.expected_lock_version)
    )
