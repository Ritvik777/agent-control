"""Base classes for agent_control plugins.

Re-exports from agent_control_plugins for convenience.
"""

# Re-export from the plugins package
from agent_control_plugins.base import PluginEvaluator, PluginMetadata

__all__ = ["PluginEvaluator", "PluginMetadata"]

