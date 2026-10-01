from __future__ import annotations

from fastapi.testclient import TestClient

from app.documents.dependencies import get_document_extractor, get_object_storage
from app.providers.fakes import FakeDocumentExtractionProvider, InMemoryObjectStorage


def _setup(
    client: TestClient,
    text: str = "Notice Date: 2026-09-27\nAmount: $10\fLater Value: 42",
) -> dict:
    from app.main import app

    domain = client.post("/domains", json={"name": "Tagging Domain"}).json()
    template = client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Tagging Template",
            "columns": [
                {"name": "Notice Date", "column_type": "date", "display_order": 0},
                {"name": "Amount", "column_type": "currency", "display_order": 1},
            ],
        },
    ).json()
    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    try:
        document = client.post(
            "/documents/upload",
            data={"domain_id": domain["id"]},
            files={"files": ("notice.txt", text.encode(), "text/plain")},
        ).json()["results"][0]["document"]
        extraction_response = client.post(f"/documents/{document['id']}/extract")
        assert extraction_response.status_code == 200
        extraction = extraction_response.json()
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)
    return {
        "domain": domain,
        "template": template,
        "document": document,
        "extraction": extraction,
    }


def _payload(data: dict, *, column: int = 0, page: int = 1, text: str = "2026-09-27") -> dict:
    return {
        "template_column_id": data["template"]["current_version"]["columns"][column]["id"],
        "document_id": data["document"]["id"],
        "document_extraction_id": data["extraction"]["id"],
        "page_number": page,
        "selected_text": text,
        "expected_value": text,
        "rectangles": [{"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.02}],
    }


def test_save_reload_replace_and_delete_tags_on_multiple_pages(phase1_client: TestClient) -> None:
    data = _setup(phase1_client)
    path = f"/templates/{data['template']['id']}/tagged-examples"
    first = phase1_client.post(path, json=_payload(data))
    assert first.status_code == 201
    tag = first.json()
    assert tag["tagged_value"] == "2026-09-27"
    selected = data["extraction"]["full_text"][tag["char_start"] : tag["char_end"]]
    assert selected == tag["tagged_value"]
    assert tag["text_block_ids"] == [data["extraction"]["pages"][0]["blocks"][0]["id"]]

    later = phase1_client.post(path, json=_payload(data, column=1, page=2, text="42"))
    assert later.status_code == 201
    assert later.json()["page_number"] == 2
    assert later.json()["char_start"] > tag["char_end"]
    listed = phase1_client.get(path, params={"document_id": data["document"]["id"]})
    assert {item["id"] for item in listed.json()} == {tag["id"], later.json()["id"]}

    replacement = _payload(data, text="Notice Date: 2026-09-27")
    replacement["expected_value"] = "2026-09-27"
    replaced = phase1_client.put(f"{path}/{tag['id']}", json=replacement)
    assert replaced.status_code == 200
    assert replaced.json()["id"] == tag["id"]
    assert replaced.json()["tagged_value"] == "Notice Date: 2026-09-27"
    assert phase1_client.delete(f"{path}/{tag['id']}").status_code == 204
    assert len(phase1_client.get(path, params={"document_id": data["document"]["id"]}).json()) == 1


def test_multiblock_selection_and_explicit_mapping_failures(phase1_client: TestClient) -> None:
    data = _setup(phase1_client, "Alpha: 11\nBeta: 22\fLater Value: 42")
    path = f"/templates/{data['template']['id']}/tagged-examples"
    multi = phase1_client.post(path, json=_payload(data, text="11\nBeta: 22"))
    assert multi.status_code == 201
    assert len(multi.json()["text_block_ids"]) == 2

    unmapped = phase1_client.post(path, json=_payload(data, column=1, text="not on page"))
    assert unmapped.status_code == 422
    assert "could not be mapped" in unmapped.json()["error"]["message"]


def test_ambiguous_selection_and_incompatible_domain_are_rejected(
    phase1_client: TestClient,
) -> None:
    data = _setup(phase1_client, "Amount: 42\nRepeated: 42")
    path = f"/templates/{data['template']['id']}/tagged-examples"
    ambiguous = phase1_client.post(path, json=_payload(data, text="42"))
    assert ambiguous.status_code == 422
    assert "ambiguous" in ambiguous.json()["error"]["message"]

    other_domain = phase1_client.post("/domains", json={"name": "Other Tag Domain"}).json()
    foreign_document = phase1_client.post(
        "/documents/upload",
        data={"domain_id": other_domain["id"]},
        files={"files": ("other.txt", b"Amount: 42", "text/plain")},
    ).json()["results"][0]["document"]
    incompatible = _payload(data)
    incompatible["document_id"] = foreign_document["id"]
    response = phase1_client.post(path, json=incompatible)
    assert response.status_code == 422
    assert "same domain" in response.json()["error"]["message"]


def test_rejected_repeat_extraction_does_not_move_tag(phase1_client: TestClient) -> None:
    data = _setup(phase1_client)
    path = f"/templates/{data['template']['id']}/tagged-examples"
    original = phase1_client.post(path, json=_payload(data)).json()
    response = phase1_client.post(f"/documents/{data['document']['id']}/extract")
    assert response.status_code == 409

    listed = phase1_client.get(path, params={"document_id": data["document"]["id"]}).json()
    assert len(listed) == 1
    assert listed[0]["id"] == original["id"]
    assert listed[0]["document_extraction_id"] == original["document_extraction_id"]
