"""Unit tests for the Luna-2 plugin.

These tests mock the Galileo SDK to test the plugin logic without
requiring actual Galileo API access.

New architecture: Plugins take config at __init__, evaluate() only takes data.
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from agent_control_models import Evaluator, EvaluatorResult

# Mock the galileo module before importing luna2 plugin
mock_galileo = MagicMock()
mock_protect = MagicMock()
mock_protect.invoke_protect = MagicMock()
mock_galileo.protect = mock_protect

sys.modules["galileo"] = mock_galileo
sys.modules["galileo.protect"] = mock_protect

# Now import and reload the luna2 module to pick up the mocks
if "agent_control_plugins.luna2.plugin" in sys.modules:
    import importlib
    import agent_control_plugins.luna2.plugin

    importlib.reload(agent_control_plugins.luna2.plugin)


class TestLuna2Config:
    """Tests for Luna2Config Pydantic model."""

    def test_local_stage_config_valid(self):
        """Test valid local stage configuration."""
        from agent_control_plugins.luna2 import Luna2Config

        config = Luna2Config(
            stage_type="local",
            metric="input_toxicity",
            operator="gt",
            target_value="0.5",
        )

        assert config.stage_type == "local"
        assert config.metric == "input_toxicity"
        assert config.operator == "gt"
        assert config.target_value == "0.5"
        assert config.timeout_ms == 10000  # Default
        assert config.on_error == "allow"  # Default

    def test_central_stage_config_valid(self):
        """Test valid central stage configuration."""
        from agent_control_plugins.luna2 import Luna2Config

        config = Luna2Config(
            stage_type="central",
            stage_name="production-guard",
            galileo_project="my-project",
        )

        assert config.stage_type == "central"
        assert config.stage_name == "production-guard"
        assert config.galileo_project == "my-project"

    def test_local_stage_requires_metric(self):
        """Test local stage requires metric field."""
        from agent_control_plugins.luna2 import Luna2Config

        with pytest.raises(ValidationError, match="metric.*required"):
            Luna2Config(
                stage_type="local",
                operator="gt",
                target_value="0.5",
            )

    def test_local_stage_requires_operator(self):
        """Test local stage requires operator field."""
        from agent_control_plugins.luna2 import Luna2Config

        with pytest.raises(ValidationError, match="operator.*required"):
            Luna2Config(
                stage_type="local",
                metric="input_toxicity",
                target_value="0.5",
            )

    def test_local_stage_requires_target_value(self):
        """Test local stage requires target_value field."""
        from agent_control_plugins.luna2 import Luna2Config

        with pytest.raises(ValidationError, match="target_value.*required"):
            Luna2Config(
                stage_type="local",
                metric="input_toxicity",
                operator="gt",
            )

    def test_central_stage_requires_stage_name(self):
        """Test central stage requires stage_name field."""
        from agent_control_plugins.luna2 import Luna2Config

        with pytest.raises(ValidationError, match="stage_name.*required"):
            Luna2Config(
                stage_type="central",
                galileo_project="my-project",
            )

    def test_timeout_ms_validation(self):
        """Test timeout_ms must be within valid range."""
        from agent_control_plugins.luna2 import Luna2Config

        # Too low
        with pytest.raises(ValidationError):
            Luna2Config(
                stage_type="central",
                stage_name="test",
                timeout_ms=500,  # Below 1000
            )

        # Too high
        with pytest.raises(ValidationError):
            Luna2Config(
                stage_type="central",
                stage_name="test",
                timeout_ms=100000,  # Above 60000
            )

        # Valid
        config = Luna2Config(
            stage_type="central",
            stage_name="test",
            timeout_ms=30000,
        )
        assert config.timeout_ms == 30000

    def test_on_error_validation(self):
        """Test on_error must be 'allow' or 'deny'."""
        from agent_control_plugins.luna2 import Luna2Config

        config_allow = Luna2Config(
            stage_type="central",
            stage_name="test",
            on_error="allow",
        )
        assert config_allow.on_error == "allow"

        config_deny = Luna2Config(
            stage_type="central",
            stage_name="test",
            on_error="deny",
        )
        assert config_deny.on_error == "deny"

        with pytest.raises(ValidationError):
            Luna2Config(
                stage_type="central",
                stage_name="test",
                on_error="invalid",
            )

    def test_metric_validation(self):
        """Test metric must be a valid Luna2 metric."""
        from agent_control_plugins.luna2 import Luna2Config

        # Valid metrics
        valid_metrics = [
            "input_toxicity",
            "output_toxicity",
            "prompt_injection",
            "pii_detection",
            "hallucination",
            "tone",
        ]
        for metric in valid_metrics:
            config = Luna2Config(
                stage_type="local",
                metric=metric,
                operator="gt",
                target_value="0.5",
            )
            assert config.metric == metric

        # Invalid metric
        with pytest.raises(ValidationError):
            Luna2Config(
                stage_type="local",
                metric="invalid_metric",
                operator="gt",
                target_value="0.5",
            )

    def test_operator_validation(self):
        """Test operator must be a valid Luna2 operator."""
        from agent_control_plugins.luna2 import Luna2Config

        valid_operators = ["gt", "lt", "gte", "lte", "eq", "contains", "any"]
        for op in valid_operators:
            config = Luna2Config(
                stage_type="local",
                metric="input_toxicity",
                operator=op,
                target_value="0.5",
            )
            assert config.operator == op

        with pytest.raises(ValidationError):
            Luna2Config(
                stage_type="local",
                metric="input_toxicity",
                operator="invalid_op",
                target_value="0.5",
            )

    def test_model_dump(self):
        """Test config can be dumped to dict."""
        from agent_control_plugins.luna2 import Luna2Config

        config = Luna2Config(
            stage_type="local",
            metric="input_toxicity",
            operator="gt",
            target_value="0.5",
            galileo_project="test-project",
        )

        data = config.model_dump(exclude_none=True)

        assert data["stage_type"] == "local"
        assert data["metric"] == "input_toxicity"
        assert data["operator"] == "gt"
        assert data["target_value"] == "0.5"
        assert data["galileo_project"] == "test-project"
        assert "stage_name" not in data  # None excluded


class TestLuna2PluginInheritance:
    """Tests for Luna-2 plugin inheritance."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    def test_plugin_extends_evaluator(self):
        """Test Luna2Plugin extends Evaluator."""
        from agent_control_plugins.luna2 import Luna2Plugin
        from agent_control_plugins import PluginEvaluator

        assert issubclass(Luna2Plugin, PluginEvaluator)
        assert issubclass(Luna2Plugin, Evaluator)


