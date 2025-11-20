"""Protection analysis endpoints."""
from typing import Any

from agent_protect_engine.core import ProtectionEngine
from agent_protect_models import ProtectionRequest, ProtectionResponse, ProtectionRule
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db
from ..services.rules import list_rules_for_agent

router = APIRouter(prefix="/protect", tags=["protection"])


class RuleAdapter:
    """Adapts API Rule to Engine RuleWithIdentity protocol."""
    def __init__(self, id: int, name: str, rule_data: dict[str, Any]):
        self.id = id
        self.name = name
        # Convert dict to Pydantic model
        self.rule = ProtectionRule.model_validate(rule_data)


@router.post(
    "",
    response_model=ProtectionResponse,
    summary="Analyze content safety",
    response_description="Safety analysis result",
)
async def protect(
    request: ProtectionRequest,
    db: AsyncSession = Depends(get_async_db)
) -> ProtectionResponse:
    """
    Analyze content for safety and protection violations.
    """
    # 1. Fetch rules for the agent
    api_rules = await list_rules_for_agent(request.agent_uuid, db)

    # 2. Adapt rules for the engine
    engine_rules = []
    for r in api_rules:
        try:
            engine_rules.append(RuleAdapter(r.id, r.name, r.rule))
        except Exception:
            # TODO: Log invalid rule error
            continue

    # 3. Execute Protection Engine
    engine = ProtectionEngine(engine_rules)
    response = engine.process(request)

    return response
