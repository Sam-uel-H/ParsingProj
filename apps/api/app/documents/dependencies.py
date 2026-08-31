from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.providers.document_extraction import DocumentExtractionProvider
from app.providers.local_document_extraction import LocalDocumentExtractionProvider
from app.providers.object_storage import FileSystemObjectStorage, ObjectStorage


@lru_cache
def get_object_storage() -> ObjectStorage:
    return FileSystemObjectStorage(get_settings().object_storage_path)


@lru_cache
def get_document_extractor() -> DocumentExtractionProvider:
    return LocalDocumentExtractionProvider()
