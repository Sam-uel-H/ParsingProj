from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.domains.models import Domain
from app.templates.models import ColumnType, Template, TemplateColumn

pytestmark = pytest.mark.integration


def create_domain(client: TestClient, name: str = "Agent Bank Notices") -> dict[str, object]:
    response = client.post(
        "/domains",
        json={"name": name, "description": "Interest and payment notices"},
    )
    assert response.status_code == 201
    return response.json()


def test_domain_crud_has_user_and_timestamp_attribution(phase1_client: TestClient) -> None:
    domain = create_domain(phase1_client)

    assert domain["created_by_id"] == domain["updated_by_id"]
    assert domain["created_at"]
    assert domain["updated_at"]

    updated = phase1_client.patch(
        f"/domains/{domain['id']}",
        json={"description": "Updated description"},
    )
    listed = phase1_client.get("/domains")

    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated description"
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()] == ["Agent Bank Notices"]


def test_template_columns_are_returned_in_display_order(phase1_client: TestClient) -> None:
    domain = create_domain(phase1_client)
    created = phase1_client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Interest Notice",
            "description": "Draft template",
            "columns": [
                {
                    "name": "Interest Amount",
                    "column_type": "currency",
                    "display_order": 2,
                },
                {
                    "name": "Notice Date",
                    "column_type": "date",
                    "display_order": 0,
                },
            ],
        },
    )

    assert created.status_code == 201
    template_id = created.json()["id"]
    added = phase1_client.post(
        f"/templates/{template_id}/columns",
        json={
            "name": "Currency",
            "column_type": "enum",
            "enum_values": ["USD", "EUR", "GBP"],
            "display_order": 1,
        },
    )
    retrieved = phase1_client.get(f"/templates/{template_id}")

    assert added.status_code == 201
    assert retrieved.status_code == 200
    body = retrieved.json()
    assert body["current_version"]["status"] == "draft"
    assert body["current_version"]["version_number"] == 1
    assert [column["name"] for column in body["current_version"]["columns"]] == [
        "Notice Date",
        "Currency",
        "Interest Amount",
    ]
    assert body["created_by_id"] == body["current_version"]["created_by_id"]


def test_duplicate_column_name_returns_structured_conflict(phase1_client: TestClient) -> None:
    domain = create_domain(phase1_client)
    created = phase1_client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Interest Notice",
            "columns": [{"name": "Notice Date", "column_type": "date", "display_order": 0}],
        },
    )
    template_id = created.json()["id"]

    duplicate = phase1_client.post(
        f"/templates/{template_id}/columns",
        json={"name": "Notice Date", "column_type": "date", "display_order": 1},
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "error": {
            "code": "conflict",
            "message": "A column with this name already exists in the draft version.",
            "details": {"field": "name"},
        }
    }


def test_template_requires_a_real_domain_and_clear_validation(phase1_client: TestClient) -> None:
    missing_field = phase1_client.post("/templates", json={"name": "Invalid"})
    missing_record = phase1_client.post(
        "/templates",
        json={"domain_id": str(uuid.uuid4()), "name": "Invalid"},
    )

    assert missing_field.status_code == 422
    assert missing_field.json()["error"]["code"] == "validation_error"
    assert missing_record.status_code == 404
    assert missing_record.json()["error"] == {
        "code": "not_found",
        "message": "Domain was not found.",
    }


def test_database_constraints_reject_invalid_direct_writes(phase1_client: TestClient) -> None:
    from app.db.session import SessionFactory

    domain = create_domain(phase1_client)
    created = phase1_client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Constraint Test",
            "columns": [{"name": "Notice Date", "column_type": "date", "display_order": 0}],
        },
    ).json()
    actor_id = uuid.UUID(str(domain["created_by_id"]))

    with SessionFactory() as db:
        db.add(
            Domain(
                name="Agent Bank Notices",
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            Template(
                domain_id=uuid.uuid4(),
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        version_id = uuid.UUID(created["current_version"]["id"])
        db.add(
            TemplateColumn(
                template_version_id=version_id,
                name="Notice Date",
                column_type=ColumnType.DATE,
                display_order=5,
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
