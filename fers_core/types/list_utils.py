from typing import Any, List


def as_list(value: Any, field_name: str) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise TypeError(f"Expected '{field_name}' to be a list or null, got {type(value).__name__}")
