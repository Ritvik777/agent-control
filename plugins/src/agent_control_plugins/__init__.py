"""Agent Control Plugins.

This package contains plugin implementations for agent-control.
Plugins can be installed individually as optional dependencies.

Available plugins:
    - luna2: Galileo Luna-2 runtime protection (pip install agent-control-plugins[luna2])
"""

from .base import PluginEvaluator, PluginMetadata

__version__ = "0.1.0"

__all__ = [
    "PluginEvaluator",
    "PluginMetadata",
]

