"""Main server application entry point."""

from uuid import UUID

from agent_protect_models import HealthResponse, ProtectionRequest, ProtectionResponse
from agent_protect_models.base import BaseModel
from agent_protect_models.protection import Agent as APIAgent
from agent_protect_models.protection import AgentTool
from agent_protect_models.server import InitAgentRequest, InitAgentResponse
from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_async_db
from .models import Agent, AgentData, AgentVersionedTool

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
async def init_agent(
    request: InitAgentRequest, db: AsyncSession = Depends(get_async_db)
) -> InitAgentResponse:
    # Try to find existing agent by name and UUID; fall back to name only
    result = await db.execute(
        select(Agent).where(
            Agent.name == request.agent.agent_name,
            Agent.agent_uuid == request.agent.agent_id,
        )
    )
    existing: Agent | None = result.scalars().first()
    if existing is None:
        # Fallback by name only to avoid unique(name) conflicts on insert
        result = await db.execute(
            select(Agent).where(Agent.name == request.agent.agent_name)
        )
        existing = result.scalars().first()

    created = False

    if existing is None:
        # Create new agent
        created = True
        versioned_tools = [
            AgentVersionedTool(version=0, tool=tool) for tool in request.tools
        ]
        data_model = AgentData(
            agent_metadata=request.agent.model_dump(mode="json"),
            tools=versioned_tools,
        )
        new_agent = Agent(
            name=request.agent.agent_name,
            agent_uuid=request.agent.agent_id,
            data=data_model.model_dump(mode="json"),
        )
        db.add(new_agent)
        await db.commit()
        return InitAgentResponse(created=created, rules=[])

    # Update existing agent if needed
    # Parse existing data via AgentData Pydantic model
    try:
        data_model = AgentData.model_validate(existing.data)
    except Exception:
        data_model = AgentData(agent_metadata={}, tools=[])

    changed = False

    # Ensure stored UUID column and metadata align with request
    requested_uuid = request.agent.agent_id
    if existing.agent_uuid != requested_uuid:
        existing.agent_uuid = requested_uuid
        data_model.agent_metadata = request.agent.model_dump(mode="json")
        changed = True

    for tool in request.tools:
        name = tool.tool_name
        # collect existing versions for this tool name
        versions = [vt for vt in (data_model.tools or []) if vt.tool.tool_name == name]
        if not versions:
            data_model.tools.append(AgentVersionedTool(version=0, tool=tool))
            changed = True
            continue

        latest = max(versions, key=lambda vt: vt.version)
        same_args = (latest.tool.arguments == tool.arguments)
        same_output = (latest.tool.output_schema == tool.output_schema)
        if same_args and same_output:
            continue
        data_model.tools.append(AgentVersionedTool(version=latest.version + 1, tool=tool))
        changed = True

    if changed:
        existing.data = data_model.model_dump(mode="json")
        await db.commit()

    return InitAgentResponse(created=created, rules=[])


class GetAgentResponse(BaseModel):
    agent: APIAgent
    tools: list[AgentTool]


@app.get("/agents/{agent_id}", response_model=GetAgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_async_db)) -> GetAgentResponse:
    result = await db.execute(select(Agent).where(Agent.agent_uuid == agent_id))
    existing: Agent | None = result.scalars().first()
    if existing is None:
        # FastAPI will turn this into a 404 automatically if we raise HTTPException,
        # but to keep dependencies minimal, return an empty not found response could be considered.
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Agent not found")

    data_model = AgentData.model_validate(existing.data)

    # Build latest tools by name
    latest_by_name: dict[str, AgentVersionedTool] = {}
    for vt in data_model.tools or []:
        name = vt.tool.tool_name
        cur = latest_by_name.get(name)
        if cur is None or vt.version > cur.version:
            latest_by_name[name] = vt

    latest_tools: list[AgentTool] = [vt.tool for vt in latest_by_name.values()]
    agent_meta = APIAgent.model_validate(data_model.agent_metadata)
    return GetAgentResponse(agent=agent_meta, tools=latest_tools)


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
