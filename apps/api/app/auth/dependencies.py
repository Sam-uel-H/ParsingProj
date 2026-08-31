from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.config import get_settings
from app.db.session import get_db


def get_development_user(db: Session = Depends(get_db)) -> User:
    """Return a deterministic local identity until Phase 13 adds OIDC authentication."""

    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.development_user_email))
    if user is not None:
        return user

    user = User(
        id=settings.development_user_id,
        email=settings.development_user_email,
        display_name=settings.development_user_name,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.scalar(select(User).where(User.email == settings.development_user_email))
        if user is None:
            raise
        return user
    db.refresh(user)
    return user
