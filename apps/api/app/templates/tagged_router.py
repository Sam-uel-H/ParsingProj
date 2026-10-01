from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.db.session import get_db
from app.templates import tagged_service
from app.templates.tagged_schemas import TaggedExampleRead, TaggedExampleWrite

router = APIRouter(prefix="/templates/{template_id}/tagged-examples", tags=["tagged-examples"])


@router.get("", response_model=list[TaggedExampleRead])
def list_tagged_examples(
    template_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[TaggedExampleRead]:
    return [
        TaggedExampleRead.model_validate(tag)
        for tag in tagged_service.list_tagged_examples(db, template_id, document_id)
    ]


@router.post("", response_model=TaggedExampleRead, status_code=status.HTTP_201_CREATED)
def create_tagged_example(
    template_id: uuid.UUID,
    data: TaggedExampleWrite,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> TaggedExampleRead:
    return TaggedExampleRead.model_validate(
        tagged_service.create_tagged_example(db, template_id, data, actor)
    )


@router.put("/{tag_id}", response_model=TaggedExampleRead)
def replace_tagged_example(
    template_id: uuid.UUID,
    tag_id: uuid.UUID,
    data: TaggedExampleWrite,
    db: Session = Depends(get_db),
) -> TaggedExampleRead:
    return TaggedExampleRead.model_validate(
        tagged_service.replace_tagged_example(db, template_id, tag_id, data)
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tagged_example(
    template_id: uuid.UUID, tag_id: uuid.UUID, db: Session = Depends(get_db)
) -> Response:
    tagged_service.delete_tagged_example(db, template_id, tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
