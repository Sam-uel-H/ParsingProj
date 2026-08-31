from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def create_draft(client: TestClient, *, prompt: str | None = None) -> dict[str, Any]:
    domain = client.post(
        "/domains",
        json={"name": "Loan Notices", "description": "Bank loan notices"},
    )
    assert domain.status_code == 201
    created = client.post(
        "/templates",
        json={
            "domain_id": domain.json()["id"],
            "name": "Payment Notice",
            "columns": [
                {
                    "name": "Amount",
                    "column_type": "currency",
                    "prompt_text": prompt,
                    "display_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201
    return created.json()


def test_complete_draft_update_increments_lock(phase1_client: TestClient) -> None:
    draft = create_draft(phase1_client)
    version = draft["current_version"]
    response = phase1_client.put(
        f"/templates/{draft['id']}/draft",
        json={
            "domain_id": draft["domain_id"],
            "name": "Updated Payment Notice",
            "description": "Still a draft",
            "expected_lock_version": version["lock_version"],
            "columns": [
                {
                    "id": version["columns"][0]["id"],
                    "name": "Amount Due",
                    "column_type": "currency",
                    "prompt_text": None,
                    "display_order": 0,
                },
                {
                    "name": "Currency",
                    "column_type": "enum",
                    "enum_values": ["USD", "EUR"],
                    "prompt_text": None,
                    "display_order": 1,
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_version"]["name"] == "Updated Payment Notice"
    assert body["current_version"]["lock_version"] == version["lock_version"] + 1
    assert [column["name"] for column in body["current_version"]["columns"]] == [
        "Amount Due",
        "Currency",
    ]


def test_failed_publish_is_structured_and_leaves_draft_unchanged(
    phase1_client: TestClient,
) -> None:
    draft = create_draft(phase1_client)
    version = draft["current_version"]

    response = phase1_client.post(
        f"/templates/{draft['id']}/publish",
        json={"expected_lock_version": version["lock_version"]},
    )
    current = phase1_client.get(f"/templates/{draft['id']}").json()["current_version"]

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["fields"][0]["path"] == ("columns.0.prompt_text")
    assert current["status"] == "draft"
    assert current["lock_version"] == version["lock_version"]
    assert current["published_at"] is None


def test_publishing_is_transactional_and_published_version_is_immutable(
    phase1_client: TestClient,
) -> None:
    draft = create_draft(phase1_client, prompt="Extract the total amount due.")
    version = draft["current_version"]
    published = phase1_client.post(
        f"/templates/{draft['id']}/publish",
        json={"expected_lock_version": version["lock_version"]},
    )

    assert published.status_code == 200
    result = published.json()["current_version"]
    assert result["status"] == "published"
    assert result["published_at"]
    assert result["published_by_id"]
    assert result["lock_version"] == version["lock_version"] + 1

    update = phase1_client.put(
        f"/templates/{draft['id']}/draft",
        json={
            "domain_id": draft["domain_id"],
            "name": "Changed after publication",
            "expected_lock_version": result["lock_version"],
            "columns": result["columns"],
        },
    )
    add = phase1_client.post(
        f"/templates/{draft['id']}/columns",
        params={"expected_lock_version": result["lock_version"]},
        json={"name": "Forbidden", "column_type": "string", "display_order": 1},
    )

    assert update.status_code == 409
    assert update.json()["error"]["code"] == "invalid_operation"
    assert add.status_code == 409
    assert add.json()["error"]["code"] == "invalid_operation"


def test_stale_writer_receives_current_lock_version(phase1_client: TestClient) -> None:
    draft = create_draft(phase1_client, prompt="Extract amount.")
    version = draft["current_version"]
    column = version["columns"][0]
    updated = phase1_client.patch(
        f"/templates/{draft['id']}/columns/{column['id']}",
        json={
            "name": "Total Amount",
            "column_type": "currency",
            "prompt_text": "Extract total amount.",
            "display_order": 0,
            "expected_lock_version": version["lock_version"],
        },
    )
    stale = phase1_client.delete(
        f"/templates/{draft['id']}/columns/{column['id']}",
        params={"expected_lock_version": version["lock_version"]},
    )

    assert updated.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_lock_version"] == (version["lock_version"] + 1)
