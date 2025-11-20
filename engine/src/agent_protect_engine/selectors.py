"""Data selection logic for rule evaluation."""
from typing import Any

from agent_protect_models import LlmCall, ToolCall


def select_data(payload: ToolCall | LlmCall, path: str) -> Any:
    """
    Select data from the payload using a dot-notation path.

    Args:
        payload: The protection payload (ToolCall or LlmCall)
        path: Dot-notation path (e.g., 'input', 'arguments.query', 'context.user_id')

    Returns:
        The selected value, or None if the path doesn't exist.
    """
    if not path or path == "*":
        return payload

    parts = path.split(".")
    current: Any = payload

    for part in parts:
        if current is None:
            return None

        # 1. Try dictionary access
        if isinstance(current, dict):
            try:
                current = current[part]
                continue
            except KeyError:
                return None

        # 2. Try attribute access (Pydantic models or objects)
        if hasattr(current, part):
            current = getattr(current, part)
            continue

        # 3. If neither worked, path is invalid for this object
        return None

    return current
