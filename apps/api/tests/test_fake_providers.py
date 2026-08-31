from __future__ import annotations

import asyncio

import pytest

from app.providers.document_extraction import DocumentExtractionRequest
from app.providers.fakes import (
    FakeDocumentExtractionProvider,
    FakeLLMProvider,
    InMemoryObjectStorage,
)
from app.providers.llm import ExtractionRequest, LLMColumn, PromptSuggestionRequest
from app.providers.object_storage import FileSystemObjectStorage, ObjectNotFoundError


def test_fake_llm_is_deterministic() -> None:
    provider = FakeLLMProvider()
    column = LLMColumn(
        name="Notice Date",
        description="Date printed on the notice.",
        value_type="date",
        prompt="Extract the date.",
    )

    suggestion = asyncio.run(
        provider.suggest_prompt(PromptSuggestionRequest(column=column, tagged_value="2026-08-17"))
    )
    response = asyncio.run(
        provider.extract(
            ExtractionRequest(document_text="Notice Date: 2026-08-17", columns=(column,))
        )
    )

    assert suggestion.metadata.provider == "fake"
    assert suggestion.text.endswith("Return JSON.")
    assert response.values[0].value == "2026-08-17"
    assert response.values[0].confidence == 1.0


def test_fake_extractor_preserves_pages_order_and_offsets() -> None:
    provider = FakeDocumentExtractionProvider()

    result = asyncio.run(
        provider.extract(
            DocumentExtractionRequest(
                filename="sample.txt",
                content=b"first line\nsecond\fpage two",
                content_type="text/plain",
            )
        )
    )

    assert result.full_text == "first line\nsecond\fpage two"
    assert [page.page_number for page in result.pages] == [1, 2]
    assert result.pages[0].blocks[1].reading_order == 1
    assert result.pages[1].blocks[0].char_start == len("first line\nsecond\f")


def test_in_memory_storage_contract() -> None:
    async def exercise_contract() -> None:
        storage = InMemoryObjectStorage()

        stored = await storage.put("samples/one.txt", b"hello", "text/plain")

        assert stored.size == 5
        assert await storage.exists(stored.key)
        assert await storage.get(stored.key) == b"hello"

        await storage.delete(stored.key)
        assert not await storage.exists(stored.key)
        with pytest.raises(ObjectNotFoundError):
            await storage.get(stored.key)

    asyncio.run(exercise_contract())


def test_file_system_storage_stays_inside_its_root(tmp_path) -> None:
    async def exercise_contract() -> None:
        storage = FileSystemObjectStorage(tmp_path / "objects")
        await storage.put("documents/one.txt", b"hello", "text/plain")

        assert await storage.get("documents/one.txt") == b"hello"
        with pytest.raises(ValueError):
            await storage.put("../escape.txt", b"bad", "text/plain")
        assert not (tmp_path / "escape.txt").exists()

    asyncio.run(exercise_contract())
