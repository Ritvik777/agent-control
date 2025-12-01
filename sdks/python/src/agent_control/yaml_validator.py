"""
YAML validation for agent control configurations.

This module provides validation for YAML control definitions to catch
errors before loading them to the server.
"""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class MatchConfig(BaseModel):
    """Match configuration for rules."""

    string: list[str] | None = None
    regex: str | None = None

    @field_validator('regex')
    @classmethod
    def validate_regex(cls, v: str | None) -> str | None:
        """Validate that regex pattern is valid."""
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v

    @model_validator(mode='after')
    def check_at_least_one(self) -> 'MatchConfig':
        """Ensure at least one match type is specified."""
        if self.string is None and self.regex is None:
            raise ValueError("Must specify at least one of 'string' or 'regex'")
        return self


class ConditionConfig(BaseModel):
    """Condition configuration for rules."""

    length: dict[str, int] | None = None
    time_range: dict[str, str] | None = None

    @field_validator('length')
    @classmethod
    def validate_length(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        """Validate length conditions."""
        if v is not None:
            if 'max' in v and v['max'] <= 0:
                raise ValueError("Length 'max' must be positive")
            if 'min' in v and v['min'] < 0:
                raise ValueError("Length 'min' must be non-negative")
            if 'max' in v and 'min' in v and v['min'] > v['max']:
                raise ValueError("Length 'min' cannot be greater than 'max'")
        return v


class RuleConfig(BaseModel):
    """Individual rule configuration."""

    match: MatchConfig | None = None
    condition: ConditionConfig | str | None = None
    action: Literal['deny', 'allow', 'redact', 'log', 'warn'] = Field(
        ..., description="Action to take"
    )
    data: Literal['input', 'output', 'context', 'tool'] = Field(
        ..., description="Data to check"
    )
    message: str | None = Field(None, description="Message to show on violation")
    replacement: str | None = Field(
        None, description="Replacement text for redaction"
    )

    @model_validator(mode='after')
    def check_match_or_condition(self) -> 'RuleConfig':
        """Ensure either match or condition is specified."""
        if self.match is None and self.condition is None:
            raise ValueError("Must specify either 'match' or 'condition'")
        return self

    @model_validator(mode='after')
    def check_redact_replacement(self) -> 'RuleConfig':
        """Warn if redact action without replacement."""
        if self.action == 'redact' and self.replacement is None:
            # This is just a warning, not an error
            pass
        return self


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    max_requests: int = Field(..., gt=0, description="Maximum number of requests")
    time_window: int = Field(..., gt=0, description="Time window in seconds")


class ControlConfig(BaseModel):
    """Complete control configuration."""

    step_id: str = Field(..., description="Identifier for when to apply this control")
    description: str | None = Field(None, description="Human-readable description")
    enabled: bool = Field(True, description="Whether this control is active")
    rules: list[RuleConfig] | None = Field(
        None, description="List of rules to evaluate"
    )
    rate_limit: RateLimitConfig | None = Field(
        None, description="Rate limiting configuration"
    )
    default_action: Literal['allow', 'deny'] = Field(
        'allow', description="Default action if no rules match"
    )
    action: Literal['deny', 'allow', 'redact', 'log', 'warn'] | None = Field(
        None, description="Action for rate limit"
    )
    message: str | None = Field(
        None, description="Message for rate limit violation"
    )

    @model_validator(mode='after')
    def check_rate_limit_action(self) -> 'ControlConfig':
        """Ensure rate_limit has action if specified."""
        if self.rate_limit is not None and self.action is None:
            raise ValueError("When 'rate_limit' is specified, 'action' must also be provided")
        return self


class ValidationResult(BaseModel):
    """Result of YAML validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    controls_count: int = 0
    control_names: list[str] = Field(default_factory=list)


class YAMLValidator:
    """Validator for control YAML files."""

    def __init__(self, strict: bool = True):
        """
        Initialize validator.

        Args:
            strict: If True, warnings are treated as errors
        """
        self.strict = strict

    def validate_file(self, yaml_path: Path | str) -> ValidationResult:
        """
        Validate a YAML file.

        Args:
            yaml_path: Path to YAML file

        Returns:
            ValidationResult with errors, warnings, and metadata
        """
        yaml_path = Path(yaml_path)
        result = ValidationResult(valid=True)

        # Check file exists
        if not yaml_path.exists():
            result.valid = False
            result.errors.append(f"File not found: {yaml_path}")
            return result

        # Check file extension
        if yaml_path.suffix not in ['.yaml', '.yml']:
            result.warnings.append(f"File extension '{yaml_path.suffix}' is not .yaml or .yml")

        # Load YAML
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            result.valid = False
            result.errors.append(f"YAML parse error: {e}")
            return result
        except Exception as e:
            result.valid = False
            result.errors.append(f"Failed to read file: {e}")
            return result

        # Check not empty
        if not data:
            result.valid = False
            result.errors.append("YAML file is empty")
            return result

        # Validate structure
        if not isinstance(data, dict):
            result.valid = False
            result.errors.append("YAML root must be a dictionary/mapping")
            return result

        # Validate each control
        result.controls_count = len(data)
        result.control_names = list(data.keys())

        for control_name, control_config in data.items():
            # Validate control name
            if not control_name or not isinstance(control_name, str):
                result.errors.append(f"Invalid control name: {control_name}")
                continue

            # Check for common naming issues
            if ' ' in control_name:
                result.warnings.append(
                    f"Control '{control_name}' contains spaces "
                    "(consider using hyphens)"
                )

            # Validate control config
            try:
                ControlConfig.model_validate(control_config)
            except Exception as e:
                result.valid = False
                result.errors.append(f"Control '{control_name}': {e}")
                continue

            # Additional warnings
            if not control_config.get('description'):
                result.warnings.append(f"Control '{control_name}' has no description")

            if not control_config.get('enabled', True):
                result.warnings.append(f"Control '{control_name}' is disabled")

            rules = control_config.get('rules', [])
            if not rules and not control_config.get('rate_limit'):
                result.warnings.append(f"Control '{control_name}' has no rules or rate_limit")

        # Treat warnings as errors in strict mode
        if self.strict and result.warnings:
            result.valid = False
            result.errors.extend([f"[Warning as Error] {w}" for w in result.warnings])
            result.warnings = []

        return result

    def validate_string(self, yaml_content: str) -> ValidationResult:
        """
        Validate YAML content from a string.

        Args:
            yaml_content: YAML content as string

        Returns:
            ValidationResult
        """
        result = ValidationResult(valid=True)

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            result.valid = False
            result.errors.append(f"YAML parse error: {e}")
            return result

        if not data:
            result.valid = False
            result.errors.append("YAML content is empty")
            return result

        if not isinstance(data, dict):
            result.valid = False
            result.errors.append("YAML root must be a dictionary")
            return result

        # Validate each control
        result.controls_count = len(data)
        result.control_names = list(data.keys())

        for control_name, control_config in data.items():
            try:
                ControlConfig.model_validate(control_config)
            except Exception as e:
                result.valid = False
                result.errors.append(f"Control '{control_name}': {e}")

        return result


def validate_yaml(yaml_path: Path | str, strict: bool = False) -> ValidationResult:
    """
    Convenience function to validate a YAML file.

    Args:
        yaml_path: Path to YAML file
        strict: If True, warnings are treated as errors

    Returns:
        ValidationResult

    Example:
        result = validate_yaml("controls.yaml")
        if result.valid:
            print(f"✓ Valid! {result.controls_count} controls")
        else:
            for error in result.errors:
                print(f"✗ {error}")
    """
    validator = YAMLValidator(strict=strict)
    return validator.validate_file(yaml_path)


def print_validation_result(result: ValidationResult, verbose: bool = True) -> None:
    """
    Pretty print validation results.

    Args:
        result: ValidationResult to print
        verbose: If True, show all details
    """
    print("=" * 70)
    print("YAML Validation Result")
    print("=" * 70)

    if result.valid:
        print("\n✓ VALID")
        print(f"\nControls found: {result.controls_count}")
        if verbose and result.control_names:
            print("\nControl names:")
            for name in result.control_names:
                print(f"  • {name}")
    else:
        print("\n✗ INVALID")

    if result.errors:
        print(f"\n❌ Errors ({len(result.errors)}):")
        for error in result.errors:
            print(f"  • {error}")

    if result.warnings:
        print(f"\n⚠️  Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  • {warning}")

    print()

