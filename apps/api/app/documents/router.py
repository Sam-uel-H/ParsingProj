from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_development_user
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.documents import extraction_service, service
from app.documents.dependencies import get_document_extractor, get_object_storage
from app.documents.models import Document
from app.documents.schemas import DocumentExtractionRead, DocumentRead, DocumentUploadBatch
from app.providers.document_extraction import DocumentExtractionProvider
from app.providers.object_storage import ObjectStorage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadBatch, summary="Upload documents")
async def upload_documents(
    files: Annotated[list[UploadFile], File()],
    domain_id: Annotated[uuid.UUID | None, Form()] = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_development_user),
    storage: ObjectStorage = Depends(get_object_storage),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadBatch:
    return DocumentUploadBatch(
        results=await service.upload_documents(
            db,
            files,
            domain_id,
            actor,
            storage,
            settings.max_upload_size_bytes,
        )
    )


@router.get("", response_model=list[DocumentRead], summary="List documents")
def list_documents(
    domain_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[Document]:
    return service.list_documents(db, domain_id)


@router.get("/{document_id}", response_model=DocumentRead, summary="Get document metadata")
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> Document:
    return service.get_document(db, document_id)


@router.get("/{document_id}/content", summary="Download the original document")
async def get_document_content(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_development_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    document = service.get_document(db, document_id)
    content = await storage.get(document.object_storage_key)
    ascii_name = document.original_file_name.encode("ascii", "ignore").decode() or "document"
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(document.original_file_name)}"
    )
    return Response(
        content=content,
        media_type=document.content_type,
        headers={"Content-Disposition": disposition},
    )


@router.post(
    "/{document_id}/extract",
    response_model=DocumentExtractionRead,
    summary="Extract a pending document",
)
async def extract_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_development_user),
    storage: ObjectStorage = Depends(get_object_storage),
    provider: DocumentExtractionProvider = Depends(get_document_extractor),
    settings: Settings = Depends(get_settings),
) -> DocumentExtractionRead:
    await extraction_service.run_extraction(
        db, document_id, storage, provider, settings.extraction_timeout_seconds
    )
    return extraction_service.get_active_extraction(db, document_id)


@router.get(
    "/{document_id}/extraction",
    response_model=DocumentExtractionRead,
    summary="Get the active document extraction",
)
def get_extraction(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentExtractionRead:
    return extraction_service.get_active_extraction(db, document_id)


@router.get("/{document_id}/pages/{page_number}/preview", summary="Preview a document page")
async def get_page_preview(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_development_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    page = extraction_service.get_page(db, document_id, page_number)
    return Response(
        content=await storage.get(page.preview_object_key),
        media_type=page.preview_content_type,
        headers={"Content-Disposition": "inline"},
    )
