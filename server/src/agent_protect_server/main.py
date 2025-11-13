"""Main server application entry point."""

from agent_protect_models import HealthResponse, ProtectionRequest, ProtectionResponse
from agent_protect_models.server import InitAgentRequest, InitAgentResponse
from fastapi import FastAPI

app = FastAPI(
    title="Agent Protect Server",
    description="Server component for agent protection system",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse: Current health status and version
    """
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/protect", response_model=ProtectionResponse)
async def protect(request: ProtectionRequest) -> ProtectionResponse:
    """
    Analyze content for protection.

    Args:
        request: Protection request with content to analyze

    Returns:
        ProtectionResponse: Analysis result with safety status
    """
    # TODO: Implement actual protection logic
    return ProtectionResponse(
        is_safe=True,
        confidence=0.95,
        reason="Content appears safe",
    )


@app.post("/initAgent", response_model=InitAgentResponse)
async def init_agent(request: InitAgentRequest) -> InitAgentResponse:
    raise NotImplementedError()


def run() -> None:
    """Run the server application."""
    import uvicorn

    from .config import settings

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    run()
