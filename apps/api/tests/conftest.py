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
    from datetime import UTC, datetime

    from app.core.config import get_settings
    from app.db.session import SessionFactory, engine
    from app.documents.dependencies import get_document_extractor, get_object_storage
    from app.jobs.dispatch import get_dispatcher
    from app.jobs.models import BackgroundTask
    from app.jobs.runner import process_task
    from app.main import app
    from app.parsing.dependencies import get_llm_provider

    async def drain_task(task_id):
        def resolve(factory):
            return app.dependency_overrides.get(factory, factory)()

        settings = resolve(get_settings)
        for _ in range(settings.job_max_attempts):
            await process_task(
                task_id,
                settings=settings,
                storage=resolve(get_object_storage),
                extractor=resolve(get_document_extractor),
                provider=resolve(get_llm_provider),
            )
            with SessionFactory() as db:
                task = db.get(BackgroundTask, task_id)
                if task.state != "queued":
                    break
                task.available_at = datetime.now(UTC)
                db.commit()

    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE template_columns, template_versions, templates, "
                "domains, users CASCADE"
            )
        )

    app.dependency_overrides[get_dispatcher] = lambda: drain_task
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_dispatcher, None)
