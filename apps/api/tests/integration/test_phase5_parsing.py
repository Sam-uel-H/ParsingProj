from __future__ import annotations

from fastapi.testclient import TestClient

from app.documents.dependencies import get_document_extractor, get_object_storage
from app.providers.fakes import FakeDocumentExtractionProvider, InMemoryObjectStorage


def test_published_template_parses_all_types_and_requires_domain_override(
    phase1_client: TestClient,
) -> None:
    from app.main import app

    domain = phase1_client.post("/domains", json={"name": "Parsing Domain"}).json()
    columns = [
        ("Name", "string", None),
        ("Count", "integer", None),
        ("Rate", "decimal", None),
        ("Amount", "currency", None),
        ("Notice Date", "date", None),
        ("Active", "boolean", None),
        ("Currency", "enum", ["USD", "EUR"]),
    ]
    created = phase1_client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Typed Template",
            "columns": [
                {
                    "name": name,
                    "column_type": kind,
                    "enum_values": values,
                    "prompt_text": f"Extract {name}.",
                    "display_order": order,
                }
                for order, (name, kind, values) in enumerate(columns)
            ],
        },
    ).json()
    published = phase1_client.post(
        f"/templates/{created['id']}/publish",
        json={"expected_lock_version": created["current_version"]["lock_version"]},
    )
    assert published.status_code == 200

    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    text = (
        "Name: Sample\nCount: 42\nRate: 12.50\nAmount: $1,234.50\n"
        "Notice Date: 2026-08-24\nActive: yes\nCurrency: usd"
    )
    try:
        document = phase1_client.post(
            "/documents/upload",
            files={"files": ("notice.txt", text.encode(), "text/plain")},
        ).json()["results"][0]["document"]
        phase1_client.post(f"/documents/{document['id']}/extract")
        blocked = phase1_client.post(
            "/parsing-jobs",
            json={"document_id": document["id"], "template_id": created["id"]},
        )
        completed = phase1_client.post(
            "/parsing-jobs",
            json={
                "document_id": document["id"],
                "template_id": created["id"],
                "confirm_domain_override": True,
            },
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)

    assert blocked.status_code == 422
    assert blocked.json()["error"]["details"]["requires_domain_override"] is True
    assert completed.status_code == 200
    job = completed.json()
    assert job["status"] == "completed"
    assert job["domain_override"] is True
    assert job["template_version_id"] == created["current_version"]["id"]
    assert len(job["results"]) == 7
    assert all(result["validation_status"] == "valid" for result in job["results"])
    assert all(result["raw_output"] for result in job["results"])
