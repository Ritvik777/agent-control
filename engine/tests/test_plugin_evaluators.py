"""Tests for plugin evaluator integration in the engine.

These tests verify that the engine can correctly use plugin-based evaluators.
With the new architecture, plugins extend Evaluator directly - no wrapper needed.
"""

import pytest
from unittest.mock import patch

from agent_control_models import Evaluator, EvaluatorResult
from agent_control_models.controls import PluginConfig, PluginControlEvaluator
from agent_control_plugins import PluginEvaluator, PluginMetadata
from agent_control_engine.evaluators import get_evaluator, _create_plugin_evaluator


class MockTestPlugin(PluginEvaluator):
    """Mock plugin for engine testing."""

    metadata = PluginMetadata(
        name="test-engine-plugin",
        version="1.0.0",
        description="Test plugin for engine tests",
    )

    def __init__(self, config: dict):
        super().__init__(config)
        self.threshold = config.get("threshold", 0.5)

    def evaluate(self, data) -> EvaluatorResult:
        """Mock evaluation (synchronous)."""
        value = float(data) if isinstance(data, (int, float)) else 0.0
        matched = value > self.threshold

        return EvaluatorResult(
            matched=matched,
            confidence=1.0,
            message=f"Value {value} vs threshold {self.threshold}",
            metadata={"value": value, "threshold": self.threshold},
        )


class TestPluginIsEvaluator:
    """Tests verifying plugins ARE evaluators (not wrapped)."""

    def test_plugin_extends_evaluator(self):
        """Test that plugins extend the Evaluator base class."""
        assert issubclass(PluginEvaluator, Evaluator)
        assert issubclass(MockTestPlugin, Evaluator)

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_create_plugin_evaluator(self, mock_get_plugin):
        """Test _create_plugin_evaluator returns an Evaluator."""
        mock_get_plugin.return_value = MockTestPlugin

        config = PluginConfig(
            plugin_name="test-engine-plugin",
            plugin_config={"threshold": 0.7},
        )

        evaluator = _create_plugin_evaluator(config)

        # Plugin IS an Evaluator - no wrapper
        assert isinstance(evaluator, Evaluator)
        assert isinstance(evaluator, PluginEvaluator)
        assert isinstance(evaluator, MockTestPlugin)

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_plugin_not_found(self, mock_get_plugin):
        """Test error when plugin not found."""
        mock_get_plugin.return_value = None

        config = PluginConfig(
            plugin_name="nonexistent-plugin",
            plugin_config={},
        )

        with pytest.raises(ValueError, match="Plugin .* not found"):
            _create_plugin_evaluator(config)

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_plugin_init_error(self, mock_get_plugin):
        """Test error during plugin initialization."""

        class BadPlugin(PluginEvaluator):
            metadata = PluginMetadata(name="bad", version="1.0", description="Bad")

            def __init__(self, config):
                raise RuntimeError("Plugin init failed")

            def evaluate(self, data):
                pass

        mock_get_plugin.return_value = BadPlugin

        config = PluginConfig(plugin_name="bad-plugin", plugin_config={})

        with pytest.raises(ValueError, match="Failed to initialize plugin"):
            _create_plugin_evaluator(config)


class TestPluginEvaluation:
    """Tests for plugin evaluation."""

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_evaluate_matched(self, mock_get_plugin):
        """Test evaluation when rule matches."""
        mock_get_plugin.return_value = MockTestPlugin

        config = PluginConfig(
            plugin_name="test-engine-plugin",
            plugin_config={"threshold": 0.5},
        )

        evaluator = _create_plugin_evaluator(config)
        result = evaluator.evaluate(data=0.8)

        assert isinstance(result, EvaluatorResult)
        assert result.matched is True
        assert result.confidence == 1.0
        assert result.metadata["value"] == 0.8
        assert result.metadata["threshold"] == 0.5

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_evaluate_not_matched(self, mock_get_plugin):
        """Test evaluation when rule doesn't match."""
        mock_get_plugin.return_value = MockTestPlugin

        config = PluginConfig(
            plugin_name="test-engine-plugin",
            plugin_config={"threshold": 0.9},
        )

        evaluator = _create_plugin_evaluator(config)
        result = evaluator.evaluate(data=0.3)

        assert result.matched is False


