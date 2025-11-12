"""Client for interacting with Agent Protect Server."""

from typing import Any, Dict, Optional

import httpx
from agent_protect_models import ProtectionRequest, ProtectionResult


class AgentProtectClient:
    """Client for Agent Protect Server."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        """
        Initialize the client.

        Args:
            base_url: Base URL of the server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "AgentProtectClient":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the client connection."""
        await self._client.aclose()

    async def health_check(self) -> Dict[str, str]:
        """
        Check server health.

        Returns:
            Dict containing health status and version

        Raises:
            httpx.HTTPError: If the request fails
        """
        response = await self._client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def check_protection(
        self, content: str, context: Optional[Dict[str, str]] = None
    ) -> ProtectionResult:
        """
        Check if content is safe.

        Args:
            content: Content to analyze
            context: Optional context information

        Returns:
            ProtectionResult with safety analysis

        Raises:
            httpx.HTTPError: If the request fails
        """
        # Create request using shared model
        request = ProtectionRequest(content=content, context=context)

        # Send request with JSON serialization
        response = await self._client.post(
            f"{self.base_url}/protect",
            json=request.to_dict(),
        )
        response.raise_for_status()

        # Parse response into ProtectionResult
        return ProtectionResult.from_dict(response.json())
