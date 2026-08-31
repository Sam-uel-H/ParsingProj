from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.db.session import get_db
from app.domains import service
from app.domains.schemas import DomainCreate, DomainRead, DomainUpdate

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=list[DomainRead], summary="List domains")
def list_domains(db: Session = Depends(get_db)) -> list[DomainRead]:
    return [DomainRead.model_validate(domain) for domain in service.list_domains(db)]


@router.post(
    "",
    response_model=DomainRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a domain",
)
def create_domain(
    data: DomainCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> DomainRead:
    return DomainRead.model_validate(service.create_domain(db, data, actor))


@router.get("/{domain_id}", response_model=DomainRead, summary="Get a domain")
def get_domain(domain_id: uuid.UUID, db: Session = Depends(get_db)) -> DomainRead:
    return DomainRead.model_validate(service.get_domain(db, domain_id))


@router.patch("/{domain_id}", response_model=DomainRead, summary="Update a domain")
def update_domain(
    domain_id: uuid.UUID,
    data: DomainUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
) -> DomainRead:
    return DomainRead.model_validate(service.update_domain(db, domain_id, data, actor))
