"""Tests for plugin-related Pydantic models.

Tests validation and serialization of PluginConfig and PluginControlEvaluator.
"""

import pytest
from pydantic import ValidationError

from agent_control_models.controls import (
    ControlDefinition,
    ControlSelector,
    ControlAction,
    PluginConfig,
    PluginControlEvaluator,
)


class TestPluginConfig:
    """Tests for PluginConfig model."""

    def test_plugin_config_creation(self):
        """Test creating a valid PluginConfig."""
        config = PluginConfig(
            plugin_name="galileo-luna2",
            plugin_config={
                "metric": "input_toxicity",
                "operator": "gt",
                "target_value": 0.8,
            },
        )

        assert config.plugin_name == "galileo-luna2"
        assert config.plugin_config["metric"] == "input_toxicity"
        assert config.plugin_config["operator"] == "gt"
        assert config.plugin_config["target_value"] == 0.8

    def test_plugin_config_empty_plugin_config(self):
        """Test PluginConfig with empty plugin_config dict."""
        config = PluginConfig(plugin_name="test-plugin", plugin_config={})

        assert config.plugin_name == "test-plugin"
        assert config.plugin_config == {}

    def test_plugin_config_complex_nested_config(self):
        """Test PluginConfig with nested configuration."""
        config = PluginConfig(
            plugin_name="complex-plugin",
            plugin_config={
                "level1": {
                    "level2": {"value": 123, "flag": True},
                    "list": [1, 2, 3],
                },
                "simple": "value",
            },
        )

        assert config.plugin_config["level1"]["level2"]["value"] == 123
        assert config.plugin_config["level1"]["list"] == [1, 2, 3]

    def test_plugin_config_serialization(self):
        """Test PluginConfig serialization to dict."""
        config = PluginConfig(
            plugin_name="test-plugin",
            plugin_config={"key": "value", "number": 42},
        )

        data = config.model_dump()

        assert data["plugin_name"] == "test-plugin"
        assert data["plugin_config"]["key"] == "value"
        assert data["plugin_config"]["number"] == 42

    def test_plugin_config_json_serialization(self):
        """Test PluginConfig JSON serialization."""
        config = PluginConfig(
            plugin_name="test-plugin", plugin_config={"threshold": 0.5}
        )

        json_str = config.model_dump_json()

        assert "test-plugin" in json_str
        assert "threshold" in json_str
        assert "0.5" in json_str


class TestPluginControlEvaluator:
    """Tests for PluginControlEvaluator model."""

    def test_plugin_control_evaluator_creation(self):
        """Test creating a valid PluginControlEvaluator."""
        evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="galileo-luna2",
                plugin_config={"metric": "input_toxicity", "operator": "gt"},
            ),
        )

        assert evaluator.type == "plugin"
        assert evaluator.config.plugin_name == "galileo-luna2"
        assert evaluator.config.plugin_config["metric"] == "input_toxicity"

    def test_plugin_control_evaluator_type_must_be_plugin(self):
        """Test that type must be 'plugin'."""
        # This should work
        evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(plugin_name="test", plugin_config={}),
        )
        assert evaluator.type == "plugin"

        # Pydantic will enforce the Literal["plugin"] type
        # Trying to create with wrong type will fail at type checking level

    def test_plugin_control_evaluator_serialization(self):
        """Test serialization of PluginControlEvaluator."""
        evaluator = PluginControlEvaluator(
            type="plugin",
            config=PluginConfig(
                plugin_name="test-plugin",
                plugin_config={"threshold": 0.7, "metric": "test"},
            ),
        )

        data = evaluator.model_dump()

        assert data["type"] == "plugin"
        assert data["config"]["plugin_name"] == "test-plugin"
        assert data["config"]["plugin_config"]["threshold"] == 0.7

    def test_plugin_control_evaluator_deserialization(self):
        """Test deserializing PluginControlEvaluator from dict."""
        data = {
            "type": "plugin",
            "config": {
                "plugin_name": "galileo-luna2",
                "plugin_config": {
                    "metric": "input_toxicity",
                    "operator": "gt",
                    "target_value": 0.8,
                },
            },
        }

        evaluator = PluginControlEvaluator(**data)

        assert evaluator.type == "plugin"
        assert evaluator.config.plugin_name == "galileo-luna2"
        assert evaluator.config.plugin_config["target_value"] == 0.8


