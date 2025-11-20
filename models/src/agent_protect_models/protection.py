"""Protection-related models."""
from typing import Any, Literal

from pydantic import UUID4, Field

from .base import BaseModel
from .rules import RuleMatch


class Agent(BaseModel):
    """
    Agent metadata for registration and tracking.

    An agent represents an AI system that can be protected and monitored.
    Each agent has a unique ID and can have multiple tools registered with it.
    """
    agent_id: UUID4 = Field(
        ..., description="Unique identifier for the agent (UUID format)"
    )
    agent_name: str = Field(
        ..., description="Human-readable name for the agent", min_length=1
    )
    agent_description: str | None = Field(
        None, description="Optional description of the agent's purpose"
    )
    agent_created_at: str | None = Field(
        None, description="ISO 8601 timestamp when agent was created"
    )
    agent_updated_at: str | None = Field(
        None, description="ISO 8601 timestamp when agent was last updated"
    )
    agent_version: str | None = Field(
        None, description="Semantic version string (e.g. '1.0.0')"
    )
    agent_metadata: dict | None = Field(
        None, description="Free-form metadata dictionary for custom properties"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
                    "agent_name": "customer-service-bot",
                    "agent_description": "Handles customer inquiries and support tickets",
                    "agent_version": "1.0.0",
                    "agent_metadata": {"team": "support", "environment": "production"}
                }
            ]
        }
    }

# 1. agent_protect.init() ->
# Make a request to the server to register the agent
# InitProtectRequest(agent_name, agent_id, agent_description, agent_tools) ->
#       InitProtectResponse *(Policy(multiple Controls) or Errors)*
#
#
class AgentTool(BaseModel):
    """Tool schema for agent capabilities."""
    tool_name: str = Field(
        ..., description="Unique name for the tool", min_length=1
    )
    arguments: dict[str, Any] = Field(
        ..., description="JSON schema describing tool input parameters"
    )
    output_schema: dict[str, Any] = Field(
        ..., description="JSON schema describing tool output structure"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tool_name": "search_knowledge_base",
                    "arguments": {"query": {"type": "string", "description": "Search query"}},
                    "output_schema": {"results": {"type": "array", "items": {"type": "object"}}}
                }
            ]
        }
    }


class AgentContext(BaseModel):
    """Base class for agent interaction context."""
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional context (conversation history, metadata, etc.)"
    )

class ToolCall(AgentContext):
    """Represents a tool invocation by the agent."""
    tool_name: str = Field(..., description="Name of the tool called")
    arguments: dict[str, Any] = Field(..., description="Arguments passed to the tool")
    output: str | dict[str, Any] | None = Field(
        None, description="Output of the tool (None for pre-checks)"
    )


class LlmCall(AgentContext):
    """Represents an LLM interaction by the agent."""
    input: str | dict[str, Any] = Field(
        ..., description="Input content to analyze for safety (text or structured data)"
    )
    output: str | dict[str, Any] | None = Field(
        None, description="Output content to analyze for safety (None for pre-checks)"
    )

class ProtectionRequest(BaseModel):
    """
    Request model for protection analysis.

    Used to analyze agent interactions for safety violations,
    policy compliance, and protection rules.

    Attributes:
        agent_uuid: UUID of the agent making the request
        payload: Either a ToolCall or LlmCall
        check_stage: 'pre' (before execution) or 'post' (after execution)
    """
    agent_uuid: UUID4 = Field(
        ..., description="UUID of the agent making the protection request"
    )
    payload: ToolCall | LlmCall = Field(
        ..., description="Agent interaction payload - either a tool call or LLM call"
    )
    check_stage: Literal["pre", "post"] = Field(
        ..., description="Check stage: 'pre' or 'post'"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_uuid": "550e8400-e29b-41d4-a716-446655440000",
                    "payload": {
                        "input": "What is the customer's credit card number?",
                        "context": {"user_id": "user123", "session_id": "abc123"}
                    },
                    "check_stage": "pre"
                },
                {
                    "agent_uuid": "550e8400-e29b-41d4-a716-446655440000",
                    "payload": {
                        "input": "What is the customer's credit card number?",
                        "output": "I cannot share sensitive payment information.",
                        "context": {"user_id": "user123", "session_id": "abc123"}
                    },
                    "check_stage": "post"
                },
                {
                    "agent_uuid": "550e8400-e29b-41d4-a716-446655440000",
                    "payload": {
                        "tool_name": "search_database",
                        "arguments": {"query": "SELECT * FROM users"},
                        "context": {"user_id": "user123"}
                    },
                    "check_stage": "pre"
                },
                {
                    "agent_uuid": "550e8400-e29b-41d4-a716-446655440000",
                    "payload": {
                        "tool_name": "search_database",
                        "arguments": {"query": "SELECT * FROM users"},
                        "output": {"results": []},
                        "context": {"user_id": "user123"}
                    },
                    "check_stage": "post"
                }
            ]
        }
    }


class ProtectionResponse(BaseModel):
    """
    Response model from protection analysis (server-side).

    This is what the server returns. The SDK may transform this
    into a ProtectionResult for client convenience.

    Attributes:
        is_safe: Whether the content is considered safe
        confidence: Confidence score between 0.0 and 1.0
        reason: Optional explanation for the decision
        matches: List of rule matches detected (if any)
    """

    is_safe: bool = Field(..., description="Whether content is safe")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0)",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation for the decision",
    )
    matches: list[RuleMatch] | None = Field(
        default=None,
        description="List of rule matches detected (if any)",
    )


class ProtectionResult(ProtectionResponse):
    """
    Client-side result model for protection analysis.

    Extends ProtectionResponse with additional client-side convenience methods.
    This is what SDK users interact with.
    """

    def is_confident(self, threshold: float = 0.8) -> bool:
        """
        Check if the result confidence exceeds a threshold.

        Args:
            threshold: Minimum confidence threshold (default: 0.8)

        Returns:
            True if confidence >= threshold
        """
        return self.confidence >= threshold

    def __bool__(self) -> bool:
        """
        Allow boolean evaluation of result.

        Returns:
            True if content is safe, False otherwise
        """
        return self.is_safe

    def __str__(self) -> str:
        """
        String representation of the result.

        Returns:
            Human-readable description
        """
        status = "SAFE" if self.is_safe else "UNSAFE"
        conf_pct = int(self.confidence * 100)
        base = f"[{status}] Confidence: {conf_pct}%"
        if self.reason:
            return f"{base} - {self.reason}"
        return base

