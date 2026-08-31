from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from alembic import command

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture(scope="session")
def migrated_postgres() -> Iterator[None]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests.")

    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    yield


@pytest.fixture
def phase1_client(migrated_postgres: None) -> Iterator[TestClient]:
    from app.db.session import engine
    from app.main import app

    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE template_columns, template_versions, templates, "
                "domains, users CASCADE"
            )
        )

    with TestClient(app) as client:
        yield client
