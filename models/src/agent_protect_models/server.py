from .base import BaseModel
from .policy import Policy
from .protection import Agent


class InitAgentRequest(BaseModel):
    agent: Agent

class InitAgentResponse(BaseModel):
    policyh: Policy
