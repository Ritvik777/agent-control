"""Unit tests for the plugin system.

Tests plugin registration, discovery, and base functionality without
requiring actual plugin implementations or external services.

New architecture: Plugins take config at __init__, evaluate() only takes data.
"""

import os

import pytest
from unittest.mock import MagicMock, patch

from agent_control.plugins import (
    PluginEvaluator,
    PluginMetadata,
    get_plugin,
    list_plugins,
    register_plugin,
)
from agent_control_models.controls import EvaluatorResult


class MockPlugin(PluginEvaluator):
    """Mock plugin for testing.

    New pattern: config is passed at __init__, not at evaluate().
    """

    metadata = PluginMetadata(
        name="test-mock-plugin",
        version="1.0.0",
        description="Mock plugin for testing",
        requires_api_key=False,
        timeout_ms=10,
        config_schema={
            "type": "object",
            "properties": {"threshold": {"type": "number"}},
        },
    )

    def __init__(self, config: dict):
        super().__init__(config)
        self.threshold = config.get("threshold", 0.5)

    def evaluate(self, data) -> EvaluatorResult:
        """Mock evaluation (synchronous)."""
        matched = float(data) > self.threshold if isinstance(data, (int, float)) else False
        return EvaluatorResult(
            matched=matched,
            confidence=1.0,
            message=f"Mock evaluation: {matched}",
            metadata={"threshold": self.threshold},
        )


class TestPluginMetadata:
    """Tests for PluginMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating plugin metadata."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
        )

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.requires_api_key is False
        assert metadata.timeout_ms == 10000  # Default
        assert metadata.config_schema is None

    def test_metadata_with_all_fields(self):
        """Test metadata with all fields populated."""
        schema = {"type": "object", "properties": {}}

        metadata = PluginMetadata(
            name="full-plugin",
            version="2.0.0",
            description="Full test",
            requires_api_key=True,
            timeout_ms=5000,
            config_schema=schema,
        )

        assert metadata.requires_api_key is True
        assert metadata.timeout_ms == 5000
        assert metadata.config_schema == schema


class TestPluginRegistry:
    """Tests for plugin registry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        from agent_control.plugins import registry

        # Clear any previously registered test plugins
        if "test-mock-plugin" in registry._PLUGIN_REGISTRY:
            del registry._PLUGIN_REGISTRY["test-mock-plugin"]
        # Reset discovery state for clean tests
        registry._DISCOVERY_COMPLETE = True  # Prevent auto-discovery during tests

    def test_register_plugin(self):
        """Test registering a plugin."""
        # Register mock plugin
        register_plugin(MockPlugin)

        # Verify it's registered
        plugin_class = get_plugin("test-mock-plugin")
        assert plugin_class is MockPlugin

    def test_get_nonexistent_plugin(self):
        """Test getting a plugin that doesn't exist."""
        plugin_class = get_plugin("nonexistent-plugin-xyz")
        assert plugin_class is None

    def test_list_plugins_includes_registered(self):
        """Test listing plugins includes registered plugins."""
        # Register mock plugin
        register_plugin(MockPlugin)

        # List plugins
        plugins = list_plugins()

        assert "test-mock-plugin" in plugins
        assert plugins["test-mock-plugin"]["name"] == "test-mock-plugin"
        assert plugins["test-mock-plugin"]["version"] == "1.0.0"
        assert plugins["test-mock-plugin"]["description"] == "Mock plugin for testing"

    def test_register_duplicate_plugin_raises_error(self):
        """Test that registering a plugin twice raises ValueError."""
        # Ensure plugin is registered first
        try:
            register_plugin(MockPlugin)
        except ValueError:
            # Already registered from previous test, that's fine
            pass

        # Second registration should fail
        with pytest.raises(ValueError, match="already registered"):
            register_plugin(MockPlugin)


