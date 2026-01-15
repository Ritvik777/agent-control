"""Control definition models for agent protection."""

from typing import Any, Literal, Self

import re2
from pydantic import Field, field_validator, model_validator

from .base import BaseModel


class ControlSelector(BaseModel):
    """Selects data from payload and optionally scopes applicability by tool.

    - path: which slice of the payload to feed into the evaluator. Optional, defaults to "*"
      meaning the entire payload object (ToolCall or LlmCall).
    - tool_names/tool_name_regex: optional applicability filters for ToolCall payloads.
    """

    path: str | None = Field(
        default="*",
        description=(
            "Path to data using dot notation. "
            "Examples: 'input', 'output', 'arguments.query', 'context.user_id', 'tool_name', '*'"
        ),
    )
    tool_names: list[str] | None = Field(
        default=None,
        description="Exact tool names this control applies to (ToolCall only)",
    )
    tool_name_regex: str | None = Field(
        default=None,
        description="RE2 pattern matched with search() against tool_name (ToolCall only)",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str | None) -> str:
        """Validate path; None becomes '*', empty string raises."""
        if v is None:
            return "*"
        if v == "":
            raise ValueError(
                "Path cannot be empty string. Use '*' for root or omit the field."
            )

        # Valid root fields
        valid_roots = {"input", "output", "arguments", "tool_name", "context", "*"}
        root = v.split(".")[0]

        if root not in valid_roots:
            raise ValueError(
                f"Invalid path root '{root}'. "
                f"Must be one of: {', '.join(sorted(valid_roots))}"
            )
        return v

    @field_validator("tool_names")
    @classmethod
    def validate_tool_names(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError(
                "tool_names cannot be an empty list. Use None/omit the field to apply to all tools."
            )
        if any((not isinstance(x, str) or not x) for x in v):
            raise ValueError("tool_names must be a list of non-empty strings")
        return v

    @field_validator("tool_name_regex")
    @classmethod
    def validate_tool_name_regex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            re2.compile(v)
        except re2.error as e:
            raise ValueError(f"Invalid tool_name_regex: {e}") from e
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"path": "output"},
                {"path": "arguments.query"},
                {"path": "context.user_id"},
                {"path": "input"},
                {"path": "*"},
                {"path": "arguments.dest", "tool_names": ["copy_file", "aws_cli"]},
                {"path": "output", "tool_name_regex": "^db_.*"},
            ]
        }
    }


# =============================================================================
# Plugin Config Models (used by plugin implementations)
# =============================================================================