class TestLuna2PluginImport:
    """Tests for Luna-2 plugin import and initialization."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    def test_luna2_plugin_import_success(self):
        """Test importing Luna-2 plugin with SDK available."""
        from agent_control_plugins.luna2 import Luna2Plugin

        assert Luna2Plugin is not None
        assert Luna2Plugin.metadata.name == "galileo-luna2"
        assert Luna2Plugin.metadata.version == "1.0.0"

    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", False)
    def test_luna2_plugin_init_without_sdk_raises_error(self):
        """Test that initializing without SDK raises ImportError."""
        from agent_control_plugins.luna2 import Luna2Plugin

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.5",
        }

        with pytest.raises(ImportError, match="Galileo SDK"):
            Luna2Plugin(config)

    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch.dict(os.environ, {}, clear=True)
    def test_luna2_plugin_init_without_api_key_raises_error(self):
        """Test that initializing without API key raises ValueError."""
        from agent_control_plugins.luna2 import Luna2Plugin

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.5",
        }

        with pytest.raises(ValueError, match="GALILEO_API_KEY"):
            Luna2Plugin(config)


class TestLuna2PluginMetadata:
    """Tests for Luna-2 plugin metadata."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    def test_metadata_fields(self):
        """Test Luna-2 plugin metadata fields."""
        from agent_control_plugins.luna2 import Luna2Plugin

        metadata = Luna2Plugin.metadata

        assert metadata.name == "galileo-luna2"
        assert metadata.requires_api_key is True
        assert metadata.timeout_ms == 10000
        assert metadata.config_schema is not None

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    def test_config_schema_supported_metrics(self):
        """Test config schema includes all supported metrics."""
        from agent_control_plugins.luna2 import Luna2Plugin

        schema = Luna2Plugin.metadata.config_schema
        metric_enum = schema["properties"]["metric"]["enum"]

        assert "input_toxicity" in metric_enum
        assert "output_toxicity" in metric_enum
        assert "prompt_injection" in metric_enum
        assert "pii_detection" in metric_enum
        assert "hallucination" in metric_enum


