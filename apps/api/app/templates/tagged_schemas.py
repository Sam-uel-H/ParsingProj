from __future__ import annotations

import math
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SelectionRectangle(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_page(self) -> SelectionRectangle:
        values = (self.x, self.y, self.width, self.height)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Selection coordinates must be finite.")
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Selection rectangle must fit inside the page.")
        return self


class TaggedExampleWrite(BaseModel):
    template_column_id: uuid.UUID
    document_id: uuid.UUID
    document_extraction_id: uuid.UUID
    page_number: int = Field(ge=1)
    selected_text: str = Field(min_length=1, max_length=10000)
    expected_value: str = Field(min_length=1, max_length=10000)
    rectangles: list[SelectionRectangle] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def nonblank_values(self) -> TaggedExampleWrite:
        if not self.selected_text.strip() or not self.expected_value.strip():
            raise ValueError("Selected text and expected value must not be blank.")
        return self


class TaggedExampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_column_id: uuid.UUID
    document_id: uuid.UUID
    document_extraction_id: uuid.UUID
    tagged_value: str
    expected_value: str
    page_number: int
    char_start: int
    char_end: int
    rectangles: list[SelectionRectangle]
    text_block_ids: list[str]
    created_by_id: uuid.UUID
    created_at: datetime
