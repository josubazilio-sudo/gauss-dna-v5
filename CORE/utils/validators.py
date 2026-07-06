import logging
from typing import Any

log = logging.getLogger(__name__)

NUMERIC_TYPES = (int, float)


def is_positive_number(value: Any) -> bool:
    return isinstance(value, NUMERIC_TYPES) and value > 0


def is_percentage(value: Any) -> bool:
    return isinstance(value, NUMERIC_TYPES) and 0 <= value <= 100


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip()) > 0


def validate_type(value: Any, expected_type: type) -> bool:
    return isinstance(value, expected_type)
