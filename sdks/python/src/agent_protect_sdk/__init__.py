"""Agent Protect SDK - Python SDK for interacting with Agent Protect services."""

__version__ = "0.1.0"

from agent_protect_models import ProtectionResult

from .client import AgentProtectClient

__all__ = ["AgentProtectClient", "ProtectionResult"]
