from typing import Any

from pydantic import Field

from .base import BaseModel
from .policy import Rule
from .protection import Agent, AgentTool
from .rules import ProtectionRule


class CreatePolicyRequest(BaseModel):
    name: str = Field(description="Unique policy name")


class CreateControlRequest(BaseModel):
    name: str = Field(description="Unique control name")


class CreateRuleRequest(BaseModel):
    name: str = Field(description="Unique rule name")


class InitAgentRequest(BaseModel):
    """Request to initialize or update an agent registration."""
    agent: Agent = Field(
        ..., description="Agent metadata including ID, name, and version"
    )
    tools: list[AgentTool] = Field(
        default_factory=list, description="List of tools available to the agent"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent": {
                        "agent_id": "550e8400-e29b-41d4-a716-446655440000",
                        "agent_name": "customer-service-bot",
                        "agent_description": "Handles customer inquiries",
                        "agent_version": "1.0.0"
                    },
                    "tools": [
                        {
                            "tool_name": "search_kb",
                            "arguments": {"query": {"type": "string"}},
                            "output_schema": {"results": {"type": "array"}}
                        }
                    ]
                }
            ]
        }
    }

class InitAgentResponse(BaseModel):
    """Response from agent initialization."""
    created: bool = Field(
        ..., description="True if agent was newly created, False if updated"
    )
    rules: list[Rule] = Field(
        default_factory=list,
        description="Active protection rules for the agent (if policy assigned)",
    )


class GetAgentResponse(BaseModel):
    """Response containing agent details and registered tools."""
    agent: Agent = Field(..., description="Agent metadata")
    tools: list[AgentTool] = Field(..., description="Tools registered with this agent")


class CreatePolicyResponse(BaseModel):
    policy_id: int = Field(description="Identifier of the created policy")


class SetPolicyResponse(BaseModel):
    success: bool = Field(description="Whether the policy was successfully assigned")
    old_policy_id: int | None = Field(
        default=None, description="Previous policy id if one was replaced"
    )


class GetPolicyResponse(BaseModel):
    policy_id: int = Field(description="Identifier of the policy assigned to the agent")


class DeletePolicyResponse(BaseModel):
    success: bool = Field(description="Whether the policy was successfully removed")


class AgentRulesResponse(BaseModel):
    rules: list[Rule] = Field(description="List of rules associated with the agent via its policy")


class CreateControlResponse(BaseModel):
    control_id: int = Field(description="Identifier of the created control")


class CreateRuleResponse(BaseModel):
    rule_id: int = Field(description="Identifier of the created rule")


class GetPolicyControlsResponse(BaseModel):
    control_ids: list[int] = Field(description="List of control ids associated with the policy")


class GetControlRulesResponse(BaseModel):
    rule_ids: list[int] = Field(description="List of rule ids associated with the control")


class AssocResponse(BaseModel):
    success: bool = Field(description="Whether the association change succeeded")


class GetRuleDataResponse(BaseModel):
    data: ProtectionRule | dict[str, Any] = Field(description="Rule data payload")


class SetRuleDataRequest(BaseModel):
    """Request to update rule configuration data."""
    data: ProtectionRule = Field(
        ...,
        description="Rule configuration data (replaces existing)",
    )


class SetRuleDataResponse(BaseModel):
    success: bool = Field(description="Whether the rule data was updated")
