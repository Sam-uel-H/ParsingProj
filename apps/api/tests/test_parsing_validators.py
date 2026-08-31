from decimal import Decimal

import pytest

from app.parsing.validators import validate_value
from app.templates.models import ColumnType


@pytest.mark.parametrize(
    ("value", "column_type", "expected"),
    [
        ("hello", ColumnType.STRING, "hello"),
        ("42", ColumnType.INTEGER, "42"),
        (Decimal("12.50"), ColumnType.DECIMAL, "12.50"),
        ("$1,234.50", ColumnType.CURRENCY, "1234.50"),
        ("2026-08-24", ColumnType.DATE, "2026-08-24"),
        ("yes", ColumnType.BOOLEAN, "true"),
        ("usd", ColumnType.ENUM, "USD"),
    ],
)
def test_typed_validators(value, column_type, expected) -> None:
    enum_values = ["USD", "EUR"] if column_type == ColumnType.ENUM else None
    assert validate_value(value, column_type, enum_values) == (expected, None)


def test_invalid_value_is_never_silently_accepted() -> None:
    canonical, error = validate_value("not-a-date", ColumnType.DATE)
    assert canonical is None
    assert error == "Expected an ISO date (YYYY-MM-DD)."
