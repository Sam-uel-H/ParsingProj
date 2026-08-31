from __future__ import annotations

import json
import re

from app.providers.document_extraction import (
    DocumentExtractionProvider,
    DocumentExtractionRequest,
    ExtractedDocument,
    ExtractedPage,
    TextBlock,
)
from app.providers.llm import (
    ExtractedValue,
    ExtractionRequest,
    ExtractionResponse,
    LLMProvider,
    PromptSuggestion,
    PromptSuggestionRequest,
    ProviderMetadata,
    ProviderUsage,
)
from app.providers.object_storage import ObjectNotFoundError, ObjectStorage, StoredObject


class FakeLLMProvider(LLMProvider):
    """Deterministic fake that reads `Column Name: value` lines from input text."""

    metadata = ProviderMetadata(provider="fake", model="deterministic-v1")
    usage = ProviderUsage(input_tokens=0, output_tokens=0, latency_ms=0)

    async def suggest_prompt(self, request: PromptSuggestionRequest) -> PromptSuggestion:
        example = f" For example: {request.tagged_value}." if request.tagged_value else ""
        text = (
            f"Extract {request.column.name} as {request.column.value_type}. "
            f"{request.column.description.strip()}{example} Return JSON."
        )
        return PromptSuggestion(text=text, metadata=self.metadata, usage=self.usage)

    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        values: list[ExtractedValue] = []
        for column in request.columns:
            pattern = re.compile(rf"(?im)^\s*{re.escape(column.name)}\s*:\s*(?P<value>.+?)\s*$")
            match = pattern.search(request.document_text)
            value = match.group("value").strip() if match else None
            raw_output = json.dumps({"value": value}, sort_keys=True)
            values.append(
                ExtractedValue(
                    column_name=column.name,
                    value=value,
                    raw_output=raw_output,
                    confidence=1.0 if match else 0.0,
                    supporting_text=match.group(0).strip() if match else None,
                )
            )

        return ExtractionResponse(
            values=tuple(values),
            metadata=self.metadata,
            usage=self.usage,
        )


class FakeDocumentExtractionProvider(DocumentExtractionProvider):
    """Deterministically decodes UTF-8 text and treats form feeds as page breaks."""

    async def extract(self, request: DocumentExtractionRequest) -> ExtractedDocument:
        text = request.content.decode("utf-8")
        page_texts = text.split("\f")
        pages: list[ExtractedPage] = []
        document_offset = 0

        for page_number, page_text in enumerate(page_texts, start=1):
            blocks: list[TextBlock] = []
            page_offset = 0
            for reading_order, line in enumerate(page_text.splitlines(keepends=True)):
                block_text = line.rstrip("\r\n")
                start = document_offset + page_offset
                end = start + len(block_text)
                blocks.append(
                    TextBlock(
                        page_number=page_number,
                        text=block_text,
                        reading_order=reading_order,
                        char_start=start,
                        char_end=end,
                        confidence=1.0,
                    )
                )
                page_offset += len(line)

            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=page_text,
                    blocks=tuple(blocks),
                )
            )
            document_offset += len(page_text)
            if page_number < len(page_texts):
                document_offset += 1

        return ExtractedDocument(
            full_text=text,
            pages=tuple(pages),
            provider="fake",
            provider_version="deterministic-v1",
        )


class InMemoryObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        self._objects[key] = (bytes(content), content_type)
        return StoredObject(key=key, content_type=content_type, size=len(content))

    async def get(self, key: str) -> bytes:
        try:
            content, _ = self._objects[key]
        except KeyError as exc:
            raise ObjectNotFoundError(key) from exc
        return bytes(content)

    async def exists(self, key: str) -> bool:
        return key in self._objects

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)
