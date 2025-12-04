"""Plugin system for agent_control.

This module provides a plugin architecture for extending agent_control
with external evaluation systems like Galileo Luna-2, Guardrails AI, etc.

Plugin Discovery:
    Plugins are discovered lazily on first use of `get_plugin()` or `list_plugins()`.
    To disable auto-discovery, set: AGENT_CONTROL_DISABLE_PLUGIN_DISCOVERY=1

    For explicit control, call `discover_plugins()` manually.

Luna-2 Plugin:
    When installed with luna2 extras, the Luna-2 types are available:
    ```python
    from agent_control.plugins import Luna2Plugin, Luna2Config  # if luna2 installed
    ```
"""

from .base import PluginEvaluator, PluginMetadata
from .registry import discover_plugins, get_plugin, list_plugins, register_plugin

__all__ = [
    "PluginEvaluator",
    "PluginMetadata",
    "discover_plugins",
    "get_plugin",
    "list_plugins",
    "register_plugin",
]

# Optionally export Luna-2 types when available
try:
    from agent_control_plugins.luna2 import (  # noqa: F401
        LUNA2_AVAILABLE,
        Luna2Config,
        Luna2Metric,
        Luna2Operator,
        Luna2Plugin,
    )

    __all__.extend([
        "Luna2Plugin",
        "Luna2Config",
        "Luna2Metric",
        "Luna2Operator",
        "LUNA2_AVAILABLE",
    ])
except ImportError:
    pass

