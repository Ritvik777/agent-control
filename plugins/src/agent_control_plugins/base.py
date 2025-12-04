"""Base classes for agent-control plugins."""

from dataclasses import dataclass
from typing import Any

from agent_control_models.controls import Evaluator, EvaluatorResult


@dataclass
class PluginMetadata:
    """Metadata about a plugin.

    Attributes:
        name: Unique plugin name (e.g., "galileo-luna2")
        version: Plugin version string
        description: Human-readable description
        requires_api_key: Whether the plugin requires an API key
        timeout_ms: Default timeout in milliseconds for plugin operations
        config_schema: JSON Schema for plugin configuration
    """

    name: str
    version: str
    description: str
    requires_api_key: bool = False
    timeout_ms: int = 10000
    config_schema: dict[str, Any] | None = None


class PluginEvaluator(Evaluator):
    """Base class for all plugin-based evaluators.

    Plugins extend agent-control with external evaluation systems.
    They follow the same pattern as other evaluators:
        1. Create with config: `plugin = MyPlugin(config)`
        2. Evaluate data: `result = plugin.evaluate(data)`

    Example:
        ```python
        from agent_control_plugins.base import PluginEvaluator, PluginMetadata

        class MyPlugin(PluginEvaluator):
            metadata = PluginMetadata(
                name="my-plugin",
                version="1.0.0",
                description="My custom evaluator",
                timeout_ms=5000,
            )

            def __init__(self, config: dict):
                self.config = config

            def evaluate(self, data: Any) -> EvaluatorResult:
                # Custom evaluation logic using self.config
                return EvaluatorResult(
                    matched=True,
                    confidence=0.9,
                    message="Evaluation complete"
                )
        ```
    """

    metadata: PluginMetadata
    config: dict[str, Any]

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize plugin with configuration.

        Args:
            config: Plugin-specific configuration from PluginConfig.plugin_config
        """
        self.config = config

    def get_timeout_seconds(self) -> float:
        """Get timeout in seconds from config or metadata default.

        Returns:
            Timeout in seconds (converted from milliseconds)
        """
        timeout_ms: int = self.config.get("timeout_ms", self.metadata.timeout_ms)
        return float(timeout_ms) / 1000.0

