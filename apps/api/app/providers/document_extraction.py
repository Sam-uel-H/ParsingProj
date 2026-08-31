from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class TextBlock:
    page_number: int
    text: str
    reading_order: int
    char_start: int
    char_end: int
    polygon: tuple[Point, ...] | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str
    blocks: tuple[TextBlock, ...]
    width: float | None = None
    height: float | None = None
    preview_content: bytes | None = None
    preview_content_type: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentExtractionRequest:
    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    full_text: str
    pages: tuple[ExtractedPage, ...]
    provider: str
    provider_version: str


class DocumentExtractionProvider(ABC):
    @abstractmethod
    async def extract(self, request: DocumentExtractionRequest) -> ExtractedDocument:
        """Return provider-neutral page and layout-aware text data."""
