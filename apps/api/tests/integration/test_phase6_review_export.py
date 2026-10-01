from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from app.documents.dependencies import get_document_extractor, get_object_storage
from app.providers.fakes import FakeDocumentExtractionProvider, InMemoryObjectStorage


def _run_typed_job(phase1_client: TestClient) -> dict:
    from app.main import app

    domain = phase1_client.post("/domains", json={"name": "Review Domain"}).json()
    columns = [
        ("Name", "string", None, "Original Name"),
        ("Count", "integer", None, "1"),
        ("Rate", "decimal", None, "1.25"),
        ("Amount", "currency", None, "$5.00"),
        ("Notice Date", "date", None, "2026-09-01"),
        ("Active", "boolean", None, "no"),
        ("Currency", "enum", ["USD", "EUR"], "USD"),
    ]
    template = phase1_client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Review Template",
            "columns": [
                {
                    "name": name,
                    "column_type": kind,
                    "enum_values": values,
                    "prompt_text": f"Extract {name}.",
                    "display_order": order,
                }
                for order, (name, kind, values, _) in enumerate(columns)
            ],
        },
    ).json()
    phase1_client.post(
        f"/templates/{template['id']}/publish",
        json={"expected_lock_version": template["current_version"]["lock_version"]},
    )

    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    try:
        text = "\n".join(f"{name}: {value}" for name, _, _, value in columns)
        document = phase1_client.post(
            "/documents/upload",
            files={"files": ("review.txt", text.encode(), "text/plain")},
        ).json()["results"][0]["document"]
        phase1_client.post(f"/documents/{document['id']}/extract")
        return phase1_client.post(
            "/parsing-jobs",
            json={
                "document_id": document["id"],
                "template_id": template["id"],
                "confirm_domain_override": True,
            },
        ).json()
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)


def test_reviewer_corrects_results_and_exports_reviewed_values(
    phase1_client: TestClient,
) -> None:
    job = _run_typed_job(phase1_client)
    corrections = {
        "Name": "Reviewed Name",
        "Count": 42,
        "Rate": "12.50",
        "Amount": "$1,234.50",
        "Notice Date": "2026-09-11",
        "Active": "yes",
        "Currency": "eur",
    }
    expected = {
        "Name": "Reviewed Name",
        "Count": "42",
        "Rate": "12.50",
        "Amount": "1234.50",
        "Notice Date": "2026-09-11",
        "Active": "true",
        "Currency": "EUR",
    }

    for result in job["results"]:
        corrected = phase1_client.patch(
            f"/parsing-jobs/{job['id']}/results/{result['id']}",
            json={"value": corrections[result["column_name"]]},
        )
        assert corrected.status_code == 200
        body = corrected.json()
        assert body["canonical_value"] == result["canonical_value"]
        assert body["reviewed_value"] == expected[result["column_name"]]
        assert body["current_value"] == expected[result["column_name"]]
        assert body["human_verified"] is True
        assert body["reviewed_by_id"] is not None
        assert body["reviewed_at"] is not None

    invalid = phase1_client.patch(
        f"/parsing-jobs/{job['id']}/results/{job['results'][4]['id']}",
        json={"value": "tomorrow"},
    )
    assert invalid.status_code == 422
    assert phase1_client.get(f"/parsing-jobs/{job['id']}").json()["status"] == "completed"

    csv_response = phase1_client.get(f"/parsing-jobs/{job['id']}/export.csv")
    rows = list(csv.reader(io.StringIO(csv_response.text)))
    assert rows == [list(expected.keys()), list(expected.values())]

    json_response = phase1_client.get(f"/parsing-jobs/{job['id']}/export.json")
    assert json_response.status_code == 200
    exported = json_response.json()["results"]
    assert [item["column_name"] for item in exported] == list(expected.keys())
    assert exported[1]["value"] == 42
    assert exported[5]["value"] is True
    assert exported[6]["value"] == "EUR"