class TestPluginInControlDefinition:
    """Tests for using plugins in full ControlDefinition."""

    def test_control_definition_with_plugin(self):
        """Test creating a full ControlDefinition with plugin evaluator."""
        control = ControlDefinition(
            description="Block toxic inputs using Luna-2",
            enabled=True,
            applies_to="llm_call",
            check_stage="pre",
            selector=ControlSelector(path="input"),
            evaluator=PluginControlEvaluator(
                type="plugin",
                config=PluginConfig(
                    plugin_name="galileo-luna2",
                    plugin_config={
                        "stage_type": "local",
                        "metric": "input_toxicity",
                        "operator": "gt",
                        "target_value": 0.8,
                        "galileo_project": "test-project",
                    },
                ),
            ),
            action=ControlAction(decision="deny"),
            tags=["safety", "luna2"],
        )

        assert control.evaluator.type == "plugin"
        assert control.evaluator.config.plugin_name == "galileo-luna2"
        assert control.action.decision == "deny"

    def test_control_definition_plugin_serialization_roundtrip(self):
        """Test serialization roundtrip for ControlDefinition with plugin."""
        original = ControlDefinition(
            description="Test plugin control",
            enabled=True,
            applies_to="tool_call",
            check_stage="post",
            selector=ControlSelector(path="output"),
            evaluator=PluginControlEvaluator(
                type="plugin",
                config=PluginConfig(
                    plugin_name="test-plugin",
                    plugin_config={"key": "value", "threshold": 0.5},
                ),
            ),
            action=ControlAction(decision="warn"),
            tags=["test"],
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = ControlDefinition(**data)

        assert restored.evaluator.type == "plugin"
        assert restored.evaluator.config.plugin_name == "test-plugin"
        assert restored.evaluator.config.plugin_config["threshold"] == 0.5
        assert restored.action.decision == "warn"

    def test_control_definition_plugin_json_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original = ControlDefinition(
            description="JSON test",
            enabled=True,
            applies_to="llm_call",
            check_stage="pre",
            selector=ControlSelector(path="input"),
            evaluator=PluginControlEvaluator(
                type="plugin",
                config=PluginConfig(
                    plugin_name="galileo-luna2",
                    plugin_config={"metric": "pii_detection", "operator": "contains"},
                ),
            ),
            action=ControlAction(decision="deny"),
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = ControlDefinition.model_validate_json(json_str)

        assert restored.evaluator.type == "plugin"
        assert restored.evaluator.config.plugin_name == "galileo-luna2"
        assert restored.evaluator.config.plugin_config["metric"] == "pii_detection"


class TestPluginConfigValidation:
    """Tests for plugin configuration validation."""

    def test_plugin_config_requires_plugin_name(self):
        """Test that plugin_name is required."""
        with pytest.raises(ValidationError):
            PluginConfig(plugin_config={})

    def test_plugin_config_requires_plugin_config(self):
        """Test that plugin_config is required."""
        with pytest.raises(ValidationError):
            PluginConfig(plugin_name="test")

    def test_plugin_config_accepts_any_dict(self):
        """Test that plugin_config accepts any valid dict."""
        # Various valid configurations
        configs = [
            {},
            {"simple": "value"},
            {"complex": {"nested": {"deep": "value"}}},
            {"list": [1, 2, 3]},
            {"mixed": {"str": "text", "num": 42, "bool": True, "null": None}},
        ]

        for cfg in configs:
            plugin_cfg = PluginConfig(plugin_name="test", plugin_config=cfg)
            assert plugin_cfg.plugin_config == cfg


class TestPluginWithOtherEvaluators:
    """Tests for plugin evaluators alongside other evaluator types."""

    def test_control_with_regex_evaluator(self):
        """Test that regex evaluators still work."""
        from agent_control_models.controls import RegexConfig, RegexControlEvaluator

        control = ControlDefinition(
            description="Regex control",
            enabled=True,
            applies_to="llm_call",
            check_stage="post",
            selector=ControlSelector(path="output"),
            evaluator=RegexControlEvaluator(
                type="regex", config=RegexConfig(pattern=r"\d{3}-\d{2}-\d{4}")
            ),
            action=ControlAction(decision="deny"),
        )

        assert control.evaluator.type == "regex"

    def test_control_with_list_evaluator(self):
        """Test that list evaluators still work."""
        from agent_control_models.controls import ListConfig, ListControlEvaluator

        control = ControlDefinition(
            description="List control",
            enabled=True,
            applies_to="tool_call",
            check_stage="pre",
            selector=ControlSelector(path="tool_name"),
            evaluator=ListControlEvaluator(
                type="list",
                config=ListConfig(values=["delete", "remove", "drop"], logic="any"),
            ),
            action=ControlAction(decision="deny"),
        )

        assert control.evaluator.type == "list"

    def test_evaluator_discriminator_works(self):
        """Test that Pydantic discriminated union works for evaluators."""
        from agent_control_models.controls import (
            RegexConfig,
            RegexControlEvaluator,
            ListConfig,
            ListControlEvaluator,
        )

        # Plugin evaluator
        plugin_dict = {
            "type": "plugin",
            "config": {"plugin_name": "test", "plugin_config": {}},
        }
        plugin_eval = PluginControlEvaluator(**plugin_dict)
        assert plugin_eval.type == "plugin"

        # Regex evaluator
        regex_dict = {"type": "regex", "config": {"pattern": "test"}}
        regex_eval = RegexControlEvaluator(**regex_dict)
        assert regex_eval.type == "regex"

        # List evaluator
        list_dict = {"type": "list", "config": {"values": ["a", "b"]}}
        list_eval = ListControlEvaluator(**list_dict)
        assert list_eval.type == "list"


class TestLuna2SpecificConfiguration:
    """Tests for Luna-2 specific configuration patterns."""

    def test_luna2_local_stage_config(self):
        """Test typical Luna-2 local stage configuration."""
        config = PluginConfig(
            plugin_name="galileo-luna2",
            plugin_config={
                "stage_type": "local",
                "metric": "input_toxicity",
                "operator": "gt",
                "target_value": 0.8,
                "galileo_project": "my-project",
                "timeout": 5.0,
                "on_error": "allow",
            },
        )

        assert config.plugin_config["stage_type"] == "local"
        assert config.plugin_config["metric"] == "input_toxicity"
        assert config.plugin_config["target_value"] == 0.8

    def test_luna2_central_stage_config(self):
        """Test typical Luna-2 central stage configuration."""
        config = PluginConfig(
            plugin_name="galileo-luna2",
            plugin_config={
                "stage_type": "central",
                "stage_name": "enterprise-protection",
                "stage_version": 2,
                "galileo_project": "enterprise",
                "metric": "prompt_injection",
                "operator": "gt",
            },
        )

        assert config.plugin_config["stage_type"] == "central"
        assert config.plugin_config["stage_name"] == "enterprise-protection"
        assert config.plugin_config["stage_version"] == 2

    def test_luna2_pii_detection_config(self):
        """Test Luna-2 PII detection configuration."""
        config = PluginConfig(
            plugin_name="galileo-luna2",
            plugin_config={
                "stage_type": "local",
                "metric": "pii_detection",
                "operator": "contains",
                "target_value": ["ssn", "credit_card", "password"],
                "galileo_project": "pii-protected",
            },
        )

        assert config.plugin_config["metric"] == "pii_detection"
        assert config.plugin_config["operator"] == "contains"
        assert isinstance(config.plugin_config["target_value"], list)
        assert "ssn" in config.plugin_config["target_value"]

