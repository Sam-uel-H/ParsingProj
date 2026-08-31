from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.db.session import get_db
from app.templates import service
from app.templates.schemas import (
    PublishTemplateRequest,
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


def _read_aggregate(aggregate: service.TemplateAggregate) -> TemplateRead:
    template = aggregate.template
    version = aggregate.version
    return TemplateRead(
        id=template.id,
        domain_id=template.domain_id,
        created_by_id=template.created_by_id,
        updated_by_id=template.updated_by_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
        current_version=TemplateVersionRead(
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
                TemplateColumnRead(
                    id=column.id,
                    name=column.name,
                    description=column.description,
                    column_type=column.column_type,
                    enum_values=column.enum_values,
                    prompt_text=column.prompt_text,
                    display_order=column.display_order,
                    created_by_id=column.created_by_id,
                    updated_by_id=column.updated_by_id,
                    created_at=column.created_at,
                    updated_at=column.updated_at,
                )
                for column in aggregate.columns
            ],
        ),
    )


@router.get("", response_model=list[TemplateSummary], summary="List templates")
def list_templates(
    domain_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[TemplateSummary]:
    return [
        TemplateSummary(
            id=item.template.id,
            domain_id=item.template.domain_id,
            name=item.version.name,
            description=item.version.description,
            version_number=item.version.version_number,
            status=item.version.status,
            lock_version=item.version.lock_version,
            published_at=item.version.published_at,
            updated_at=item.template.updated_at,
        )
        for item in service.list_templates(db, domain_id)
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
