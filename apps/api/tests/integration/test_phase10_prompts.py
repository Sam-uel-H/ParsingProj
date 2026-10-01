from __future__ import annotations

from fastapi.testclient import TestClient

from app.documents.dependencies import get_document_extractor, get_object_storage
from app.parsing.dependencies import get_llm_provider
from app.providers.errors import ProviderError
from app.providers.fakes import (
    FakeDocumentExtractionProvider,
    FakeLLMProvider,
    InMemoryObjectStorage,
)
from app.providers.llm import (
    ExtractedValue,
    ExtractionRequest,
    ExtractionResponse,
    PromptSuggestion,
    PromptSuggestionRequest,
)


def _setup(client: TestClient, text: str = "Notice Date: 2026-09-28") -> tuple[str, str, str, str]:
    from app.main import app

    domain = client.post("/domains", json={"name": "Prompt Domain"}).json()
    template = client.post(
        "/templates",
        json={
            "domain_id": domain["id"],
            "name": "Prompt Template",
            "columns": [{"name": "Notice Date", "column_type": "date", "display_order": 0}],
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
        extraction = client.post(f"/documents/{document['id']}/extract").json()
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_document_extractor, None)
    column_id = template["current_version"]["columns"][0]["id"]
    tag = client.post(
        f"/templates/{template['id']}/tagged-examples",
        json={
            "template_column_id": column_id,
            "document_id": document["id"],
            "document_extraction_id": extraction["id"],
            "page_number": 1,
            "selected_text": "2026-09-28",
            "expected_value": "2026-09-28",
            "rectangles": [{"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.02}],
        },
    )
    assert tag.status_code == 201
    return template["id"], column_id, document["id"], extraction["id"]


def test_generate_edit_dry_run_and_accept(phase1_client: TestClient) -> None:
    template_id, column_id, document_id, extraction_id = _setup(phase1_client)
    path = f"/templates/{template_id}/prompt-drafts"
    generated = phase1_client.post(
        path, json={"template_column_id": column_id, "document_id": document_id}
    )
    assert generated.status_code == 201
    draft = generated.json()
    assert draft["document_extraction_id"] == extraction_id
    assert "2026-09-28" in draft["suggested_prompt"]
    assert draft["provider_name"] == "fake"
    edited = phase1_client.put(
        f"{path}/{draft['id']}", json={"edited_prompt": "Find the notice date and return ISO JSON."}
    )
    assert edited.status_code == 200
    run = phase1_client.post(f"{path}/{draft['id']}/dry-runs")
    assert run.status_code == 200
    result = run.json()["dry_runs"][0]
    assert result["status"] == "valid"
    assert result["actual_value"] == "2026-09-28"
    assert result["matches_expected"] is True
    assert result["evidence_verified"] is True
    assert result["evidence"]["quote"] == "Notice Date: 2026-09-28"
    second = phase1_client.post(f"{path}/{draft['id']}/dry-runs")
    assert len(second.json()["dry_runs"]) == 2
    listed = phase1_client.get(path, params={"column_id": column_id, "document_id": document_id})
    assert listed.status_code == 200
    assert listed.json()[0]["edited_prompt"] == "Find the notice date and return ISO JSON."
    lock = phase1_client.get(f"/templates/{template_id}").json()["current_version"]["lock_version"]
    stale = phase1_client.post(
        f"{path}/{draft['id']}/accept", json={"expected_lock_version": lock + 1}
    )
    assert stale.status_code == 409
    accepted = phase1_client.post(
        f"{path}/{draft['id']}/accept", json={"expected_lock_version": lock}
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    template = phase1_client.get(f"/templates/{template_id}").json()
    assert template["current_version"]["columns"][0]["prompt_text"] == (
        "Find the notice date and return ISO JSON."
    )


class InvalidValueProvider(FakeLLMProvider):
    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        return ExtractionResponse(
            values=(ExtractedValue("Notice Date", "not-a-date", "{}", supporting_text="invented"),),
            metadata=self.metadata,
            usage=self.usage,
        )


class FailingProvider(FakeLLMProvider):
    async def suggest_prompt(self, request: PromptSuggestionRequest) -> PromptSuggestion:
        raise ProviderError("unavailable")


class MalformedProvider(FakeLLMProvider):
    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        return ExtractionResponse(values=(), metadata=self.metadata, usage=self.usage)


class BlankSuggestionProvider(FakeLLMProvider):
    async def suggest_prompt(self, request: PromptSuggestionRequest) -> PromptSuggestion:
        return PromptSuggestion(text="  ", metadata=self.metadata, usage=self.usage)


def test_invalid_value_and_unverified_evidence(phase1_client: TestClient) -> None:
    from app.main import app

    template_id, column_id, document_id, _ = _setup(phase1_client)
    path = f"/templates/{template_id}/prompt-drafts"
    draft_id = phase1_client.post(
        path, json={"template_column_id": column_id, "document_id": document_id}
    ).json()["id"]
    app.dependency_overrides[get_llm_provider] = lambda: InvalidValueProvider()
    try:
        result = phase1_client.post(f"{path}/{draft_id}/dry-runs").json()["dry_runs"][0]
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
    assert result["status"] == "invalid"
    assert result["matches_expected"] is False
    assert result["evidence_verified"] is False
    assert result["evidence"] is None


def test_provider_failure_and_malformed_output(phase1_client: TestClient) -> None:
    from app.main import app

    template_id, column_id, document_id, _ = _setup(phase1_client)
    path = f"/templates/{template_id}/prompt-drafts"
    app.dependency_overrides[get_llm_provider] = lambda: FailingProvider()
    try:
        failed = phase1_client.post(
            path, json={"template_column_id": column_id, "document_id": document_id}
        )
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
    assert failed.status_code == 502
    draft_id = phase1_client.post(
        path, json={"template_column_id": column_id, "document_id": document_id}
    ).json()["id"]
    app.dependency_overrides[get_llm_provider] = lambda: MalformedProvider()
    try:
        response = phase1_client.post(f"{path}/{draft_id}/dry-runs")
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
    assert response.status_code == 200
    assert response.json()["dry_runs"][0]["status"] == "provider_error"

    app.dependency_overrides[get_llm_provider] = lambda: BlankSuggestionProvider()
    try:
        blank = phase1_client.post(
            path, json={"template_column_id": column_id, "document_id": document_id}
        )
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
    assert blank.status_code == 502


def test_published_version_cannot_change_prompt_draft(phase1_client: TestClient) -> None:
    template_id, column_id, document_id, _ = _setup(phase1_client)
    path = f"/templates/{template_id}/prompt-drafts"
    draft_id = phase1_client.post(
        path, json={"template_column_id": column_id, "document_id": document_id}
    ).json()["id"]
    lock = phase1_client.get(f"/templates/{template_id}").json()["current_version"]["lock_version"]
    accepted = phase1_client.post(f"{path}/{draft_id}/accept", json={"expected_lock_version": lock})
    assert accepted.status_code == 200
    current_lock = phase1_client.get(f"/templates/{template_id}").json()["current_version"][
        "lock_version"
    ]
    published = phase1_client.post(
        f"/templates/{template_id}/publish", json={"expected_lock_version": current_lock}
    )
    assert published.status_code == 200
    changed = phase1_client.put(f"{path}/{draft_id}", json={"edited_prompt": "Should not change"})
    assert changed.status_code == 409
    rerun = phase1_client.post(f"{path}/{draft_id}/dry-runs")
    assert rerun.status_code == 409
