"""Base classes for agent_control plugins.

Re-exports from agent_control_models for convenience.
"""

# Re-export from the models package (where they're defined)
from agent_control_models import PluginEvaluator, PluginMetadata

__all__ = ["PluginEvaluator", "PluginMetadata"]

