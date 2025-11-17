from pydantic import Field

from .base import BaseModel
from .policy import Rule
from .protection import Agent, AgentTool


class InitAgentRequest(BaseModel):
    agent: Agent
    tools: list[AgentTool]

class InitAgentResponse(BaseModel):
    created: bool = Field(description="Whether an agent was newly registered or already existed.")
    rules: list[Rule]


class GetAgentResponse(BaseModel):
    agent: Agent
    tools: list[AgentTool]
