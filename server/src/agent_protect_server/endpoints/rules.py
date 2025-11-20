
from agent_protect_models.server import (
    CreateRuleRequest,
    CreateRuleResponse,
    GetRuleDataResponse,
    SetRuleDataRequest,
    SetRuleDataResponse,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db
from ..logging_utils import get_logger
from ..models import Rule

router = APIRouter(prefix="/rules", tags=["rules"])

_logger = get_logger(__name__)


@router.put(
    "",
    response_model=CreateRuleResponse,
    summary="Create a new rule",
    response_description="Created rule ID",
)
async def create_rule(
    request: CreateRuleRequest, db: AsyncSession = Depends(get_async_db)
) -> CreateRuleResponse:
    """
    Create a new rule with a unique name and empty data.

    Rules define protection logic and can be added to controls.
    Use the PUT /{rule_id}/data endpoint to set rule configuration.

    Args:
        request: Rule creation request with unique name
        db: Database session (injected)

    Returns:
        CreateRuleResponse with the new rule's ID

    Raises:
        HTTPException 409: Rule with this name already exists
        HTTPException 500: Database error during creation
    """
    # Uniqueness check
    existing = await db.execute(select(Rule.id).where(Rule.name == request.name))
    if existing.first() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Rule with name '{request.name}' already exists",
        )

    rule = Rule(name=request.name, data={})
    db.add(rule)
    try:
        await db.commit()
        await db.refresh(rule)
    except Exception:
        await db.rollback()
        _logger.error(
            f"Failed to create rule '{request.name}'",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create rule '{request.name}': database error",
        )
    return CreateRuleResponse(rule_id=rule.id)


@router.get(
    "/{rule_id}/data",
    response_model=GetRuleDataResponse,
    summary="Get rule configuration data",
    response_description="Rule data payload",
)
async def get_rule_data(
    rule_id: int, db: AsyncSession = Depends(get_async_db)
) -> GetRuleDataResponse:
    """
    Retrieve the configuration data for a rule.

    Rule data is a free-form JSONB field that can contain any structure
    needed for your protection logic (e.g., patterns, thresholds, actions).

    Args:
        rule_id: ID of the rule
        db: Database session (injected)

    Returns:
        GetRuleDataResponse with rule data dictionary

    Raises:
        HTTPException 404: Rule not found
    """
    res = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = res.scalars().first()
    if rule is None:
        raise HTTPException(
            status_code=404, detail=f"Rule with ID '{rule_id}' not found"
        )
    return GetRuleDataResponse(data=rule.data)


@router.put(
    "/{rule_id}/data",
    response_model=SetRuleDataResponse,
    summary="Update rule configuration data",
    response_description="Success confirmation",
)
async def set_rule_data(
    rule_id: int,
    request: SetRuleDataRequest,
    db: AsyncSession = Depends(get_async_db),
) -> SetRuleDataResponse:
    """
    Update the configuration data for a rule.

    This replaces the entire data payload. The data structure is application-defined.

    Example structures:
    - Content filter: {"type": "filter", "pattern": "regex", "action": "block"}
    - Rate limit: {"type": "rate_limit", "max_requests": 100, "window_seconds": 60}

    Args:
        rule_id: ID of the rule
        request: New rule data (replaces existing)
        db: Database session (injected)

    Returns:
        SetRuleDataResponse with success flag

    Raises:
        HTTPException 404: Rule not found
        HTTPException 500: Database error during update
    """
    res = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = res.scalars().first()
    if rule is None:
        raise HTTPException(
            status_code=404, detail=f"Rule with ID '{rule_id}' not found"
        )
    rule.data = request.data.model_dump(mode="json")
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        _logger.error(
            f"Failed to update data for rule '{rule.name}' ({rule_id})",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update data for rule '{rule.name}': database error",
        )
    return SetRuleDataResponse(success=True)