class TestLuna2PluginLocalStage:
    """Tests for Luna-2 plugin with local stages."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_local_stage_triggered(self, mock_invoke):
        """Test local stage evaluation when rule is triggered."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "triggered",
            "text": "Toxic content detected",
            "trace_metadata": {
                "id": "trace-123",
                "received_at": 1234567890,
                "response_at": 1234567900,
                "execution_time": 150,
            },
        }

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
            "galileo_project": "test-project",
        }

        plugin = Luna2Plugin(config)
        result = plugin.evaluate(data="toxic content here")

        assert isinstance(result, EvaluatorResult)
        assert result.matched is True
        assert result.confidence == 1.0
        assert "toxic content detected" in result.message.lower()
        assert result.metadata["trace_id"] == "trace-123"
        assert result.metadata["metric"] == "input_toxicity"
        assert result.metadata["status"] == "triggered"

        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["project_name"] == "test-project"
        assert call_kwargs["payload"]["input"] == "toxic content here"
        assert len(call_kwargs["prioritized_rulesets"]) == 1

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_local_stage_not_triggered(self, mock_invoke):
        """Test local stage evaluation when rule is not triggered."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "success",
            "text": "Content is safe",
            "trace_metadata": {"id": "trace-456", "execution_time": 120},
        }

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
            "galileo_project": "test-project",
        }

        plugin = Luna2Plugin(config)
        result = plugin.evaluate(data="hello world")

        assert result.matched is False
        assert result.confidence == 0.0
        assert result.metadata["status"] == "success"

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_local_stage_with_timeout_ms(self, mock_invoke):
        """Test local stage respects timeout_ms configuration."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "success",
            "text": "OK",
            "trace_metadata": {"id": "trace-789"},
        }

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
            "galileo_project": "test-project",
            "timeout_ms": 5000,
        }

        plugin = Luna2Plugin(config)
        plugin.evaluate(data="test")

        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["timeout"] == 5.0


