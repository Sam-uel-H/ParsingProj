from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import ConflictError, NotFoundError
from app.domains.models import Domain
from app.domains.schemas import DomainCreate, DomainUpdate


def list_domains(db: Session) -> list[Domain]:
    return list(db.scalars(select(Domain).order_by(Domain.name, Domain.id)))


def get_domain(db: Session, domain_id: uuid.UUID) -> Domain:
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise NotFoundError("Domain")
    return domain


def create_domain(db: Session, data: DomainCreate, actor: User) -> Domain:
    domain = Domain(
        name=data.name,
        description=data.description,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(domain)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A domain with this name already exists.",
            details={"field": "name"},
        ) from exc
    db.refresh(domain)
    return domain


def update_domain(
    db: Session,
    domain_id: uuid.UUID,
    data: DomainUpdate,
    actor: User,
) -> Domain:
    domain = get_domain(db, domain_id)
    if "name" in data.model_fields_set and data.name is not None:
        domain.name = data.name
    if "description" in data.model_fields_set:
        domain.description = data.description
    domain.updated_by_id = actor.id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A domain with this name already exists.",
            details={"field": "name"},
        ) from exc
    db.refresh(domain)
    return domain
