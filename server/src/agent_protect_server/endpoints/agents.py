from uuid import UUID

from agent_protect_models.protection import Agent as APIAgent
from agent_protect_models.protection import AgentTool
from agent_protect_models.server import GetAgentResponse, InitAgentRequest, InitAgentResponse
from fastapi import APIRouter, Depends, HTTPException
from pydantic_core._pydantic_core import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db
from ..logging_utils import get_logger
from ..models import Agent, AgentData, AgentVersionedTool

router = APIRouter(prefix="/agents")

_logger = get_logger(__name__)


@router.post("/initAgent", response_model=InitAgentResponse)
async def init_agent(
    request: InitAgentRequest, db: AsyncSession = Depends(get_async_db)
) -> InitAgentResponse:
    # Look up by name only; name is unique
    result = await db.execute(select(Agent).where(Agent.name == request.agent.agent_name))
    existing: Agent | None = result.scalars().first()

    created = False

    if existing is None:
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

    requested_uuid = request.agent.agent_id
    if existing.agent_uuid != requested_uuid:
        # UUID mismatch for the same name: return error
        raise HTTPException(
            status_code=409, detail="Agent UUID does not match existing record for name"
        )

    # Parse existing data via AgentData Pydantic model
    try:
        data_model = AgentData.model_validate(existing.data)
    except ValidationError:
        _logger.warning("Failed to parse existing agent data", exc_info=True)
        data_model = AgentData(agent_metadata={}, tools=[])

    changed = False

    incoming_by_name: dict[str, AgentTool] = {t.tool_name: t for t in request.tools}
    new_tools: list[AgentVersionedTool] = []
    seen: set[str] = set()

    for vt in data_model.tools or []:
        name = vt.tool.tool_name
        if name in incoming_by_name:
            if name not in seen:
                incoming_tool = incoming_by_name[name]
                if vt.tool.model_dump(mode="json") != incoming_tool.model_dump(mode="json"):
                    changed = True
                new_tools.append(AgentVersionedTool(version=0, tool=incoming_tool))
                seen.add(name)
        else:
            new_tools.append(vt)

    for name, t in incoming_by_name.items():
        if name not in seen and all((x.tool.tool_name != name) for x in new_tools):
            new_tools.append(AgentVersionedTool(version=0, tool=t))
            changed = True

    data_model.tools = new_tools

    if changed:
        existing.data = data_model.model_dump(mode="json")
        await db.commit()

    return InitAgentResponse(created=created, rules=[])


@router.get("/{agent_id}", response_model=GetAgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_async_db)) -> GetAgentResponse:
    result = await db.execute(select(Agent).where(Agent.agent_uuid == agent_id))
    existing: Agent | None = result.scalars().first()
    if existing is None:
        # FastAPI will turn this into a 404 automatically if we raise HTTPException,
        # but to keep dependencies minimal, return an empty not found response could be considered.
        raise HTTPException(status_code=404, detail="Agent not found")

    data_model = AgentData.model_validate(existing.data)

    tools_by_name: dict[str, AgentTool] = {}
    for vt in data_model.tools or []:
        tools_by_name[vt.tool.tool_name] = vt.tool
    latest_tools: list[AgentTool] = list(tools_by_name.values())
    agent_meta = APIAgent.model_validate(data_model.agent_metadata)
    return GetAgentResponse(agent=agent_meta, tools=latest_tools)