class TestLuna2PluginCentralStage:
    """Tests for Luna-2 plugin with central stages."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_central_stage_evaluation(self, mock_invoke):
        """Test central stage evaluation."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "triggered",
            "text": "Central stage rule triggered",
            "trace_metadata": {"id": "trace-central-1"},
        }

        config = {
            "stage_type": "central",
            "stage_name": "enterprise-protection",
            "stage_version": 2,
            "galileo_project": "prod-project",
        }

        plugin = Luna2Plugin(config)
        result = plugin.evaluate(data="test input")

        assert result.matched is True

        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["stage_name"] == "enterprise-protection"
        assert call_kwargs["stage_version"] == 2
        assert "prioritized_rulesets" not in call_kwargs

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_central_stage_without_version(self, mock_invoke):
        """Test central stage without pinned version."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "success",
            "text": "OK",
            "trace_metadata": {"id": "trace-latest"},
        }

        config = {
            "stage_type": "central",
            "stage_name": "latest-protection",
            "galileo_project": "prod-project",
        }

        plugin = Luna2Plugin(config)
        plugin.evaluate(data="test")

        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["stage_name"] == "latest-protection"


class TestLuna2PluginPayloadPreparation:
    """Tests for payload preparation logic."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_input_metric_payload(self, mock_invoke):
        """Test payload for input metrics."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "success",
            "text": "OK",
            "trace_metadata": {"id": "t1"},
        }

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
        }

        plugin = Luna2Plugin(config)
        plugin.evaluate(data="user input text")

        payload = mock_invoke.call_args.kwargs["payload"]
        assert payload["input"] == "user input text"
        assert payload["output"] == ""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_output_metric_payload(self, mock_invoke):
        """Test payload for output metrics."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "success",
            "text": "OK",
            "trace_metadata": {"id": "t2"},
        }

        config = {
            "stage_type": "local",
            "metric": "output_toxicity",
            "operator": "gt",
            "target_value": "0.7",
        }

        plugin = Luna2Plugin(config)
        plugin.evaluate(data="llm output text")

        payload = mock_invoke.call_args.kwargs["payload"]
        assert payload["input"] == ""
        assert payload["output"] == "llm output text"

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_payload_field_override(self, mock_invoke):
        """Test explicit payload_field configuration."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = {
            "status": "success",
            "text": "OK",
            "trace_metadata": {"id": "t4"},
        }

        config = {
            "stage_type": "central",
            "stage_name": "test-stage",
            "payload_field": "output",
        }

        plugin = Luna2Plugin(config)
        plugin.evaluate(data="some data")

        payload = mock_invoke.call_args.kwargs["payload"]
        assert payload["input"] == ""
        assert payload["output"] == "some data"


class TestLuna2PluginErrorHandling:
    """Tests for error handling in Luna-2 plugin."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_error_with_fail_open(self, mock_invoke):
        """Test error handling with fail open (default)."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.side_effect = Exception("Luna-2 API unavailable")

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
            "on_error": "allow",
        }

        plugin = Luna2Plugin(config)
        result = plugin.evaluate(data="test")

        assert result.matched is False
        assert result.confidence == 0.0
        assert "error" in result.message.lower()
        assert result.metadata["fallback_action"] == "allow"

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_error_with_fail_closed(self, mock_invoke):
        """Test error handling with fail closed."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.side_effect = Exception("Luna-2 API error")

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
            "on_error": "deny",
        }

        plugin = Luna2Plugin(config)
        result = plugin.evaluate(data="test")

        assert result.matched is True
        assert result.confidence == 0.0
        assert "error" in result.message.lower()
        assert result.metadata["fallback_action"] == "deny"

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    @patch("agent_control_plugins.luna2.plugin.invoke_protect")
    def test_empty_response_handling(self, mock_invoke):
        """Test handling of empty/None response."""
        from agent_control_plugins.luna2 import Luna2Plugin

        mock_invoke.return_value = None

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.8",
        }

        plugin = Luna2Plugin(config)
        result = plugin.evaluate(data="test")

        assert result.matched is False
        assert "No response from Luna-2" in result.message
        assert result.metadata["error"] == "empty_response"


class TestLuna2PluginTimeoutHelper:
    """Tests for timeout helper method."""

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    def test_get_timeout_from_config(self):
        """Test timeout conversion from config."""
        from agent_control_plugins.luna2 import Luna2Plugin

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.5",
            "timeout_ms": 5000,
        }

        plugin = Luna2Plugin(config)
        assert plugin.get_timeout_seconds() == 5.0

    @patch.dict(os.environ, {"GALILEO_API_KEY": "test-key"})
    @patch("agent_control_plugins.luna2.plugin.LUNA2_AVAILABLE", True)
    def test_get_timeout_from_default(self):
        """Test timeout uses metadata default."""
        from agent_control_plugins.luna2 import Luna2Plugin

        config = {
            "stage_type": "local",
            "metric": "input_toxicity",
            "operator": "gt",
            "target_value": "0.5",
            # No timeout_ms - should use default
        }

        plugin = Luna2Plugin(config)
        assert plugin.get_timeout_seconds() == 10.0  # Default from metadata
