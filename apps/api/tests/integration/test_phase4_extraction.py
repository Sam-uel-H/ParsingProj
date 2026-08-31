from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.documents.dependencies import get_document_extractor, get_object_storage
from app.providers.document_extraction import (
    DocumentExtractionProvider,
    DocumentExtractionRequest,
    ExtractedDocument,
    ExtractedPage,
    Point,
    TextBlock,
)
from app.providers.errors import ProviderError
from app.providers.fakes import FakeDocumentExtractionProvider, InMemoryObjectStorage

pytestmark = pytest.mark.integration


class FailingExtractor(DocumentExtractionProvider):
    async def extract(self, request: DocumentExtractionRequest) -> ExtractedDocument:
        raise ProviderError(f"Could not extract {request.filename}.")


class ScannedImageExtractor(DocumentExtractionProvider):
    async def extract(self, request: DocumentExtractionRequest) -> ExtractedDocument:
        block = TextBlock(
            page_number=1,
            text="Scanned notice",
            reading_order=0,
            char_start=0,
            char_end=14,
            polygon=(Point(10, 10), Point(190, 10), Point(190, 40), Point(10, 40)),
            confidence=0.91,
        )
        return ExtractedDocument(
            full_text="Scanned notice",
            pages=(ExtractedPage(1, "Scanned notice", (block,), 200, 100),),
            provider="fake-ocr",
            provider_version="1",
        )


class SlowExtractor(DocumentExtractionProvider):
    async def extract(self, request: DocumentExtractionRequest) -> ExtractedDocument:
        await asyncio.sleep(0.1)
        raise AssertionError("timeout should cancel extraction")


def upload_text(client: TestClient, storage: InMemoryObjectStorage) -> dict[str, object]:
    from app.main import app

    app.dependency_overrides[get_object_storage] = lambda: storage
    response = client.post(
        "/documents/upload",
        files={"files": ("notice.txt", b"first line\nsecond\fpage two", "text/plain")},
    )
    assert response.status_code == 200
    return response.json()["results"][0]["document"]


def test_extraction_persists_pages_blocks_offsets_and_preview(
    phase1_client: TestClient,
) -> None:
    from app.main import app

    storage = InMemoryObjectStorage()
    document = upload_text(phase1_client, storage)
    app.dependency_overrides[get_document_extractor] = lambda: FakeDocumentExtractionProvider()
    try:
        response = phase1_client.post(f"/documents/{document['id']}/extract")
        preview = phase1_client.get(f"/documents/{document['id']}/pages/2/preview")
        original = phase1_client.get(f"/documents/{document['id']}/content")
    finally:
        app.dependency_overrides.pop(get_document_extractor, None)
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 200
    extraction = response.json()
    assert extraction["status"] == "succeeded"
    assert len(extraction["pages"]) == 2
    block = extraction["pages"][1]["blocks"][0]
    assert extraction["full_text"][block["char_start"] : block["char_end"]] == block["text"]
    assert all(0 <= point["x"] <= extraction["pages"][1]["width"] for point in block["polygon"])
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/svg+xml")
    assert original.content == b"first line\nsecond\fpage two"


def test_provider_failure_is_visible_and_original_survives(phase1_client: TestClient) -> None:
    from app.main import app

    storage = InMemoryObjectStorage()
    document = upload_text(phase1_client, storage)
    app.dependency_overrides[get_document_extractor] = lambda: FailingExtractor()
    try:
        response = phase1_client.post(f"/documents/{document['id']}/extract")
        detail = phase1_client.get(f"/documents/{document['id']}")
        original = phase1_client.get(f"/documents/{document['id']}/content")
    finally:
        app.dependency_overrides.pop(get_document_extractor, None)
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "extraction_failed"
    assert detail.json()["processing_status"] == "failed"
    assert original.content.startswith(b"first line")


def test_fake_ocr_contract_preserves_coordinates() -> None:
    result = asyncio.run(
        ScannedImageExtractor().extract(
            DocumentExtractionRequest("scan.png", b"image", "image/png")
        )
    )
    assert result.pages[0].blocks[0].confidence == 0.91
    assert result.pages[0].blocks[0].polygon == (
        Point(10, 10),
        Point(190, 10),
        Point(190, 40),
        Point(10, 40),
    )


def test_provider_timeout_is_recorded(phase1_client: TestClient) -> None:
    from app.main import app

    storage = InMemoryObjectStorage()
    document = upload_text(phase1_client, storage)
    app.dependency_overrides[get_document_extractor] = lambda: SlowExtractor()
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"extraction_timeout_seconds": 0.001}
    )
    try:
        response = phase1_client.post(f"/documents/{document['id']}/extract")
    finally:
        app.dependency_overrides.pop(get_document_extractor, None)
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_settings, None)

    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "extraction_timeout"
