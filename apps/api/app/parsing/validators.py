from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.templates.models import ColumnType


def validate_value(
    value: Any, column_type: ColumnType, enum_values: list[str] | None = None
) -> tuple[str | None, str | None]:
    if value is None:
        return None, "The provider returned no value."
    if column_type == ColumnType.STRING:
        if isinstance(value, str) and value.strip():
            return value.strip(), None
        return None, "Expected a non-empty string."
    if column_type == ColumnType.INTEGER:
        if isinstance(value, bool):
            return None, "Expected an integer."
        try:
            parsed = Decimal(str(value).strip())
            if parsed != parsed.to_integral_value():
                raise InvalidOperation
            return str(int(parsed)), None
        except (InvalidOperation, ValueError):
            return None, "Expected an integer."
    if column_type in {ColumnType.DECIMAL, ColumnType.CURRENCY}:
        candidate = str(value).strip().replace(",", "")
        if column_type == ColumnType.CURRENCY:
            candidate = candidate.lstrip("$€£¥").strip()
        try:
            return format(Decimal(candidate), "f"), None
        except InvalidOperation:
            return None, f"Expected a {column_type.value} value."
    if column_type == ColumnType.DATE:
        try:
            return date.fromisoformat(str(value).strip()).isoformat(), None
        except ValueError:
            return None, "Expected an ISO date (YYYY-MM-DD)."
    if column_type == ColumnType.BOOLEAN:
        if isinstance(value, bool):
            return "true" if value else "false", None
        normalized = str(value).strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return "true", None
        if normalized in {"false", "no", "0"}:
            return "false", None
        return None, "Expected a boolean value."
    if column_type == ColumnType.ENUM:
        normalized = str(value).strip().casefold()
        matches = [item for item in enum_values or [] if item.strip().casefold() == normalized]
        if len(matches) == 1:
            return matches[0], None
        return None, "Value is not one of the allowed enum values."
    return None, "Unsupported column type."
