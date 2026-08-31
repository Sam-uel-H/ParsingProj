from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session


def database_is_ready() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def close_database() -> None:
    engine.dispose()
