from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import SessionFactory
from app.domains.models import Domain
from app.seed import SEED_DOMAIN_NAME, SEED_TEMPLATE_NAME, seed_development_data
from app.templates.models import TemplateVersion, TemplateVersionStatus


def test_development_seed_is_synthetic_published_and_idempotent(
    phase1_client: TestClient,
) -> None:
    del phase1_client
    with SessionFactory() as db:
        with pytest.raises(RuntimeError, match="only be created in development"):
            seed_development_data(db, Settings(_env_file=None, environment="test"))

        development_settings = Settings(_env_file=None, environment="development")
        first = seed_development_data(db, development_settings)
        second = seed_development_data(db, development_settings)

        assert first.created_domain is True
        assert first.created_template is True
        assert second.created_domain is False
        assert second.created_template is False
        assert first.domain_id == second.domain_id
        assert first.template_id == second.template_id
        assert db.scalar(
            select(func.count()).select_from(Domain).where(Domain.name == SEED_DOMAIN_NAME)
        ) == 1
        version = db.scalar(
            select(TemplateVersion).where(TemplateVersion.name == SEED_TEMPLATE_NAME)
        )
        assert version is not None
        assert version.status == TemplateVersionStatus.PUBLISHED
