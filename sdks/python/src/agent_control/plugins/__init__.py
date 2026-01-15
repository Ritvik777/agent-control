"""Plugin system for agent_control.

This module provides a plugin architecture for extending agent_control
with external evaluation systems like Galileo Luna-2, Guardrails AI, etc.

Plugin Discovery:
    Call `discover_plugins()` at startup to load plugins. This loads:
    - Built-in plugins (regex, list) from agent_control_plugins
    - Third-party plugins via the 'agent_control.plugins' entry point group

    Then use `list_plugins()` to get available plugins.

Luna-2 Plugin:
    When installed with luna2 extras, the Luna-2 types are available:
    ```python
    from agent_control.plugins import Luna2Plugin, Luna2Config  # if luna2 installed
    ```
"""

from agent_control_engine import (
    discover_plugins,
    ensure_plugins_discovered,
    list_plugins,
)
from agent_control_models import register_plugin

from .base import PluginEvaluator, PluginMetadata

__all__ = [
    "PluginEvaluator",
    "PluginMetadata",
    "discover_plugins",
    "ensure_plugins_discovered",
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