class TestPluginEvaluator:
    """Tests for PluginEvaluator base class."""

    def test_plugin_evaluate(self):
        """Test synchronous evaluation."""
        # Config is now passed at init
        plugin = MockPlugin({"threshold": 0.5})
        result = plugin.evaluate(data=0.8)

        assert isinstance(result, EvaluatorResult)
        assert result.matched is True
        assert result.confidence == 1.0
        assert "Mock evaluation" in result.message

    def test_plugin_evaluate_no_match(self):
        """Test evaluation when rule doesn't match."""
        plugin = MockPlugin({"threshold": 0.5})
        result = plugin.evaluate(data=0.3)

        assert isinstance(result, EvaluatorResult)
        assert result.matched is False
        assert result.confidence == 1.0

    def test_plugin_with_different_configs(self):
        """Test plugin uses config correctly (set at init)."""
        # Create two plugins with different configs
        plugin_low = MockPlugin({"threshold": 0.5})
        plugin_high = MockPlugin({"threshold": 0.7})

        # Same data, different thresholds
        assert plugin_low.evaluate(data=0.6).matched is True
        assert plugin_high.evaluate(data=0.6).matched is False

    def test_plugin_metadata_accessible(self):
        """Test that plugin metadata is accessible."""
        plugin = MockPlugin({"threshold": 0.5})

        assert plugin.metadata.name == "test-mock-plugin"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.metadata.timeout_ms == 10

    def test_plugin_config_stored(self):
        """Test that plugin stores config."""
        config = {"threshold": 0.75, "extra": "value"}
        plugin = MockPlugin(config)

        assert plugin.config == config
        assert plugin.threshold == 0.75


class TestPluginDiscovery:
    """Tests for plugin discovery mechanism."""

    def setup_method(self):
        """Reset discovery state before each test."""
        from agent_control.plugins import registry

        registry._DISCOVERY_COMPLETE = False
        # Clear test plugins
        if "test-mock-plugin" in registry._PLUGIN_REGISTRY:
            del registry._PLUGIN_REGISTRY["test-mock-plugin"]

    @patch("agent_control.plugins.registry._load_luna2_plugin")
    @patch("agent_control.plugins.registry._load_entry_point_plugins")
    def test_discover_plugins_calls_loaders(self, mock_entry_points, mock_luna2):
        """Test that discover_plugins calls all loader functions."""
        from agent_control.plugins.registry import discover_plugins

        discover_plugins()

        mock_luna2.assert_called_once()
        mock_entry_points.assert_called_once()

    @patch("agent_control.plugins.registry._load_luna2_plugin")
    @patch("agent_control.plugins.registry._load_entry_point_plugins")
    def test_lazy_discovery_on_get_plugin(self, mock_entry_points, mock_luna2):
        """Test that get_plugin triggers lazy discovery."""
        from agent_control.plugins import registry
        from agent_control.plugins.registry import get_plugin

        registry._DISCOVERY_COMPLETE = False
        get_plugin("some-plugin")

        mock_luna2.assert_called_once()
        mock_entry_points.assert_called_once()

    @patch.dict(os.environ, {"AGENT_CONTROL_DISABLE_PLUGIN_DISCOVERY": "1"})
    @patch("agent_control.plugins.registry._load_luna2_plugin")
    def test_discovery_disabled_via_env(self, mock_luna2):
        """Test that discovery can be disabled via environment variable."""
        from agent_control.plugins import registry
        from agent_control.plugins.registry import discover_plugins

        registry._DISCOVERY_COMPLETE = False
        discover_plugins()

        mock_luna2.assert_not_called()

    def test_load_luna2_plugin_handles_import_error(self):
        """Test that Luna-2 plugin load handles ImportError gracefully."""
        from agent_control.plugins.registry import _load_luna2_plugin

        # Should not raise an exception
        try:
            _load_luna2_plugin()
        except Exception as e:
            pytest.fail(f"Luna-2 loader should handle errors gracefully: {e}")

    @patch("importlib.metadata.entry_points")
    def test_load_entry_point_plugins(self, mock_entry_points):
        """Test loading plugins via entry points."""
        mock_ep = MagicMock()
        mock_ep.name = "custom-plugin"
        mock_ep.load.return_value = MockPlugin

        mock_entry_points.return_value = [mock_ep]

        from agent_control.plugins.registry import _load_entry_point_plugins

        _load_entry_point_plugins()

        mock_ep.load.assert_called_once()