class TestGetEvaluatorWithPlugin:
    """Tests for get_evaluator factory with plugin type."""

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_get_evaluator_returns_plugin_directly(self, mock_get_plugin):
        """Test get_evaluator returns plugin as Evaluator (no wrapper)."""
        mock_get_plugin.return_value = MockTestPlugin

        control_evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="test-engine-plugin",
                plugin_config={},
            ),
        )

        evaluator = get_evaluator(control_evaluator)

        # Should be the plugin itself, not a wrapper
        assert isinstance(evaluator, Evaluator)
        assert isinstance(evaluator, MockTestPlugin)

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_get_evaluator_plugin_with_config(self, mock_get_plugin):
        """Test get_evaluator passes plugin config correctly."""
        mock_get_plugin.return_value = MockTestPlugin

        plugin_config = {"threshold": 0.75}

        control_evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="test-engine-plugin",
                plugin_config=plugin_config,
            ),
        )

        evaluator = get_evaluator(control_evaluator)
        result = evaluator.evaluate(data=0.8)

        # Verify config was used
        assert result.metadata["threshold"] == 0.75


class TestPluginIntegrationWithEngine:
    """Integration tests for plugins with the engine."""

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_plugin_in_control_flow(self, mock_get_plugin):
        """Test plugin evaluator in typical control flow."""
        mock_get_plugin.return_value = MockTestPlugin

        # 1. Create control evaluator config
        control_evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="test-engine-plugin",
                plugin_config={"threshold": 0.6},
            ),
        )

        # 2. Get evaluator from factory
        evaluator = get_evaluator(control_evaluator)

        # 3. Evaluate some data
        result = evaluator.evaluate(data=0.8)

        # 4. Verify result
        assert result.matched is True
        assert result.confidence == 1.0

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_multiple_plugin_evaluations(self, mock_get_plugin):
        """Test multiple evaluations with same plugin."""
        mock_get_plugin.return_value = MockTestPlugin

        control_evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="test-engine-plugin",
                plugin_config={"threshold": 0.5},
            ),
        )

        evaluator = get_evaluator(control_evaluator)

        # Multiple evaluations
        results = [
            evaluator.evaluate(data=0.2),
            evaluator.evaluate(data=0.6),
            evaluator.evaluate(data=0.9),
        ]

        assert results[0].matched is False  # 0.2 < 0.5
        assert results[1].matched is True  # 0.6 > 0.5
        assert results[2].matched is True  # 0.9 > 0.5

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_plugin_with_different_data_types(self, mock_get_plugin):
        """Test plugin handles different data types."""
        mock_get_plugin.return_value = MockTestPlugin

        control_evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="test-engine-plugin",
                plugin_config={"threshold": 0.5},
            ),
        )

        evaluator = get_evaluator(control_evaluator)

        # Test with different types
        result_int = evaluator.evaluate(data=1)
        result_float = evaluator.evaluate(data=0.8)
        result_string = evaluator.evaluate(data="not a number")

        assert result_int.matched is True
        assert result_float.matched is True
        assert result_string.matched is False  # Converts to 0.0


class TestPluginMetadataAccess:
    """Tests for accessing plugin metadata."""

    @patch("agent_control_engine.evaluators.get_plugin")
    def test_access_plugin_metadata(self, mock_get_plugin):
        """Test that plugin metadata is accessible."""
        mock_get_plugin.return_value = MockTestPlugin

        config = PluginConfig(
            plugin_name="test-engine-plugin",
            plugin_config={},
        )

        plugin = _create_plugin_evaluator(config)

        # Plugin should have metadata
        assert hasattr(plugin, "metadata")
        assert plugin.metadata.name == "test-engine-plugin"
        assert plugin.metadata.version == "1.0.0"
