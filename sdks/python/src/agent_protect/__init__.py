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
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast
from uuid import UUID

import httpx

# Import from the models package
try:
    from agent_protect_models import (
        Agent,
        LlmCall,
        ProtectionRequest,
        ProtectionResult,
        ToolCall,
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

        class ToolCall:  # runtime fallback
            def __init__(
                self,
                tool_name: str,
                arguments: dict[str, Any],
                output: str | dict[str, Any] | None = None,
                context: dict[str, Any] | None = None,
            ):
                self.tool_name = tool_name
                self.arguments = arguments
                self.output = output
                self.context = context

        class LlmCall:  # runtime fallback
            def __init__(
                self,
                input: str | dict[str, Any],
                output: str | dict[str, Any] | None = None,
                context: dict[str, Any] | None = None,
            ):
                self.input = input
                self.output = output
                self.context = context

        class ProtectionRequest:  # runtime fallback
            def __init__(
                self,
                agent_uuid: UUID,
                payload: ToolCall | LlmCall,
                check_stage: str,
            ):
                self.agent_uuid = agent_uuid
                self.payload = payload
                self.check_stage = check_stage

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
        agent_uuid: UUID,
        payload: "ToolCall | LlmCall",
        check_stage: Literal["pre", "post"],
    ) -> ProtectionResult:
        """
        Check if agent interaction is safe.

        Args:
            agent_uuid: UUID of the agent making the request
            payload: Either a ToolCall or LlmCall instance
            check_stage: 'pre' for pre-execution check, 'post' for post-execution check

        Returns:
            ProtectionResult with safety analysis

        Raises:
            httpx.HTTPError: If request fails

        Example:
            # Pre-check before LLM call
            result = await client.check_protection(
                agent_uuid=agent.agent_id,
                payload=LlmCall(input="User question", output=None),
                check_stage="pre"
            )

            # Post-check after tool execution
            result = await client.check_protection(
                agent_uuid=agent.agent_id,
                payload=ToolCall(
                    tool_name="search",
                    arguments={"query": "test"},
                    output={"results": []}
                ),
                check_stage="post"
            )
        """
        if MODELS_AVAILABLE:
            request = ProtectionRequest(
                agent_uuid=agent_uuid,
                payload=payload,
                check_stage=check_stage
            )
            request_payload = request.to_dict()
        else:
            # Fallback for when models aren't available
            payload_dict = {
                "tool_name": getattr(payload, "tool_name", None),
                "arguments": getattr(payload, "arguments", None),
                "input": getattr(payload, "input", None),
                "output": getattr(payload, "output", None),
                "context": getattr(payload, "context", None),
            }
            # Remove None values
            payload_dict = {k: v for k, v in payload_dict.items() if v is not None}

            request_payload = {
                "agent_uuid": str(agent_uuid),
                "payload": payload_dict,
                "check_stage": check_stage,
            }

        assert self._client is not None
        response = await self._client.post("/api/v1/protect", json=request_payload)
        response.raise_for_status()

        if MODELS_AVAILABLE:
            return cast(ProtectionResult, ProtectionResult.from_dict(response.json()))
        else:
            data = response.json()
            return ProtectionResult(**data)

    async def register_agent(
        self,
        agent: Agent,
        tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Register an agent with the server via /initAgent endpoint.

        Args:
            agent: Agent instance to register
            tools: Optional list of tools with their schemas

        Returns:
            InitAgentResponse with created flag and rules

        Raises:
            httpx.HTTPError: If request fails
        """
        if tools is None:
            tools = []

        if MODELS_AVAILABLE:
            agent_dict = agent.to_dict()
            # Ensure UUID is converted to string for JSON serialization
            if isinstance(agent_dict.get('agent_id'), UUID):
                agent_dict['agent_id'] = str(agent_dict['agent_id'])
            payload = {
                "agent": agent_dict,
                "tools": tools
            }
        else:
            payload = {
                "agent": {
                    "agent_id": str(agent.agent_id),
                    "agent_name": agent.agent_name,
                    "agent_description": getattr(agent, 'agent_description', None),
                    "agent_version": getattr(agent, 'agent_version', None),
                    "agent_metadata": getattr(agent, 'agent_metadata', None),
                },
                "tools": tools
            }

        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        assert self._client is not None  # Help mypy understand
        response = await self._client.post("/api/v1/agents/initAgent", json=payload)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Get agent details by ID from the server.

        Args:
            agent_id: UUID or string identifier of the agent

        Returns:
            Dictionary containing:
                - agent: Agent metadata
                - tools: List of tools registered with the agent

        Raises:
            httpx.HTTPError: If request fails or agent not found (404)

        Example:
            async with AgentProtectClient() as client:
                agent_data = await client.get_agent("550e8400-e29b-41d4-a716-446655440000")
                print(f"Agent: {agent_data['agent']['agent_name']}")
                print(f"Tools: {len(agent_data['tools'])}")
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        assert self._client is not None  # Help mypy understand
        response = await self._client.get(f"/api/v1/agents/{agent_id}")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


# ============================================================================
# Global State
# ============================================================================

# Global agent instance
_current_agent: Agent | None = None
_protect_engine = None
_client: AgentProtectClient | None = None
_server_rules: list | None = None


F = TypeVar("F", bound=Callable[..., Any])


def init(
    agent_name: str,
    agent_id: str,
    agent_description: str | None = None,
    agent_version: str | None = None,
    server_url: str | None = None,
    rules_file: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    **kwargs: object
) -> Agent:
    """
    Initialize Agent Protect with your agent's information.

    This function should be called once at the base of your agent file.
    It will:
    1. Create an Agent instance with your metadata
    2. Register with the Agent Protect server via /initAgent endpoint
    3. Fetch protection rules from the server
    4. Auto-discover and load local rules.yaml as fallback
    5. Enable the @protect decorator

    Args:
        agent_name: Human-readable name for your agent (e.g., "Customer Service Bot")
        agent_id: Unique identifier for your agent. Can be:
                 - A UUID string (e.g., "550e8400-e29b-41d4-a716-446655440000")
                 - Any string (e.g., "csbot-prod-v1") - will be converted to UUID
        agent_description: Optional description of what your agent does
        agent_version: Optional version string (e.g., "1.0.0")
        server_url: Optional server URL (defaults to AGENT_PROTECT_URL env var
                   or http://localhost:8000)
        rules_file: Optional explicit path to rules.yaml (auto-discovered if not provided)
        tools: Optional list of tools with their schemas for registration:
               [{"tool_name": "search", "arguments": {...}, "output_schema": {...}}]
        **kwargs: Additional metadata to store with the agent

    Returns:
        Agent instance with all metadata

    Example:
        import agent_protect

        agent_protect.init(
            agent_name="Customer Service Bot",
            agent_id="csbot-prod-v1",
            agent_description="Handles customer inquiries and support tickets",
            agent_version="2.1.0",
            tools=[
                {
                    "tool_name": "search_knowledge_base",
                    "arguments": {"query": {"type": "string"}},
                    "output_schema": {"results": {"type": "array"}}
                }
            ]
        )

        # Now use @protect decorator
        from agent_protect import protect

        @protect('input-check', input='message')
        async def handle(message: str):
            return message

    Environment Variables:
        AGENT_PROTECT_URL: Server URL (default: http://localhost:8000)
    """
    global _current_agent, _protect_engine, _client, _server_rules

    # Create agent instance with metadata
    # Convert agent_id to UUID (accept UUID string or generate from regular string)
    try:
        _agent_uuid = UUID(agent_id)
    except ValueError:
        # If not a valid UUID, generate one from the string deterministically
        import hashlib
        _agent_uuid = UUID(hashlib.sha1(agent_id.encode()).hexdigest()[:32])
        print(f"ℹ️  Generated UUID {_agent_uuid} from agent_id '{agent_id}'")

    _current_agent = Agent(
        agent_id=_agent_uuid,
        agent_name=agent_name,
        agent_description=agent_description,
        agent_created_at=datetime.utcnow().isoformat(),
        agent_updated_at=None,
        agent_version=agent_version,
        agent_metadata=kwargs
    )

    # Get server URL (ensure it's always a string)
    _server_url = server_url or os.getenv('AGENT_PROTECT_URL') or 'http://localhost:8000'

    # Register with server and fetch rules
    server_rules = None
    try:
        import asyncio

        async def register() -> list[dict[str, Any]] | None:
            async with AgentProtectClient(base_url=_server_url) as client:
                # Check server health first
                try:
                    health = await client.health_check()
                    print(f"✓ Connected to Agent Protect server: {_server_url}")
                    print(f"  Server status: {health.get('status', 'unknown')}")
                except Exception as e:
                    print(f"⚠️  Server not available: {e}")
                    return None

                # Register agent with tools
                try:
                    response = await client.register_agent(_current_agent, tools=tools or [])
                    created = response.get('created', False)
                    rules: list[dict[str, Any]] = response.get('rules', [])

                    if created:
                        print(f"✓ Agent registered: {agent_name} (ID: {_agent_uuid})")
                    else:
                        print(f"✓ Agent updated: {agent_name} (ID: {_agent_uuid})")

                    if tools:
                        print(f"  Registered {len(tools)} tool(s)")

                    return rules
                except Exception as e:
                    print(f"⚠️  Failed to register agent: {e}")
                    return None

        # Run registration synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        server_rules = loop.run_until_complete(register())
        loop.close()

    except Exception as e:
        print(f"⚠️  Could not connect to server: {e}")
        print("   Will use local rules if available.")

    # Store server rules globally for later use by @protect decorator
    _server_rules = server_rules
    if server_rules:
        print(f"✓ Loaded {len(server_rules)} rule(s) from server")
    else:
        print("ℹ️  No rules returned from server (use local rules.yaml or @protect decorator)")

    return _current_agent


async def get_agent(agent_id: str, server_url: str | None = None) -> dict[str, Any]:
    """
    Get agent details from the server by ID.

    Args:
        agent_id: UUID or string identifier of the agent
        server_url: Optional server URL (defaults to AGENT_PROTECT_URL env var)

    Returns:
        Dictionary containing:
            - agent: Agent metadata (agent_name, agent_id, etc.)
            - tools: List of tools registered with the agent

    Raises:
        httpx.HTTPError: If request fails or agent not found

    Example:
        import asyncio
        import agent_protect

        # Fetch agent from server
        async def main():
            agent_data = await agent_protect.get_agent("bot-123")
            print(f"Agent: {agent_data['agent']['agent_name']}")
            print(f"Tools: {len(agent_data['tools'])}")

        asyncio.run(main())

        # Or using the client directly
        async with agent_protect.AgentProtectClient() as client:
            agent_data = await client.get_agent("bot-123")
    """
    _final_server_url = server_url or os.getenv('AGENT_PROTECT_URL') or 'http://localhost:8000'

    async with AgentProtectClient(base_url=_final_server_url) as client:
        return await client.get_agent(agent_id)


def current_agent() -> Agent | None:
    """
    Get the currently initialized agent (from init()).

    Returns:
        Current Agent instance or None if not initialized

    Example:
        agent_protect.init(agent_name="My Bot", agent_id="bot-123")
        agent = agent_protect.current_agent()
        print(agent.agent_name)  # "My Bot"
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
    "current_agent",

    # Agent management
    "get_agent",

    # Decorator
    "protect",

    # Client
    "AgentProtectClient",

    # Models (if available)
    "Agent",
    "LlmCall",
    "ToolCall",
    "ProtectionRequest",
    "ProtectionResult",
    "ProtectionResponse",
    "HealthResponse",
]

__version__ = "0.1.0"

