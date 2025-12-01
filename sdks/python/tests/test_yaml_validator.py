"""Tests for YAML validation functionality."""

import tempfile
from pathlib import Path

import pytest
import yaml

from agent_control import ValidationResult, YAMLValidator, validate_yaml


class TestYAMLValidator:
    """Test suite for YAMLValidator class."""

    def test_valid_yaml_file(self, tmp_path: Path):
        """Test validation of a valid YAML file."""
        yaml_content = {
            "pii-detection": {
                "step_id": "pii-check",
                "description": "Detect PII",
                "enabled": True,
                "rules": [
                    {
                        "match": {"regex": r"\b\d{3}-\d{2}-\d{4}\b"},
                        "action": "deny",
                        "data": "input",
                        "message": "SSN detected"
                    }
                ],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "test.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert result.valid
        assert result.controls_count == 1
        assert "pii-detection" in result.control_names
        assert len(result.errors) == 0

    def test_invalid_yaml_syntax(self, tmp_path: Path):
        """Test validation of YAML with syntax errors."""
        yaml_file = tmp_path / "invalid.yaml"
        with open(yaml_file, 'w') as f:
            f.write("invalid: yaml: syntax\n  bad: indentation")
        
        result = validate_yaml(yaml_file)
        
        assert not result.valid
        assert len(result.errors) > 0
        assert any("parse error" in err.lower() for err in result.errors)

    def test_missing_required_fields(self, tmp_path: Path):
        """Test validation catches missing required fields."""
        yaml_content = {
            "missing-step-id": {
                "description": "Missing step_id",
                "rules": []
            }
        }
        
        yaml_file = tmp_path / "missing.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert not result.valid
        assert any("step_id" in err.lower() for err in result.errors)

    def test_invalid_regex_pattern(self, tmp_path: Path):
        """Test validation catches invalid regex patterns."""
        yaml_content = {
            "bad-regex": {
                "step_id": "test",
                "rules": [
                    {
                        "match": {"regex": "[unclosed"},
                        "action": "deny",
                        "data": "input"
                    }
                ],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "bad_regex.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert not result.valid
        assert any("regex" in err.lower() for err in result.errors)

    def test_invalid_action_type(self, tmp_path: Path):
        """Test validation catches invalid action types."""
        yaml_content = {
            "bad-action": {
                "step_id": "test",
                "rules": [
                    {
                        "match": {"string": ["test"]},
                        "action": "block",  # Invalid action
                        "data": "input"
                    }
                ],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "bad_action.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert not result.valid
        assert any("action" in err.lower() for err in result.errors)

    def test_warnings_in_normal_mode(self, tmp_path: Path):
        """Test that warnings are generated in normal mode."""
        yaml_content = {
            "no-description": {
                "step_id": "test",
                "rules": [],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "warnings.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file, strict=False)
        
        assert result.valid
        assert len(result.warnings) > 0
        assert any("description" in warn.lower() for warn in result.warnings)

    def test_warnings_as_errors_in_strict_mode(self, tmp_path: Path):
        """Test that warnings become errors in strict mode."""
        yaml_content = {
            "no-description": {
                "step_id": "test",
                "rules": [],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "strict.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file, strict=True)
        
        assert not result.valid
        assert len(result.errors) > 0
        assert len(result.warnings) == 0

    def test_multiple_controls(self, tmp_path: Path):
        """Test validation of multiple controls in one file."""
        yaml_content = {
            "control-1": {
                "step_id": "test-1",
                "description": "First control",
                "rules": [],
                "default_action": "allow"
            },
            "control-2": {
                "step_id": "test-2",
                "description": "Second control",
                "rules": [],
                "default_action": "allow"
            },
            "control-3": {
                "step_id": "test-3",
                "description": "Third control",
                "rules": [],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "multiple.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert result.valid
        assert result.controls_count == 3
        assert len(result.control_names) == 3

    def test_empty_yaml_file(self, tmp_path: Path):
        """Test validation of empty YAML file."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        
        result = validate_yaml(yaml_file)
        
        assert not result.valid
        assert any("empty" in err.lower() for err in result.errors)

    def test_file_not_found(self):
        """Test validation of non-existent file."""
        result = validate_yaml("nonexistent.yaml")
        
        assert not result.valid
        assert any("not found" in err.lower() for err in result.errors)

    def test_validate_string(self):
        """Test validation of YAML content from string."""
        yaml_content = """
pii-check:
  step_id: "pii"
  description: "PII detection"
  rules:
    - match:
        string: ["test"]
      action: deny
      data: input
  default_action: allow
"""
        validator = YAMLValidator(strict=False)
        result = validator.validate_string(yaml_content)
        
        assert result.valid
        assert result.controls_count == 1

    def test_rate_limit_configuration(self, tmp_path: Path):
        """Test validation of rate limit configuration."""
        yaml_content = {
            "rate-limiter": {
                "step_id": "rate-limit",
                "description": "Rate limiting",
                "rate_limit": {
                    "max_requests": 10,
                    "time_window": 60
                },
                "action": "deny",
                "message": "Rate limit exceeded",
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "rate_limit.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert result.valid

    def test_rate_limit_without_action_fails(self, tmp_path: Path):
        """Test that rate_limit without action fails validation."""
        yaml_content = {
            "bad-rate-limit": {
                "step_id": "rate-limit",
                "rate_limit": {
                    "max_requests": 10,
                    "time_window": 60
                },
                "default_action": "allow"
                # Missing action!
            }
        }
        
        yaml_file = tmp_path / "bad_rate_limit.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert not result.valid
        assert any("action" in err.lower() for err in result.errors)

    def test_complex_control(self, tmp_path: Path):
        """Test validation of complex control with multiple rules."""
        yaml_content = {
            "complex-control": {
                "step_id": "multi-check",
                "description": "Complex validation",
                "enabled": True,
                "rules": [
                    {
                        "match": {"string": ["test1", "test2"]},
                        "action": "deny",
                        "data": "input",
                        "message": "String match"
                    },
                    {
                        "match": {"regex": r"\d+"},
                        "action": "log",
                        "data": "output",
                        "message": "Number detected"
                    },
                    {
                        "match": {"string": ["redact-me"]},
                        "action": "redact",
                        "data": "output",
                        "replacement": "[REDACTED]"
                    }
                ],
                "default_action": "allow"
            }
        }
        
        yaml_file = tmp_path / "complex.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_content, f)
        
        result = validate_yaml(yaml_file)
        
        assert result.valid
        assert result.controls_count == 1


class TestValidationResult:
    """Test ValidationResult model."""

    def test_validation_result_creation(self):
        """Test creating a ValidationResult."""
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=["Warning 1"],
            controls_count=5,
            control_names=["c1", "c2", "c3", "c4", "c5"]
        )
        
        assert result.valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.controls_count == 5

    def test_validation_result_defaults(self):
        """Test ValidationResult with default values."""
        result = ValidationResult(valid=False)
        
        assert not result.valid
        assert result.errors == []
        assert result.warnings == []
        assert result.controls_count == 0
        assert result.control_names == []


@pytest.fixture
def tmp_path(tmp_path_factory):
    """Create a temporary directory for test files."""
    return tmp_path_factory.mktemp("yaml_tests")

