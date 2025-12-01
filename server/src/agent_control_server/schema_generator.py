"""
Schema generator for agents based on registered tools.

This module automatically generates comprehensive schemas for agents
based on their registered tools.
"""

from typing import Any


def generate_agent_schema(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Generate a comprehensive schema for an agent based on its registered tools.

    This function creates a JSON schema that describes:
    - Available tools
    - Tool inputs and outputs
    - Validation rules
    - Capability definitions

    Args:
        tools: List of tool definitions with arguments and output_schema

    Returns:
        Complete agent schema dictionary

    Example:
        tools = [
            {
                "tool_name": "search",
                "arguments": {"query": {"type": "string"}},
                "output_schema": {"results": {"type": "array"}}
            }
        ]
        schema = generate_agent_schema(tools)
    """
    if not tools:
        return {
            "version": "1.0",
            "schema_type": "agent",
            "tools": [],
            "capabilities": [],
            "total_tools": 0,
            "metadata": {
                "auto_generated": True,
                "generator_version": "1.0"
            }
        }

    # Extract tool definitions
    tool_definitions = []
    capabilities = []

    for tool in tools:
        tool_name = tool.get("tool_name", "")
        arguments = tool.get("arguments", {})
        output_schema = tool.get("output_schema", {})

        # Build tool definition
        tool_def = {
            "name": tool_name,
            "input_schema": arguments,
            "output_schema": output_schema,
            "required_inputs": _extract_required_fields(arguments),
            "output_type": _infer_output_type(output_schema)
        }
        tool_definitions.append(tool_def)

        # Extract capabilities from tool names
        capability = _infer_capability(tool_name)
        if capability and capability not in capabilities:
            capabilities.append(capability)

    return {
        "version": "1.0",
        "schema_type": "agent",
        "tools": tool_definitions,
        "capabilities": capabilities,
        "total_tools": len(tool_definitions),
        "metadata": {
            "auto_generated": True,
            "generator_version": "1.0"
        }
    }


def _extract_required_fields(schema: dict[str, Any]) -> list[str]:
    """Extract required field names from a JSON schema."""
    if not schema or not isinstance(schema, dict):
        return []

    # Check for explicit required array
    if "required" in schema:
        required = schema["required"]
        if isinstance(required, list):
            return required

    # Check properties for required fields
    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        required = []
        for field_name, field_def in properties.items():
            if isinstance(field_def, dict):
                # If optional is explicitly False or not specified, it's required
                if not field_def.get("optional", False):
                    required.append(field_name)
        return required

    return []


def _infer_output_type(schema: dict[str, Any]) -> str:
    """Infer the primary output type from schema."""
    if not schema or not isinstance(schema, dict):
        return "unknown"

    # Check top-level type
    if "type" in schema:
        type_value = schema["type"]
        return str(type_value) if type_value is not None else "unknown"

    # Check properties for dominant type
    properties = schema.get("properties", {})
    if isinstance(properties, dict) and properties:
        # Return first property type as representative
        first_prop = next(iter(properties.values()))
        if isinstance(first_prop, dict) and "type" in first_prop:
            type_value = first_prop["type"]
            return str(type_value) if type_value is not None else "unknown"

    return "object"


def _infer_capability(tool_name: str) -> str | None:
    """
    Infer agent capability from tool name.

    Extracts high-level capabilities like "search", "process", "send"
    from tool names following common naming patterns.
    """
    if not tool_name:
        return None

    # Common verb patterns for capabilities
    verbs = [
        "search", "find", "query", "lookup",
        "create", "add", "insert", "register",
        "update", "modify", "edit", "change",
        "delete", "remove", "cancel",
        "send", "notify", "alert", "email",
        "process", "handle", "execute", "run",
        "get", "fetch", "retrieve", "read",
        "list", "show", "display",
        "validate", "check", "verify"
    ]

    tool_lower = tool_name.lower()

    for verb in verbs:
        if tool_lower.startswith(verb) or f"_{verb}" in tool_lower:
            return verb

    # Extract first word as capability if it's a verb-like pattern
    parts = tool_lower.split('_')
    if parts:
        return parts[0]

    return None


def validate_agent_schema(schema: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate an agent schema for completeness and correctness.

    Args:
        schema: Generated agent schema

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required top-level fields
    required_fields = ["version", "schema_type", "tools"]
    for field in required_fields:
        if field not in schema:
            errors.append(f"Missing required field: {field}")

    # Validate schema type
    if schema.get("schema_type") != "agent":
        errors.append(f"Invalid schema_type: expected 'agent', got '{schema.get('schema_type')}'")

    # Validate tools structure
    tools = schema.get("tools", [])
    if not isinstance(tools, list):
        errors.append("Field 'tools' must be a list")
    else:
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                errors.append(f"Tool at index {i} must be a dictionary")
                continue

            # Check required tool fields
            if "name" not in tool:
                errors.append(f"Tool at index {i} missing 'name' field")
            if "input_schema" not in tool:
                errors.append(f"Tool at index {i} missing 'input_schema' field")

    return (len(errors) == 0, errors)

