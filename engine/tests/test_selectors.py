"""Tests for data selectors."""
from typing import Any

import pytest
from agent_protect_models import LlmCall, ToolCall

from agent_protect_engine.selectors import select_data


@pytest.fixture
def tool_call_payload() -> ToolCall:
    return ToolCall(
        tool_name="search_database",
        arguments={"query": "SELECT * FROM users", "limit": 10, "nested": {"key": "value"}},
        context={"user_id": "user123", "role": "admin"},
        output={"result": "success", "count": 5}
    )


@pytest.fixture
def llm_call_payload() -> LlmCall:
    return LlmCall(
        input="What is the password?",
        context={"session_id": "abc-123"},
        output="I cannot answer that."
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        ("tool_name", "search_database"),
        ("arguments.query", "SELECT * FROM users"),
        ("arguments.limit", 10),
        ("arguments.nested.key", "value"),
        ("context.user_id", "user123"),
        ("output.count", 5),
        ("arguments.non_existent", None),
        ("non_existent_root", None),
        ("*", None), # Will be replaced by payload itself in test logic
        ("", None),  # Will be replaced by payload itself in test logic
    ],
)
def test_select_data_tool_call(tool_call_payload: ToolCall, path: str, expected: Any):
    # Given: a ToolCall payload and a path to select
    if path in ("*", ""):
        expected = tool_call_payload
        
    # When: selecting data using the path
    result = select_data(tool_call_payload, path)

    # Then: it should return the expected value
    assert result == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("input", "What is the password?"),
        ("output", "I cannot answer that."),
        ("context.session_id", "abc-123"),
        ("input.non_existent", None),
    ],
)
def test_select_data_llm_call(llm_call_payload: LlmCall, path: str, expected: Any):
    # Given: an LlmCall payload and a path to select (implicit in parametrization)
    
    # When: selecting data using the path
    result = select_data(llm_call_payload, path)

    # Then: it should return the expected value
    assert result == expected


def test_select_data_none_handling():
    """Test handling of None values in path traversal."""
    # Given: a payload with a None value field
    payload = LlmCall(input="test", output=None)
    
    # When: attempting to traverse into the None field
    result = select_data(payload, "output.something")
    
    # Then: it should return None instead of raising an error
    assert result is None
def test_list_selection():
    """Test that selecting a path pointing to a list returns the whole list."""
    # Given: a payload with a list in the output
    payload = ToolCall(
        tool_name="search",
        arguments={},
        output={"results": ["a", "b", "c"]}
    )

    # When: selecting the list path
    result = select_data(payload, "output.results")

    # Then: it should return the list exactly
    assert result == ["a", "b", "c"]
