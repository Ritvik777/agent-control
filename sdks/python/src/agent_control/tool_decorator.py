"""
Tool decorator for automatic schema inference from Python functions.

This module provides OpenAI-style decorators that automatically infer
tool schemas from function signatures, type hints, and docstrings.
"""

import inspect
from collections.abc import Callable
from typing import Any, Literal, get_args, get_origin, get_type_hints

from docstring_parser import parse as parse_docstring  # type: ignore[import-not-found]


def python_type_to_json_type(py_type: Any) -> dict[str, Any]:
    """
    Convert Python type hint to JSON schema type.

    Args:
        py_type: Python type hint

    Returns:
        JSON schema type definition
    """
    # Handle None/Optional
    origin = get_origin(py_type)

    # Handle Union types (including Optional)
    if origin is type(None):
        return {"type": "null"}

    # Handle Optional (Union with None)
    if origin in (type(None) | type, type | None):  # Python 3.10+ union syntax
        args = get_args(py_type)
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1:
            return python_type_to_json_type(non_none[0])

    # Handle Literal types (for enums)
    if origin is Literal:
        values = get_args(py_type)
        base_type = type(values[0]).__name__ if values else "string"
        return {
            "type": base_type.replace("bool", "boolean").replace("int", "integer"),
            "enum": list(values)
        }

    # Handle list/List
    if origin is list:
        args = get_args(py_type)
        items_type = args[0] if args else Any
        return {
            "type": "array",
            "items": python_type_to_json_type(items_type)
        }

    # Handle dict/Dict
    if origin is dict:
        return {"type": "object"}

    # Basic type mapping
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null"
    }

    # Get the actual type if it's a generic alias
    actual_type = py_type
    if hasattr(py_type, "__origin__"):
        actual_type = py_type.__origin__

    json_type = type_map.get(actual_type, "string")
    return {"type": json_type}


def extract_docstring_info(func: Callable) -> dict[str, Any]:
    """
    Extract parameter descriptions and function description from docstring.

    Supports Google, NumPy, and Sphinx docstring formats.

    Args:
        func: Function to extract docstring from

    Returns:
        Dictionary with 'description' and 'params' (param_name -> description)
    """
    if not func.__doc__:
        return {"description": "", "params": {}}

    try:
        docstring = parse_docstring(func.__doc__)

        return {
            "description": docstring.short_description or docstring.long_description or "",
            "params": {
                param.arg_name: param.description or ""
                for param in docstring.params
            }
        }
    except Exception:
        # Fallback: simple extraction
        lines = func.__doc__.strip().split("\n")
        description = lines[0] if lines else ""

        # Try to extract simple Args: section
        params = {}
        in_args = False
        for line in lines[1:]:
            if "Args:" in line or "Parameters:" in line:
                in_args = True
                continue
            if in_args and line.strip():
                if ":" in line:
                    parts = line.strip().split(":", 1)
                    param_name = parts[0].strip()
                    param_desc = parts[1].strip() if len(parts) > 1 else ""
                    params[param_name] = param_desc
                elif "Returns:" in line or "Raises:" in line:
                    break

        return {"description": description, "params": params}


