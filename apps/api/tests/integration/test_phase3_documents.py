from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.documents.dependencies import get_object_storage
from app.providers.fakes import InMemoryObjectStorage

pytestmark = pytest.mark.integration


def docx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


SUPPORTED_FILES: list[tuple[str, bytes, str, str]] = [
    ("sample.pdf", b"%PDF-1.4\nminimal", "application/pdf", "pdf"),
    (
        "sample.docx",
        docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    ("sample.tiff", b"II*\x00minimal", "image/tiff", "tiff"),
    ("sample.png", b"\x89PNG\r\n\x1a\nminimal", "image/png", "png"),
    ("sample.jpg", b"\xff\xd8\xffminimal", "image/jpeg", "jpeg"),
    ("sample.txt", b"plain text", "text/plain", "text"),
]


@pytest.fixture
def document_storage(phase1_client: TestClient) -> InMemoryObjectStorage:
    from app.main import app

    storage = InMemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_object_storage, None)


def create_domain(client: TestClient) -> dict[str, Any]:
    response = client.post("/domains", json={"name": "Uploaded Notices"})
    assert response.status_code == 201
    return response.json()


def test_multi_upload_accepts_every_supported_type_and_isolates_failure(
    phase1_client: TestClient,
    document_storage: InMemoryObjectStorage,
) -> None:
    domain = create_domain(phase1_client)
    files = [
        ("files", (file_name, content, mime)) for file_name, content, mime, _ in SUPPORTED_FILES
    ]
    files.append(("files", ("malware.exe", b"\x00\x01binary", "application/octet-stream")))

    response = phase1_client.post(
        "/documents/upload",
        data={"domain_id": domain["id"]},
        files=files,
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["success"] for result in results] == [True] * 6 + [False]
    assert [result["document"]["file_type"] for result in results[:6]] == [
        expected for *_, expected in SUPPORTED_FILES
    ]
    assert results[-1]["error"]["code"] == "invalid_upload"

    listed = phase1_client.get(f"/documents?domain_id={domain['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 6

    pdf = results[0]["document"]
    assert pdf["checksum_sha256"] == hashlib.sha256(SUPPORTED_FILES[0][1]).hexdigest()
    assert pdf["file_size"] == len(SUPPORTED_FILES[0][1])
    assert pdf["processing_status"] == "pending"
    downloaded = phase1_client.get(f"/documents/{pdf['id']}/content")
    assert downloaded.status_code == 200
    assert downloaded.content == SUPPORTED_FILES[0][1]
    assert awaitable_exists(document_storage, pdf["id"])


def awaitable_exists(storage: InMemoryObjectStorage, document_id: str) -> bool:
    import asyncio

    return asyncio.run(storage.exists(f"documents/{document_id}/original.pdf"))


def test_upload_can_be_unassigned_and_sanitizes_display_name(
    phase1_client: TestClient,
    document_storage: InMemoryObjectStorage,
) -> None:
    response = phase1_client.post(
        "/documents/upload",
        files={"files": ("../unsafe.txt", b"safe text", "text/plain")},
    )

    document = response.json()["results"][0]["document"]
    assert response.status_code == 200
    assert document["domain_id"] is None
    assert document["original_file_name"] == "unsafe.txt"
    assert phase1_client.get(f"/documents/{document['id']}").status_code == 200


def test_upload_rejects_oversize_and_mismatched_mime(
    phase1_client: TestClient,
    document_storage: InMemoryObjectStorage,
) -> None:
    from app.main import app

    settings = get_settings().model_copy(update={"max_upload_size_bytes": 8})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = phase1_client.post(
            "/documents/upload",
            files=[
                ("files", ("large.txt", b"123456789", "text/plain")),
                ("files", ("wrong.pdf", b"%PDF-1.4", "text/plain")),
            ],
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    results = response.json()["results"]
    assert response.status_code == 200
    assert results[0]["error"]["message"].startswith("File exceeds")
    assert results[1]["error"]["message"].startswith("MIME type does not match")
    assert phase1_client.get("/documents").json() == []
