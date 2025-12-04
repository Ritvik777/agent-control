"""Luna-2 plugin implementation."""

import logging
import os
from typing import Any

try:
    from galileo.protect import invoke_protect  # type: ignore

    LUNA2_AVAILABLE = True
except ImportError:
    LUNA2_AVAILABLE = False

from agent_control_models.controls import EvaluatorResult

from agent_control_plugins.base import PluginEvaluator, PluginMetadata

from .config import Luna2Config

logger = logging.getLogger(__name__)


class Luna2Plugin(PluginEvaluator):
    """Galileo Luna-2 runtime protection plugin.

    This plugin uses Galileo's Luna-2 enterprise model for real-time
    safety and quality checks on agent inputs and outputs.

    Supported Metrics:
        - input_toxicity, output_toxicity
        - input_sexism, output_sexism
        - prompt_injection
        - pii_detection
        - hallucination
        - tone
        - custom metrics (if configured in Galileo)

    Stage Types:
        - local: Define rules at runtime (full control)
        - central: Reference pre-defined stages managed in Galileo

    Example:
        ```python
        from agent_control_plugins.luna2 import Luna2Plugin, Luna2Config

        config = Luna2Config(
            stage_type="local",
            metric="input_toxicity",
            operator="gt",
            target_value="0.8",
            galileo_project="my-project",
        ).model_dump()

        plugin = Luna2Plugin(config)
        result = plugin.evaluate("some text")
        ```
    """

    metadata = PluginMetadata(
        name="galileo-luna2",
        version="1.0.0",
        description="Galileo Luna-2 enterprise runtime protection",
        requires_api_key=True,
        timeout_ms=10000,
        config_schema={
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Luna-2 metric to evaluate",
                    "enum": [
                        "input_toxicity",
                        "output_toxicity",
                        "input_sexism",
                        "output_sexism",
                        "prompt_injection",
                        "pii_detection",
                        "hallucination",
                        "tone",
                    ],
                },
                "operator": {
                    "type": "string",
                    "description": "Comparison operator",
                    "enum": ["gt", "lt", "gte", "lte", "eq", "contains"],
                },
                "target_value": {
                    "anyOf": [
                        {"type": "number"},
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "Target value for comparison",
                },
                "galileo_project": {
                    "type": "string",
                    "description": "Galileo project name for logging",
                },
                "stage_type": {
                    "type": "string",
                    "enum": ["local", "central"],
                    "default": "local",
                    "description": "Use local (runtime) or central (pre-defined) stage",
                },
                "stage_name": {
                    "type": "string",
                    "description": "Stage name (for central stages)",
                },
                "stage_version": {
                    "type": "integer",
                    "description": "Stage version (for central stages)",
                },
                "timeout_ms": {
                    "type": "integer",
                    "default": 10000,
                    "description": "Request timeout in milliseconds",
                },
                "on_error": {
                    "type": "string",
                    "enum": ["allow", "deny"],
                    "default": "allow",
                    "description": "Action on error (fail open or closed)",
                },
                "payload_field": {
                    "type": "string",
                    "enum": ["input", "output"],
                    "description": "Which field to populate (defaults to input)",
                },
            },
        },
    )

    # Validated config stored as Luna2Config
    _validated_config: Luna2Config

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Luna-2 plugin with configuration.

        Args:
            config: Plugin configuration dict (will be validated as Luna2Config)

        Raises:
            ImportError: If Galileo SDK not installed
            ValueError: If GALILEO_API_KEY not set or config invalid
        """
        if not LUNA2_AVAILABLE:
            raise ImportError(
                "Luna-2 plugin requires the Galileo SDK.\n"
                "Install with: pip install agent-control-plugins[luna2]\n"
                "Or: pip install galileo>=1.34.0"
            )

        # Verify API key is configured
        if not os.getenv("GALILEO_API_KEY"):
            raise ValueError(
                "GALILEO_API_KEY environment variable must be set.\n"
                "Get your API key from: https://app.galileo.ai"
            )

        # Call parent to store raw config
        super().__init__(config)

        # Validate and store typed config
        self._validated_config = Luna2Config(**config)

    def evaluate(self, data: Any) -> EvaluatorResult:
        """Evaluate data using Galileo Luna-2 (synchronous).

        Args:
            data: The data to evaluate (from selector)

        Returns:
            EvaluatorResult with matched status and metadata
        """
        if self._validated_config.stage_type == "local":
            return self._evaluate_local_stage(data)
        else:
            return self._evaluate_central_stage(data)

    def _evaluate_local_stage(self, data: Any) -> EvaluatorResult:
        """Evaluate using a local stage (runtime rulesets).

        Local stages allow you to define rules dynamically at runtime,
        giving you full control over the evaluation logic.
        """
        # Prepare payload
        payload = self._prepare_payload(data)

        # Build ruleset from config
        # Note: Galileo API expects target_value as string
        rule = {
            "metric": self._validated_config.metric,
            "operator": self._validated_config.operator,
            "target_value": str(self._validated_config.target_value or ""),
        }

        # For local stages, we provide prioritized_rulesets at runtime
        prioritized_rulesets = [
            {
                "rules": [rule],
                "action": {"type": "PASSTHROUGH"},  # We handle actions in agent-control
                "description": f"Agent-control rule: {self._validated_config.metric}",
            }
        ]

        try:
            # Call Galileo SDK (sync)
            response = invoke_protect(
                payload=payload,
                prioritized_rulesets=prioritized_rulesets,
                project_name=self._validated_config.galileo_project,
                timeout=self.get_timeout_seconds(),
                metadata=self._validated_config.metadata or {},
            )

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Luna-2 evaluation error: {e}", exc_info=True)
            return self._handle_error(e)

    def _evaluate_central_stage(self, data: Any) -> EvaluatorResult:
        """Evaluate using a central stage (pre-defined rulesets).

        Central stages are managed centrally in Galileo and can be
        updated without changing your application code.
        """
        # Prepare payload
        payload = self._prepare_payload(data)

        try:
            # For central stages, we reference the stage by name/ID
            response = invoke_protect(
                payload=payload,
                project_name=self._validated_config.galileo_project,
                stage_name=self._validated_config.stage_name,
                stage_version=self._validated_config.stage_version,
                timeout=self.get_timeout_seconds(),
                metadata=self._validated_config.metadata or {},
            )

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Luna-2 central stage error: {e}", exc_info=True)
            return self._handle_error(e)

    def _prepare_payload(self, data: Any) -> dict:
        """Prepare the Payload for Galileo protect.

        Payload has 'input' and 'output' fields based on what we're checking.
        """
        # Check explicit payload_field config
        payload_field = self._validated_config.payload_field
        if payload_field == "output":
            return {"input": "", "output": str(data) if data is not None else ""}
        elif payload_field == "input":
            return {"input": str(data) if data is not None else "", "output": ""}

        # Determine from metric name if provided
        metric = self._validated_config.metric or ""
        is_output_metric = "output" in metric

        if is_output_metric:
            return {"input": "", "output": str(data) if data is not None else ""}
        else:
            # Default to input for central stages or input metrics
            return {"input": str(data) if data is not None else "", "output": ""}

    def _parse_response(self, response: Any) -> EvaluatorResult:
        """Parse Galileo protect response into EvaluatorResult.

        Response is a Pydantic model with attributes:
            - status: ExecutionStatus enum (triggered, success, skipped, paused)
            - text: Response message
            - trace_metadata: TraceMetadata object with id, execution_time, etc.
        """
        if not response:
            return EvaluatorResult(
                matched=False,
                confidence=0.0,
                message="No response from Luna-2",
                metadata={"error": "empty_response"},
            )

        # Handle Pydantic Response model from Galileo SDK
        if hasattr(response, "status"):
            raw_status = response.status
            if hasattr(raw_status, "value"):
                raw_status = raw_status.value
            status = str(raw_status).lower()
        else:
            status_val = response.get("status", "") if isinstance(response, dict) else ""
            status = str(status_val).lower()

        triggered = status == "triggered"

        # Extract text
        if hasattr(response, "text"):
            text = response.text
        else:
            text = response.get("text", "") if isinstance(response, dict) else str(response)

        # Extract trace metadata
        trace_id = None
        execution_time = None
        received_at = None
        response_at = None

        if hasattr(response, "trace_metadata") and response.trace_metadata:
            tm = response.trace_metadata
            trace_id = str(tm.id) if hasattr(tm, "id") else None
            execution_time = tm.execution_time if hasattr(tm, "execution_time") else None
            received_at = tm.received_at if hasattr(tm, "received_at") else None
            response_at = tm.response_at if hasattr(tm, "response_at") else None
        elif isinstance(response, dict):
            trace_metadata = response.get("trace_metadata", {})
            trace_id = trace_metadata.get("id")
            execution_time = trace_metadata.get("execution_time")
            received_at = trace_metadata.get("received_at")
            response_at = trace_metadata.get("response_at")

        return EvaluatorResult(
            matched=triggered,
            confidence=1.0 if triggered else 0.0,
            message=text or f"Luna-2 check: {status}",
            metadata={
                "status": status,
                "metric": self._validated_config.metric or "unknown",
                "trace_id": trace_id,
                "execution_time_ms": execution_time,
                "received_at": received_at,
                "response_at": response_at,
            },
        )

    def _handle_error(self, error: Exception) -> EvaluatorResult:
        """Handle errors from Luna-2 evaluation."""
        error_action = self._validated_config.on_error

        return EvaluatorResult(
            matched=(error_action == "deny"),  # Fail closed if configured
            confidence=0.0,
            message=f"Luna-2 evaluation error: {str(error)}",
            metadata={
                "error": str(error),
                "error_type": type(error).__name__,
                "metric": self._validated_config.metric,
                "fallback_action": error_action,
            },
        )
