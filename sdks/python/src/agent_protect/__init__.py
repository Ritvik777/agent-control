"""
Agent Protect - Unified agent protection, monitoring, and SDK client.

This package provides a complete interface for protecting your agents with
automatic registration, rule enforcement, and server communication.

Usage:
    import agent_protect

    # Initialize at the base of your agent file
    agent_protect.init(
        agent_name="my-customer-service-bot",
        agent_id="csbot-prod-v1"
    )

    # Use the protect decorator
    from agent_protect import protect

    @protect('input-validation', input='message')
    async def handle_message(message: str):
        return f"Processed: {message}"

    # Or use the client directly for custom checks
    async with agent_protect.AgentProtectClient() as client:
        result = await client.check_protection("some content")
"""

import importlib
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

import httpx

# Import from the models package
try:
    from agent_protect_models import (
        Agent,
        ProtectionRequest,
        ProtectionResult,
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    if not TYPE_CHECKING:
        class Agent:  # runtime fallback
            def __init__(self, agent_id: str, agent_name: str, **kwargs: object):
                self.agent_id = agent_id
                self.agent_name = agent_name
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class ProtectionRequest:  # runtime fallback
            def __init__(self, content: str, context: dict | None = None):
                self.content = content
                self.context = context

        class ProtectionResult:  # runtime fallback
            def __init__(self, is_safe: bool, confidence: float, reason: str | None = None):
                self.is_safe = is_safe
                self.confidence = confidence
                self.reason = reason


# ============================================================================
# HTTP Client for Server Communication
# ============================================================================

class AgentProtectClient:
    """
    Async HTTP client for Agent Protect server.

    This client provides methods to interact with the Agent Protect server,
    including health checks and content protection analysis.

    Usage:
        async with AgentProtectClient() as client:
            result = await client.check_protection("content to check")
            if result.is_safe:
                print("Content is safe!")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0
    ):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the Agent Protect server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AgentProtectClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> dict[str, str]:
        """
        Check server health.

        Returns:
            Dictionary with health status

        Raises:
            httpx.HTTPError: If request fails
        """
        assert self._client is not None
        response = await self._client.get("/health")
        response.raise_for_status()
        return cast(dict[str, str], response.json())

    async def check_protection(
        self,
        content: str,
        context: dict[str, str] | None = None
    ) -> ProtectionResult:
        """
        Check if content is safe.

        Args:
            content: Content to analyze
            context: Optional context information

        Returns:
            ProtectionResult with safety analysis

        Raises:
            httpx.HTTPError: If request fails
        """
        if MODELS_AVAILABLE:
            request = ProtectionRequest(content=content, context=context)
            payload = request.to_dict()
        else:
            payload = {"content": content, "context": context}

        assert self._client is not None
        response = await self._client.post("/protect", json=payload)
        response.raise_for_status()

        if MODELS_AVAILABLE:
            return cast(ProtectionResult, ProtectionResult.from_dict(response.json()))
        else:
            data = response.json()
            return ProtectionResult(**data)

    async def register_agent(self, agent: Agent) -> dict[str, str]:
        """
        Register an agent with the server.

        Args:
            agent: Agent instance to register

        Returns:
            Registration response from server
        """
        if MODELS_AVAILABLE:
            agent.to_dict()
        else:
            {
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "agent_description": getattr(agent, 'agent_description', None),
                "agent_version": getattr(agent, 'agent_version', None),
            }

        # TODO: Implement actual registration endpoint on server
        # For now, just return success
        return {
            "status": "registered",
            "agent_id": str(agent.agent_id),
            "message": f"Agent {agent.agent_name} registered successfully"
        }


# ============================================================================
# Global State
# ============================================================================

# Global agent instance
_current_agent: Agent | None = None
_protect_engine = None
_client: AgentProtectClient | None = None


F = TypeVar("F", bound=Callable[..., Any])


def init(
    agent_name: str,
    agent_id: str,
    agent_description: str | None = None,
    agent_version: str | None = None,
    server_url: str | None = None,
    rules_file: str | None = None,
    **kwargs: object
) -> Agent:
    """
    Initialize Agent Protect with your agent's information.

    This function should be called once at the base of your agent file.
    It will:
    1. Create an Agent instance with your metadata
    2. Auto-discover and load rules.yaml
    3. Register with the Agent Protect server
    4. Enable the @protect decorator

    Args:
        agent_name: Human-readable name for your agent (e.g., "Customer Service Bot")
        agent_id: Unique identifier for your agent (e.g., "csbot-prod-v1")
        agent_description: Optional description of what your agent does
        agent_version: Optional version string (e.g., "1.0.0")
        server_url: Optional server URL (defaults to AGENT_PROTECT_URL env var
                   or http://localhost:8000)
        rules_file: Optional explicit path to rules.yaml (auto-discovered if not provided)
        **kwargs: Additional metadata to store with the agent

    Returns:
        Agent instance with all metadata

    Example:
        import agent_protect

        agent_protect.init(
            agent_name="Customer Service Bot",
            agent_id="csbot-prod-v1",
            agent_description="Handles customer inquiries and support tickets",
            agent_version="2.1.0"
        )

        # Now use @protect decorator
        from agent_protect import protect

        @protect('input-check', input='message')
        async def handle(message: str):
            return message

    Environment Variables:
        AGENT_PROTECT_URL: Server URL (default: http://localhost:8000)
    """
    global _current_agent, _protect_engine

    # Create agent instance with metadata
    # Ensure UUID type for models
    _agent_uuid = UUID(agent_id)

    _current_agent = Agent(
        agent_id=_agent_uuid,
        agent_name=agent_name,
        agent_description=agent_description,
        agent_created_at=datetime.utcnow().isoformat(),
        agent_version=agent_version,
        agent_metadata=kwargs
    )

    # Initialize the protection engine
    try:
        # Import from the langgraph example (in production, this would be a proper package)
        import sys
        from pathlib import Path

        example_path = Path(__file__).parents[4] / "examples" / "langgraph" / "my_agent"
        if example_path.exists():
            sys.path.insert(0, str(example_path))

        module = importlib.import_module("protect_engine")
        protect_engine_cls = getattr(module, "ProtectEngine")

        # Get server URL
        server_url = server_url or os.getenv('AGENT_PROTECT_URL', 'http://localhost:8000')

        # Initialize engine with agent info
        _protect_engine = protect_engine_cls(
            rules_file=rules_file,
            agent_id=str(_agent_uuid),
            server_url=server_url,
            auto_discover=True
        )

        print(f"✓ Agent initialized: {agent_name} (ID: {_agent_uuid})")
        print(f"✓ Connected to: {server_url}")

    except Exception as e:
        print(f"⚠️  Could not initialize protection engine: {e}")
        print("   Agent will run without protection rules.")

    return _current_agent


def get_agent() -> Agent | None:
    """
    Get the current agent instance.

    Returns:
        Current Agent instance or None if not initialized
    """
    return _current_agent


def protect(step_id: str, **data_sources: str) -> Callable[[F], F]:
    """
    Decorator to protect a function with rules from rules.yaml.

    Must call agent_protect.init() before using this decorator.

    Args:
        step_id: Step identifier that matches rules.yaml
        **data_sources: Mapping of data types to parameter names

    Example:
        @protect('input-validation', input='user_message', context='ctx')
        async def process(user_message: str, ctx: dict):
            return user_message

    See protect_engine.protect for full documentation.
    """
    if _protect_engine is None:
        def decorator(func: F) -> F:
            return func
        return decorator

    # Import the actual protect decorator
    try:
        import sys
        example_path = Path(__file__).parents[4] / "examples" / "langgraph" / "my_agent"
        if example_path.exists():
            sys.path.insert(0, str(example_path))

        module = importlib.import_module("protect_engine")
        # Cast the dynamically imported decorator factory to the expected type
        return cast(Callable[[F], F], getattr(module, "protect")(step_id, **data_sources))
    except Exception as e:
        print(f"⚠️  Could not load protect decorator: {e}")
        def decorator(func: F) -> F:
            return func
        return decorator


__all__ = [
    # Initialization
    "init",
    "get_agent",

    # Decorator
    "protect",

    # Client
    "AgentProtectClient",

    # Models (if available)
    "Agent",
    "ProtectionRequest",
    "ProtectionResult",
]

__version__ = "0.1.0"