def infer_tool_schema(func: Callable) -> dict[str, Any]:
    """
    Infer complete tool schema from a Python function.

    Extracts:
    - Function name
    - Description from docstring
    - Parameter schemas from type hints
    - Required vs optional parameters
    - Return type schema

    Args:
        func: Python function to analyze

    Returns:
        Complete tool schema dictionary

    Example:
        >>> def search(query: str, limit: int = 10) -> dict:
        ...     '''Search for items.
        ...
        ...     Args:
        ...         query: Search query string
        ...         limit: Maximum results to return
        ...     '''
        ...     pass
        >>> schema = infer_tool_schema(search)
        >>> print(schema['tool_name'])
        'search'
    """
    # Get function signature and type hints
    sig = inspect.signature(func)
    hints = get_type_hints(func)

    # Extract docstring information
    doc_info = extract_docstring_info(func)

    # Build parameters schema
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        # Skip self/cls for methods
        if param_name in ("self", "cls"):
            continue

        # Determine if required (no default value)
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

        # Get type hint
        param_type = hints.get(param_name, Any)
        type_schema = python_type_to_json_type(param_type)

        # Add description from docstring
        if param_name in doc_info["params"]:
            type_schema["description"] = doc_info["params"][param_name]

        properties[param_name] = type_schema

    # Infer return type schema
    return_type = hints.get("return", dict)
    output_schema = python_type_to_json_type(return_type)

    return {
        "tool_name": func.__name__,
        "arguments": {
            "type": "object",
            "properties": properties,
            "required": required
        },
        "output_schema": output_schema,
        "description": doc_info["description"]
    }


def tool(
    name: str | None = None,
    description: str | None = None
) -> Callable:
    """
    Decorator to mark a function as an agent tool with automatic schema inference.

    This decorator inspects the function's signature, type hints, and docstring
    to automatically generate a tool schema compatible with Agent Control.

    Args:
        name: Optional custom name for the tool (defaults to function name)
        description: Optional custom description (defaults to docstring)

    Returns:
        Decorated function with attached schema

    Example:
        >>> from agent_control.tool_decorator import tool
        >>> from typing import Literal
        >>>
        >>> @tool()
        >>> def get_weather(
        ...     location: str,
        ...     unit: Literal["celsius", "fahrenheit"] = "fahrenheit"
        ... ) -> dict:
        ...     '''Get current weather for a location.
        ...
        ...     Args:
        ...         location: City and state, e.g. "San Francisco, CA"
        ...         unit: Temperature unit to use
        ...     '''
        ...     # Implementation
        ...     return {"temp": 72, "unit": unit}
        >>>
        >>> # Schema is automatically attached
        >>> print(get_weather._tool_schema)
    """
    def decorator(func: Callable) -> Callable:
        # Infer schema from function
        schema = infer_tool_schema(func)

        # Override with custom values if provided
        if name:
            schema["tool_name"] = name
        if description:
            schema["description"] = description

        # Attach schema to function
        func._tool_schema = schema  # type: ignore

        return func

    return decorator


def extract_tools_from_functions(functions: list[Callable]) -> list[dict[str, Any]]:
    """
    Extract tool schemas from a list of functions.

    Functions can be decorated with @tool() or plain functions.
    For plain functions, schema is inferred automatically.

    Args:
        functions: List of Python functions

    Returns:
        List of tool schema dictionaries

    Example:
        >>> @tool()
        >>> def search(query: str) -> list:
        ...     pass
        >>>
        >>> def fetch(url: str) -> str:
        ...     pass
        >>>
        >>> tools = extract_tools_from_functions([search, fetch])
        >>> print(len(tools))
        2
    """
    schemas = []

    for func in functions:
        # Check if already decorated with schema
        if hasattr(func, "_tool_schema"):
            schemas.append(func._tool_schema)
        else:
            # Infer schema automatically
            schemas.append(infer_tool_schema(func))

    return schemas


# Convenience function for common use case
def tools_from_module(module: Any) -> list[dict[str, Any]]:
    """
    Extract all @tool decorated functions from a module.

    Args:
        module: Python module to scan

    Returns:
        List of tool schemas from decorated functions

    Example:
        >>> # In tools.py:
        >>> @tool()
        >>> def search(query: str) -> list:
        ...     pass
        >>>
        >>> @tool()
        >>> def fetch(url: str) -> str:
        ...     pass
        >>>
        >>> # In main.py:
        >>> import tools
        >>> tool_schemas = tools_from_module(tools)
    """
    schemas = []

    for name in dir(module):
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, "_tool_schema"):
            schemas.append(obj._tool_schema)

    return schemas

