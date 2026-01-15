"""Built-in plugins for agent-control.

These plugins are automatically registered when this module is imported.
"""

from .json import JSONControlEvaluatorPlugin
from .list import ListPlugin
from .regex import RegexPlugin

__all__ = ["JSONControlEvaluatorPlugin", "ListPlugin", "RegexPlugin"]
