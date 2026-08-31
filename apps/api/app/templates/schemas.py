from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.templates.models import ColumnType, TemplateVersionStatus


class TemplateColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    column_type: ColumnType
    enum_values: list[str] | None = None
    prompt_text: str | None = Field(default=None, max_length=10000)
    display_order: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Column name must not be blank.")
        return value

    @field_validator("description", "prompt_text")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_enum_values(self) -> TemplateColumnCreate:
        if self.column_type == ColumnType.ENUM:
            if not self.enum_values:
                raise ValueError("Enum columns require at least one allowed value.")
            normalized = [value.strip() for value in self.enum_values]
            if any(not value for value in normalized):
                raise ValueError("Enum values must not be blank.")
            if len(set(normalized)) != len(normalized):
                raise ValueError("Enum values must be unique.")
            self.enum_values = normalized
        elif self.enum_values is not None:
            raise ValueError("Enum values are only valid for Enum columns.")
        return self


class TemplateCreate(BaseModel):
    domain_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    columns: list[TemplateColumnCreate] = Field(
        default_factory=lambda: list[TemplateColumnCreate]()
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Template name must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_unique_column_names(self) -> TemplateCreate:
        names = [column.name for column in self.columns]
        if len(set(names)) != len(names):
            raise ValueError("Column names must be unique within a template version.")
        return self


class TemplateColumnDraft(TemplateColumnCreate):
    id: uuid.UUID | None = None


class TemplateColumnUpdate(TemplateColumnCreate):
    expected_lock_version: int = Field(ge=1)


class TemplateDraftUpdate(BaseModel):
    domain_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    expected_lock_version: int = Field(ge=1)
    columns: list[TemplateColumnDraft]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Template name must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_columns(self) -> TemplateDraftUpdate:
        names = [column.name for column in self.columns]
        if len(set(names)) != len(names):
            raise ValueError("Column names must be unique within a template version.")
        orders = [column.display_order for column in self.columns]
        if len(set(orders)) != len(orders):
            raise ValueError("Column display-order values must be unique.")
        ids = [column.id for column in self.columns if column.id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("A template column may appear only once in an update.")
        return self


class PublishTemplateRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class TemplateColumnRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    column_type: ColumnType
    enum_values: list[str] | None
    prompt_text: str | None
    display_order: int
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TemplateVersionRead(BaseModel):
    id: uuid.UUID
    version_number: int
    status: TemplateVersionStatus
    name: str
    description: str | None
    lock_version: int
    published_at: datetime | None
    published_by_id: uuid.UUID | None
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    columns: list[TemplateColumnRead]


class TemplateRead(BaseModel):
    id: uuid.UUID
    domain_id: uuid.UUID
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    current_version: TemplateVersionRead


class TemplateSummary(BaseModel):
    id: uuid.UUID
    domain_id: uuid.UUID
    name: str
    description: str | None
    version_number: int
    status: TemplateVersionStatus
    lock_version: int
    published_at: datetime | None
    updated_at: datetime
