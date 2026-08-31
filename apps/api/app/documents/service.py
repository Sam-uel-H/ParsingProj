from __future__ import annotations

import hashlib
import re
import uuid
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import NotFoundError
from app.documents.models import (
    Document,
    DocumentFileType,
    DocumentProcessingStatus,
    DocumentUploadStatus,
)
from app.documents.schemas import DocumentRead, DocumentUploadResult, UploadErrorRead
from app.domains.models import Domain
from app.providers.object_storage import ObjectStorage


@dataclass(frozen=True, slots=True)
class VerifiedUpload:
    file_name: str
    file_type: DocumentFileType
    content_type: str
    extension: str
    content: bytes


class UploadValidationError(ValueError):
    pass


FILE_RULES: dict[DocumentFileType, tuple[set[str], set[str], str]] = {
    DocumentFileType.PDF: ({".pdf"}, {"application/pdf"}, "application/pdf"),
    DocumentFileType.DOCX: (
        {".docx"},
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    DocumentFileType.TIFF: ({".tif", ".tiff"}, {"image/tiff"}, "image/tiff"),
    DocumentFileType.PNG: ({".png"}, {"image/png"}, "image/png"),
    DocumentFileType.JPEG: (
        {".jpg", ".jpeg"},
        {"image/jpeg", "image/jpg", "image/pjpeg"},
        "image/jpeg",
    ),
    DocumentFileType.TEXT: ({".txt"}, {"text/plain"}, "text/plain"),
}


def sanitize_file_name(file_name: str | None) -> str:
    candidate = (file_name or "upload").replace("\\", "/")
    candidate = PurePosixPath(candidate).name
    candidate = re.sub(r"[\x00-\x1f\x7f]", "", candidate).replace('"', "'").strip().strip(".")
    return (candidate or "upload")[:255]


def _is_docx(content: bytes) -> bool:
    if not content.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            return "[Content_Types].xml" in names and "word/document.xml" in names
    except zipfile.BadZipFile:
        return False


def _detect_file_type(content: bytes) -> DocumentFileType:
    if content.startswith(b"%PDF-"):
        return DocumentFileType.PDF
    if _is_docx(content):
        return DocumentFileType.DOCX
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return DocumentFileType.TIFF
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return DocumentFileType.PNG
    if content.startswith(b"\xff\xd8\xff"):
        return DocumentFileType.JPEG
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadValidationError("The file content is not a supported document type.") from exc
    if b"\x00" in content:
        raise UploadValidationError("The file content is not valid plain text.")
    return DocumentFileType.TEXT


async def verify_upload(upload: UploadFile, max_size: int) -> VerifiedUpload:
    file_name = sanitize_file_name(upload.filename)
    chunks: list[bytes] = []
    total = 0
    try:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_size:
                raise UploadValidationError(
                    f"File exceeds the configured {max_size}-byte size limit."
                )
            chunks.append(chunk)
    finally:
        await upload.close()

    content = b"".join(chunks)
    if not content:
        raise UploadValidationError("Empty files cannot be uploaded.")

    file_type = _detect_file_type(content)
    allowed_extensions, allowed_mimes, canonical_mime = FILE_RULES[file_type]
    extension = PurePosixPath(file_name).suffix.lower()
    if extension not in allowed_extensions:
        raise UploadValidationError(
            f"File extension does not match detected {file_type.value} content."
        )
    submitted_mime = (upload.content_type or "").lower().split(";", 1)[0].strip()
    if submitted_mime not in allowed_mimes:
        raise UploadValidationError(f"MIME type does not match detected {file_type.value} content.")
    return VerifiedUpload(
        file_name=file_name,
        file_type=file_type,
        content_type=canonical_mime,
        extension=extension,
        content=content,
    )


async def upload_documents(
    db: Session,
    uploads: list[UploadFile],
    domain_id: uuid.UUID | None,
    actor: User,
    storage: ObjectStorage,
    max_size: int,
) -> list[DocumentUploadResult]:
    if domain_id is not None and db.get(Domain, domain_id) is None:
        raise NotFoundError("Domain")

    results: list[DocumentUploadResult] = []
    for upload in uploads:
        display_name = sanitize_file_name(upload.filename)
        storage_key: str | None = None
        try:
            verified = await verify_upload(upload, max_size)
            document_id = uuid.uuid4()
            storage_key = f"documents/{document_id}/original{verified.extension}"
            await storage.put(storage_key, verified.content, verified.content_type)
            document = Document(
                id=document_id,
                domain_id=domain_id,
                original_file_name=verified.file_name,
                file_type=verified.file_type,
                content_type=verified.content_type,
                object_storage_key=storage_key,
                file_size=len(verified.content),
                checksum_sha256=hashlib.sha256(verified.content).hexdigest(),
                upload_status=DocumentUploadStatus.STORED,
                processing_status=DocumentProcessingStatus.PENDING,
                uploaded_by_id=actor.id,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            results.append(
                DocumentUploadResult(
                    file_name=verified.file_name,
                    success=True,
                    document=DocumentRead.model_validate(document),
                )
            )
        except UploadValidationError as exc:
            db.rollback()
            results.append(
                DocumentUploadResult(
                    file_name=display_name,
                    success=False,
                    error=UploadErrorRead(code="invalid_upload", message=str(exc)),
                )
            )
        except IntegrityError:
            db.rollback()
            if storage_key is not None:
                await storage.delete(storage_key)
            results.append(
                DocumentUploadResult(
                    file_name=display_name,
                    success=False,
                    error=UploadErrorRead(
                        code="storage_conflict",
                        message="Document metadata could not be saved.",
                    ),
                )
            )
        except (OSError, ValueError):
            db.rollback()
            results.append(
                DocumentUploadResult(
                    file_name=display_name,
                    success=False,
                    error=UploadErrorRead(
                        code="storage_error",
                        message="The original file could not be stored.",
                    ),
                )
            )
    return results


def list_documents(db: Session, domain_id: uuid.UUID | None = None) -> list[Document]:
    statement = select(Document).order_by(Document.uploaded_at.desc(), Document.id)
    if domain_id is not None:
        statement = statement.where(Document.domain_id == domain_id)
    return list(db.scalars(statement))


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document")
    return document
