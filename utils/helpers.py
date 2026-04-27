"""Helper utility functions"""

from typing import Any, Optional, Dict


def safe_dict_get(
    data: Dict, key: str, default: Any = None, key_type: type = str
) -> Any:
    """
    Safely get value from dictionary with type casting

    Args:
        data: Dictionary to fetch from
        key: Key to access
        default: Default value if key not found
        key_type: Type to cast value to

    Returns:
        Value or default
    """
    try:
        value = data.get(key, default)
        return key_type(value) if value is not None else default
    except (ValueError, TypeError):
        return default