class RegexConfig(BaseModel):
    """Configuration for regex plugin."""

    pattern: str = Field(..., description="Regular expression pattern")
    flags: list[str] | None = Field(default=None, description="Regex flags")

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate that the pattern is a valid regex."""
        try:
            re2.compile(v)
        except re2.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e
        return v


class ListConfig(BaseModel):
    """Configuration for list plugin."""

    values: list[str | int | float] = Field(
        ..., description="List of values to match against"
    )
    logic: Literal["any", "all"] = Field(
        "any", description="Matching logic: any item matches vs all items match"
    )
    match_on: Literal["match", "no_match"] = Field(
        "match", description="Trigger rule on match or no match"
    )
    match_mode: Literal["exact", "contains"] = Field(
        "exact",
        description="'exact' for full string match, 'contains' for keyword/substring match",
    )
    case_sensitive: bool = Field(False, description="Whether matching is case sensitive")


class JSONControlEvaluatorPluginConfig(BaseModel):
    """Configuration for JSON validation plugin.

    Multiple validation checks can be combined. Checks are evaluated in this order (fail-fast):
    1. JSON syntax/validity (always - ensures data is valid JSON)
    2. JSON Schema validation (if schema provided) - comprehensive structure validation
    3. Required fields check (if required_fields provided) - ensures critical fields exist
    4. Type checking (if field_types provided) - validates field types are correct
    5. Field constraints (if field_constraints provided) - validates ranges, enums, string length
    6. Pattern matching (if field_patterns provided) - validates field values match patterns

    This order makes sense because:
    - Check syntax first (can't do anything with invalid JSON)
    - Check schema next (comprehensive structural validation)
    - Check required fields (fail fast if missing critical fields)
    - Check types (verify data types before checking constraints)
    - Check constraints (validate value ranges/enums after type is confirmed)
    - Check patterns last (most specific regex validation)
    """

    # Validation Options (all optional, can be combined)
    json_schema: dict[str, Any] | None = Field(
        default=None, description="JSON Schema specification (Draft 7 or later)"
    )

    required_fields: list[str] | None = Field(
        default=None,
        description="List of field paths that must be present (dot notation)",
    )

    field_types: dict[str, str] | None = Field(
        default=None,
        description=(
            "Map of field paths to expected JSON types "
            "(string, number, integer, boolean, array, object, null)"
        ),
    )

    field_constraints: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Field-level constraints: numeric ranges (min/max), enums, string length",
    )

    field_patterns: dict[str, str | dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Map of field paths to RE2 regex patterns. "
            "Can be string (pattern only) or dict with 'pattern' and optional 'flags'"
        ),
    )

    # Validation Behavior
    allow_extra_fields: bool = Field(
        default=True,
        description="If False, fail if extra fields exist beyond those specified in field_types",
    )

    allow_null_required: bool = Field(
        default=False,
        description=(
            "If True, required fields can be present but null. "
            "If False, null is treated as missing"
        ),
    )

    pattern_match_logic: Literal["all", "any"] = Field(
        default="all",
        description=(
            "For field_patterns: 'all' requires all patterns to match, "
            "'any' requires at least one"
        ),
    )

    case_sensitive_enums: bool = Field(
        default=True,
        description="If False, enum value matching is case-insensitive",
    )

    # Error Handling
    allow_invalid_json: bool = Field(
        default=False,
        description=(
            "If True, treat invalid JSON as non-match and allow. "
            "If False, block invalid JSON"
        ),
    )

    @field_validator("json_schema")
    @classmethod
    def validate_json_schema(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Ensure the JSON schema itself is valid."""
        if v is None:
            return v
        from jsonschema import Draft7Validator

        Draft7Validator.check_schema(v)
        return v

    @field_validator("field_types")
    @classmethod
    def validate_type_names(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Ensure type names are valid JSON types."""
        if v is None:
            return v
        valid_types = {
            "string",
            "number",
            "integer",
            "boolean",
            "array",
            "object",
            "null",
        }
        for path, type_name in v.items():
            if type_name not in valid_types:
                raise ValueError(f"Invalid type '{type_name}' for field '{path}'")
        return v

    @field_validator("field_patterns")
    @classmethod
    def validate_patterns(
        cls, v: dict[str, str | dict[str, Any]] | None
    ) -> dict[str, str | dict[str, Any]] | None:
        """Validate all regex patterns compile."""
        if v is None:
            return v

        for path, pattern_config in v.items():
            # Support both string (simple) and dict (with flags) formats
            if isinstance(pattern_config, str):
                pattern = pattern_config
                flags = None
            elif isinstance(pattern_config, dict):
                if "pattern" not in pattern_config:
                    raise ValueError(
                        f"Pattern config for field '{path}' must have 'pattern' key"
                    )
                pattern = pattern_config["pattern"]
                flags = pattern_config.get("flags")

                # Validate flags if provided
                if flags is not None:
                    if not isinstance(flags, list):
                        raise ValueError(f"Flags for field '{path}' must be a list")
                    valid_flags = {"IGNORECASE"}
                    for flag in flags:
                        if flag not in valid_flags:
                            raise ValueError(
                                f"Invalid flag '{flag}' for field '{path}'. "
                                f"Valid flags: {valid_flags}"
                            )
            else:
                raise ValueError(
                    f"Pattern for field '{path}' must be string or dict"
                )

            # Validate pattern compiles
            try:
                re2.compile(pattern)
            except re2.error as e:
                raise ValueError(f"Invalid regex for field '{path}': {e}") from e

        return v

    @field_validator("field_constraints")
    @classmethod
    def validate_constraints(
        cls, v: dict[str, dict[str, Any]] | None
    ) -> dict[str, dict[str, Any]] | None:
        """Validate constraint definitions."""
        if v is None:
            return v

        for field_path, constraints in v.items():
            # Must have at least one constraint type
            valid_keys = {"type", "min", "max", "enum", "min_length", "max_length"}
            if not any(k in constraints for k in valid_keys):
                raise ValueError(
                    f"Constraint for '{field_path}' must specify at least one constraint"
                )

            # Validate numeric constraints
            if "min" in constraints or "max" in constraints:
                if "type" in constraints and constraints["type"] not in (
                    "number",
                    "integer",
                ):
                    raise ValueError(
                        f"min/max constraints require type 'number' or 'integer' for '{field_path}'"
                    )

            # Validate enum
            if "enum" in constraints:
                if (
                    not isinstance(constraints["enum"], list)
                    or len(constraints["enum"]) == 0
                ):
                    raise ValueError(
                        f"enum constraint must be a non-empty list for '{field_path}'"
                    )

            # Validate string length
            if "min_length" in constraints or "max_length" in constraints:
                if "min_length" in constraints and not isinstance(
                    constraints["min_length"], int
                ):
                    raise ValueError(
                        f"min_length must be an integer for '{field_path}'"
                    )
                if "max_length" in constraints and not isinstance(
                    constraints["max_length"], int
                ):
                    raise ValueError(
                        f"max_length must be an integer for '{field_path}'"
                    )

        return v

    @model_validator(mode="after")
    def validate_has_checks(self) -> Self:
        """Ensure at least one validation check is configured."""
        if not any(
            [
                self.json_schema,
                self.field_types,
                self.required_fields,
                self.field_constraints,
                self.field_patterns,
            ]
        ):
            raise ValueError(
                "At least one validation check must be configured: "
                "json_schema, field_types, required_fields, field_constraints, or field_patterns"
            )
        return self


# =============================================================================
# Unified Evaluator Config (used in API)
# =============================================================================


class EvaluatorConfig(BaseModel):
    """Evaluator configuration. See GET /plugins for available plugins and schemas.

    Plugin reference formats:
    - Built-in: "regex", "list"
    - Agent-scoped: "my-agent:my-evaluator" (validated in endpoint, not here)
    """

    plugin: str = Field(
        ...,
        description="Plugin name or agent-scoped reference (agent:evaluator)",
        examples=["regex", "list", "my-agent:pii-detector"],
    )
    config: dict[str, Any] = Field(
        ...,
        description="Plugin-specific configuration",
        examples=[
            {"pattern": r"\d{3}-\d{2}-\d{4}"},
            {"values": ["admin"], "logic": "any"},
        ],
    )

    @model_validator(mode="after")
    def validate_plugin_config(self) -> Self:
        """Validate config against plugin's schema if plugin is registered.

        Agent-scoped evaluators (format: agent:evaluator) are validated in the
        endpoint where we have database access to look up the agent's schema.
        """
        # Agent-scoped evaluators: defer validation to endpoint (needs DB access)
        if ":" in self.plugin:
            return self

        # Built-in plugins: validate config against plugin's config_model
        from .plugin import get_plugin

        plugin_cls = get_plugin(self.plugin)
        if plugin_cls:
            plugin_cls.config_model(**self.config)
        # If plugin not found, allow it (might be a server-side registered plugin)
        return self


class ControlAction(BaseModel):
    """What to do when control matches."""

    decision: Literal["allow", "deny", "warn", "log"] = Field(
        ..., description="Action to take when control is triggered"
    )


class ControlDefinition(BaseModel):
    """A control definition to evaluate agent interactions.

    This model contains only the logic and configuration.
    Identity fields (id, name) are managed by the database.
    """

    description: str | None = Field(None, description="Detailed description of the control")
    enabled: bool = Field(True, description="Whether this control is active")
    local: bool = Field(
        False,
        description=(
            "If True, this control runs locally in the SDK. "
            "If False (default), it runs on the server."
        ),
    )

    # When to apply
    applies_to: Literal["llm_call", "tool_call"] = Field(
        ..., description="Which type of interaction this control applies to"
    )
    check_stage: Literal["pre", "post"] = Field(
        ..., description="When to execute this control"
    )

    # What to check
    selector: ControlSelector = Field(..., description="What data to select from the payload")

    # How to check (unified plugin-based evaluator)
    evaluator: EvaluatorConfig = Field(..., description="How to evaluate the selected data")

    # What to do
    action: ControlAction = Field(..., description="What action to take when control matches")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Block outputs containing US Social Security Numbers",
                    "enabled": True,
                    "applies_to": "llm_call",
                    "check_stage": "post",
                    "selector": {"path": "output"},
                    "evaluator": {
                        "plugin": "regex",
                        "config": {
                            "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
                        },
                    },
                    "action": {
                        "decision": "deny",
                    },
                    "tags": ["pii", "compliance"],
                }
            ]
        }
    }


class EvaluatorResult(BaseModel):
    """Result from a control evaluator.

    When a plugin encounters an internal error (exception, missing plugin, etc.),
    the system fails open (matched=False) but sets the `error` field to indicate
    the evaluation did not complete successfully. Callers should check `error`
    to detect partial failures.
    """

    matched: bool = Field(..., description="Whether the pattern matched")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the evaluation"
    )
    message: str | None = Field(default=None, description="Explanation of the result")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional result metadata")
    error: str | None = Field(
        default=None,
        description=(
            "Error message if evaluation failed internally. "
            "When set, matched=False is due to error, not actual evaluation."
        ),
    )


class ControlMatch(BaseModel):
    """Represents a control match (could be allow, deny, warn, or log)."""

    control_id: int = Field(..., description="Database ID of the control that matched")
    control_name: str = Field(..., description="Name of the control that matched")
    action: Literal["allow", "deny", "warn", "log"] = Field(
        ..., description="Action to take for this match"
    )
    result: EvaluatorResult = Field(
        ..., description="Evaluator result (confidence, message, metadata)"
    )


