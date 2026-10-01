from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.documents.dependencies import get_document_extractor, get_object_storage
from app.providers.fakes import FakeDocumentExtractionProvider, InMemoryObjectStorage


def _create_template(
    client: TestClient,
    *,
    domain_name: str = "Lifecycle Notices",
    template_name: str = "Payment Notice",
) -> dict[str, Any]:
    domain = client.post("/domains", json={"name": domain_name}).json()
    response = client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": template_name,
            "description": "Template lifecycle test data",
            "columns": [
                {
                    "name": "Notice Date",
                    "column_type": "date",
                    "prompt_text": "Extract Notice Date.",
                    "display_order": 0,
                },
                {
                    "name": "Amount",
                    "column_type": "currency",
                    "prompt_text": "Extract Amount.",
                    "display_order": 1,
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _publish(client: TestClient, template: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"/templates/{template['id']}/publish",
        json={"expected_lock_version": template["current_version"]["lock_version"]},
    )
    assert response.status_code == 200
    return response.json()


def test_searches_and_filters_current_template_state(phase1_client: TestClient) -> None:
    draft = _create_template(
        phase1_client,
        domain_name="Lifecycle A",
        template_name="Quarterly Payment Notice",
    )
    published = _publish(
        phase1_client,
        _create_template(
            phase1_client,
            domain_name="Lifecycle B",
            template_name="Annual Interest Notice",
        ),
    )

    search = phase1_client.get("/templates", params={"search": "interest"})
    domain = phase1_client.get("/templates", params={"domain_id": draft["domain_id"]})
    author = phase1_client.get("/templates", params={"author": "developer"})
    status = phase1_client.get("/templates", params={"status": "published"})

    assert [item["id"] for item in search.json()] == [published["id"]]
    assert [item["id"] for item in domain.json()] == [draft["id"]]
    assert {item["id"] for item in author.json()} == {draft["id"], published["id"]}
    assert [item["id"] for item in status.json()] == [published["id"]]
    assert status.json()[0]["created_by_name"] == "Development User"


def test_new_version_copies_published_data_and_preserves_history(
    phase1_client: TestClient,
) -> None:
    from app.main import app

    published = _publish(phase1_client, _create_template(phase1_client))
    version_one = published["current_version"]
    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    try:
        document = phase1_client.post(
            "/documents/upload",
            data={"domain_id": published["domain_id"]},
            files={
                "files": (
                    "version-one.txt",
                    b"Notice Date: 2026-09-26\nAmount: $10.00",
                    "text/plain",
                )
            },
        ).json()["results"][0]["document"]
        phase1_client.post(f"/documents/{document['id']}/extract")
        historical_job = phase1_client.post(
            "/parsing-jobs",
            json={"document_id": document["id"], "template_id": published["id"]},
        ).json()
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)

    created = phase1_client.post(f"/templates/{published['id']}/versions", json={})

    assert created.status_code == 201
    version_two = created.json()["current_version"]
    assert version_two["version_number"] == 2
    assert version_two["status"] == "draft"
    assert version_two["created_by_id"]
    assert [column["name"] for column in version_two["columns"]] == [
        "Notice Date",
        "Amount",
    ]
    assert [column["prompt_text"] for column in version_two["columns"]] == [
        "Extract Notice Date.",
        "Extract Amount.",
    ]

    updated = phase1_client.put(
        f"/templates/{published['id']}/draft",
        json={
            "domain_id": published["domain_id"],
            "name": "Payment Notice Revised",
            "description": "Version two",
            "expected_lock_version": version_two["lock_version"],
            "columns": [
                {**column, "name": f"{column['name']} V2"} for column in version_two["columns"]
            ],
        },
    )
    assert updated.status_code == 200

    duplicate_draft = phase1_client.post(f"/templates/{published['id']}/versions", json={})
    assert duplicate_draft.status_code == 409
    published_two = _publish(phase1_client, updated.json())
    assert published_two["current_version"]["version_number"] == 2

    history = phase1_client.get(f"/templates/{published['id']}/versions")
    assert history.status_code == 200
    assert [version["version_number"] for version in history.json()] == [2, 1]
    assert history.json()[1]["id"] == version_one["id"]
    assert history.json()[1]["name"] == "Payment Notice"
    assert [column["name"] for column in history.json()[1]["columns"]] == [
        "Notice Date",
        "Amount",
    ]

    persisted_job = phase1_client.get(f"/parsing-jobs/{historical_job['id']}")
    assert persisted_job.status_code == 200
    assert persisted_job.json()["template_version_id"] == version_one["id"]


def test_clone_archive_and_used_template_deletion_rules(
    phase1_client: TestClient,
) -> None:
    from app.main import app

    published = _publish(phase1_client, _create_template(phase1_client))
    clone = phase1_client.post(
        f"/templates/{published['id']}/clone",
        json={"name": "Payment Notice Copy"},
    )
    assert clone.status_code == 201
    cloned = clone.json()
    assert cloned["id"] != published["id"]
    assert cloned["current_version"]["status"] == "draft"
    assert cloned["current_version"]["name"] == "Payment Notice Copy"
    assert [column["prompt_text"] for column in cloned["current_version"]["columns"]] == [
        "Extract Notice Date.",
        "Extract Amount.",
    ]
    assert phase1_client.delete(f"/templates/{cloned['id']}").status_code == 204

    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    try:
        document = phase1_client.post(
            "/documents/upload",
            data={"domain_id": published["domain_id"]},
            files={
                "files": (
                    "notice.txt",
                    b"Notice Date: 2026-09-26\nAmount: $10.00",
                    "text/plain",
                )
            },
        ).json()["results"][0]["document"]
        phase1_client.post(f"/documents/{document['id']}/extract")
        job = phase1_client.post(
            "/parsing-jobs",
            json={"document_id": document["id"], "template_id": published["id"]},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)

    assert job.status_code == 200
    archived = phase1_client.post(f"/templates/{published['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    assert (
        phase1_client.get("/templates", params={"status": "archived"}).json()[0]["id"]
        == published["id"]
    )

    delete_used = phase1_client.delete(f"/templates/{published['id']}")
    assert delete_used.status_code == 409
    assert "parsing jobs" in delete_used.json()["error"]["message"]
    parse_archived = phase1_client.post(
        "/parsing-jobs",
        json={"document_id": document["id"], "template_id": published["id"]},
    )
    assert parse_archived.status_code == 422
    create_from_archived = phase1_client.post(f"/templates/{published['id']}/versions", json={})
    assert create_from_archived.status_code == 409


def test_reorder_columns_is_atomic_and_controls_export_order(
    phase1_client: TestClient,
) -> None:
    from app.main import app

    draft = _create_template(phase1_client)
    version = draft["current_version"]
    original_ids = [column["id"] for column in version["columns"]]

    invalid = phase1_client.put(
        f"/templates/{draft['id']}/columns/order",
        json={
            "expected_lock_version": version["lock_version"],
            "column_ids": [original_ids[0]],
        },
    )
    assert invalid.status_code == 422
    unchanged = phase1_client.get(f"/templates/{draft['id']}").json()
    assert [column["id"] for column in unchanged["current_version"]["columns"]] == original_ids

    reordered = phase1_client.put(
        f"/templates/{draft['id']}/columns/order",
        json={
            "expected_lock_version": version["lock_version"],
            "column_ids": list(reversed(original_ids)),
        },
    )
    assert reordered.status_code == 200
    assert [column["name"] for column in reordered.json()["current_version"]["columns"]] == [
        "Amount",
        "Notice Date",
    ]
    published = _publish(phase1_client, reordered.json())

    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    try:
        document = phase1_client.post(
            "/documents/upload",
            data={"domain_id": published["domain_id"]},
            files={
                "files": (
                    "notice.txt",
                    b"Notice Date: 2026-09-26\nAmount: $10.00",
                    "text/plain",
                )
            },
        ).json()["results"][0]["document"]
        phase1_client.post(f"/documents/{document['id']}/extract")
        job = phase1_client.post(
            "/parsing-jobs",
            json={"document_id": document["id"], "template_id": draft["id"]},
        ).json()
        exported = phase1_client.get(f"/parsing-jobs/{job['id']}/export.csv")
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)

    assert exported.status_code == 200
    assert exported.text.splitlines()[0].startswith("Amount,Notice Date")
