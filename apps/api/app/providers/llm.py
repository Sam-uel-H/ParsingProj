from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMColumn:
    name: str
    description: str
    value_type: str
    prompt: str
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptSuggestionRequest:
    column: LLMColumn
    tagged_value: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    document_text: str
    columns: tuple[LLMColumn, ...]
    correction_instruction: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True, slots=True)
class PromptSuggestion:
    text: str
    metadata: ProviderMetadata
    usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    column_name: str
    value: Any | None
    raw_output: str
    confidence: float | None = None
    supporting_text: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractionResponse:
    values: tuple[ExtractedValue, ...]
    metadata: ProviderMetadata
    usage: ProviderUsage


class LLMProvider(ABC):
    @abstractmethod
    async def suggest_prompt(self, request: PromptSuggestionRequest) -> PromptSuggestion:
        """Suggest editable prompt text for one column."""

    @abstractmethod
    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        """Extract one or many scalar column values from document text."""
