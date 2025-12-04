"""Tests for plugin base classes.

New architecture: Plugins take config at __init__, evaluate() only takes data.
"""

import pytest
from typing import Any

from agent_control_models import Evaluator
from agent_control_models.controls import EvaluatorResult
from agent_control_plugins.base import PluginEvaluator, PluginMetadata


class MockPlugin(PluginEvaluator):
    """A mock plugin for testing."""

    metadata = PluginMetadata(
        name="mock-plugin",
        version="1.0.0",
        description="A mock plugin for testing",
        requires_api_key=False,
        timeout_ms=5000,
        config_schema={"type": "object"},
    )

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.should_match = config.get("should_match", False)

    def evaluate(self, data: Any) -> EvaluatorResult:
        """Simple mock evaluation."""
        return EvaluatorResult(
            matched=self.should_match,
            confidence=1.0,
            message="Mock evaluation",
            metadata={"data": str(data)},
        )


class TestPluginMetadata:
    """Tests for PluginMetadata dataclass."""

    def test_metadata_with_defaults(self):
        """Test metadata with default values."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
        )

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.requires_api_key is False
        assert metadata.timeout_ms == 10000
        assert metadata.config_schema is None

    def test_metadata_with_all_fields(self):
        """Test metadata with all fields specified."""
        metadata = PluginMetadata(
            name="full-plugin",
            version="2.0.0",
            description="Full plugin",
            requires_api_key=True,
            timeout_ms=15000,
            config_schema={"type": "object", "properties": {}},
        )

        assert metadata.name == "full-plugin"
        assert metadata.version == "2.0.0"
        assert metadata.requires_api_key is True
        assert metadata.timeout_ms == 15000
        assert metadata.config_schema is not None


class TestPluginEvaluator:
    """Tests for PluginEvaluator base class."""

    def test_plugin_extends_evaluator(self):
        """Test that PluginEvaluator extends Evaluator."""
        assert issubclass(PluginEvaluator, Evaluator)

    def test_mock_plugin_metadata(self):
        """Test that mock plugin has correct metadata."""
        assert MockPlugin.metadata.name == "mock-plugin"
        assert MockPlugin.metadata.version == "1.0.0"
        assert MockPlugin.metadata.timeout_ms == 5000

    def test_mock_plugin_evaluate(self):
        """Test mock plugin evaluation."""
        plugin = MockPlugin({"should_match": True})

        result = plugin.evaluate("test data")

        assert result.matched is True
        assert result.confidence == 1.0
        assert result.metadata["data"] == "test data"

    def test_mock_plugin_evaluate_no_match(self):
        """Test mock plugin evaluation without match."""
        plugin = MockPlugin({"should_match": False})

        result = plugin.evaluate("test data")

        assert result.matched is False

    def test_plugin_config_stored(self):
        """Test that plugin stores config."""
        config = {"should_match": True, "extra": "value"}
        plugin = MockPlugin(config)

        assert plugin.config == config
        assert plugin.should_match is True

    def test_get_timeout_seconds_from_config(self):
        """Test timeout conversion from config."""
        plugin = MockPlugin({"timeout_ms": 3000})

        assert plugin.get_timeout_seconds() == 3.0

    def test_get_timeout_seconds_different_values(self):
        """Test timeout with different values."""
        plugin1 = MockPlugin({"timeout_ms": 7500})
        plugin2 = MockPlugin({"timeout_ms": 1000})

        assert plugin1.get_timeout_seconds() == 7.5
        assert plugin2.get_timeout_seconds() == 1.0

    def test_get_timeout_seconds_from_default(self):
        """Test timeout uses metadata default when not in config."""
        plugin = MockPlugin({})  # No timeout_ms in config

        # MockPlugin has timeout_ms=5000 in metadata
        assert plugin.get_timeout_seconds() == 5.0

    def test_cannot_instantiate_abstract_class(self):
        """Test that PluginEvaluator cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            PluginEvaluator({})  # type: ignore
