from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.core.config import Settings, get_settings
from app.db.session import SessionFactory
from app.domains import service as domain_service
from app.domains.models import Domain
from app.domains.schemas import DomainCreate
from app.templates import service as template_service
from app.templates.models import ColumnType, Template, TemplateVersion
from app.templates.schemas import TemplateColumnCreate, TemplateCreate

SEED_DOMAIN_NAME = "Agent Bank Notices"
SEED_TEMPLATE_NAME = "Agent Bank Notice - Section 6"


@dataclass(frozen=True)
class SeedResult:
    domain_id: str
    template_id: str
    created_domain: bool
    created_template: bool


def seed_development_data(db: Session, settings: Settings) -> SeedResult:
    if settings.environment != "development":
        raise RuntimeError("Development seed data may only be created in development.")

    actor = get_development_user(db)
    domain = db.scalar(select(Domain).where(Domain.name == SEED_DOMAIN_NAME))
    created_domain = domain is None
    if domain is None:
        domain = domain_service.create_domain(
            db,
            DomainCreate(
                name=SEED_DOMAIN_NAME,
                description="Synthetic local data for the MVP Agent Bank Notice workflow.",
            ),
            actor,
        )

    template = db.scalar(
        select(Template)
        .join(TemplateVersion, TemplateVersion.template_id == Template.id)
        .where(
            Template.domain_id == domain.id,
            Template.archived_at.is_(None),
            TemplateVersion.name == SEED_TEMPLATE_NAME,
        )
        .limit(1)
    )
    created_template = template is None
    if template is None:
        aggregate = template_service.create_template(
            db,
            TemplateCreate(
                domain_id=domain.id,
                name=SEED_TEMPLATE_NAME,
                description="Synthetic MVP template; safe for local development and demos.",
                columns=[
                    TemplateColumnCreate(
                        name="Notice Date",
                        column_type=ColumnType.DATE,
                        prompt_text="Extract the notice date.",
                        display_order=0,
                    ),
                    TemplateColumnCreate(
                        name="Borrower Name",
                        column_type=ColumnType.STRING,
                        prompt_text="Extract the borrower name.",
                        display_order=1,
                    ),
                    TemplateColumnCreate(
                        name="Interest Amount",
                        column_type=ColumnType.CURRENCY,
                        prompt_text="Extract the interest amount as a decimal number.",
                        display_order=2,
                    ),
                    TemplateColumnCreate(
                        name="Payment Due Date",
                        column_type=ColumnType.DATE,
                        prompt_text="Extract the payment due date.",
                        display_order=3,
                    ),
                ],
            ),
            actor,
        )
        aggregate = template_service.publish_template(
            db,
            aggregate.template.id,
            actor,
            aggregate.version.lock_version,
        )
        template = aggregate.template

    return SeedResult(
        domain_id=str(domain.id),
        template_id=str(template.id),
        created_domain=created_domain,
        created_template=created_template,
    )


def main() -> None:
    settings = get_settings()
    with SessionFactory() as db:
        result = seed_development_data(db, settings)
    print(
        f"Development seed ready: domain={result.domain_id} template={result.template_id} "
        f"created_domain={result.created_domain} created_template={result.created_template}"
    )


if __name__ == "__main__":
    main()
