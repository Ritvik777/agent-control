from agent_control_models import ControlDefinition, get_plugin
from agent_control_models.server import (
    CreateControlRequest,
    CreateControlResponse,
    GetControlDataResponse,
    GetControlResponse,
    SetControlDataRequest,
    SetControlDataResponse,
)
from fastapi import APIRouter, Depends, HTTPException
from jsonschema_rs import ValidationError as JSONSchemaValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db
from ..logging_utils import get_logger
from ..models import Agent, AgentData, Control
from ..services.evaluator_utils import parse_evaluator_ref, validate_config_against_schema

router = APIRouter(prefix="/controls", tags=["controls"])

_logger = get_logger(__name__)


@router.put(
    "",
    response_model=CreateControlResponse,
    summary="Create a new control",
    response_description="Created control ID",
)
async def create_control(
    request: CreateControlRequest, db: AsyncSession = Depends(get_async_db)
) -> CreateControlResponse:
    """
    Create a new control with a unique name and empty data.

    Controls define protection logic and can be added to control sets.
    Use the PUT /{control_id}/data endpoint to set control configuration.

    Args:
        request: Control creation request with unique name
        db: Database session (injected)

    Returns:
        CreateControlResponse with the new control's ID

    Raises:
        HTTPException 409: Control with this name already exists
        HTTPException 500: Database error during creation
    """
    # Uniqueness check
    existing = await db.execute(select(Control.id).where(Control.name == request.name))
    if existing.first() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Control with name '{request.name}' already exists",
        )

    control = Control(name=request.name, data={})
    db.add(control)
    try:
        await db.commit()
        await db.refresh(control)
    except Exception:
        await db.rollback()
        _logger.error(
            f"Failed to create control '{request.name}'",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create control '{request.name}': database error",
        )
    return CreateControlResponse(control_id=control.id)


@router.get(
    "/{control_id}",
    response_model=GetControlResponse,
    summary="Get control details",
    response_description="Control metadata and configuration",
)
async def get_control(
    control_id: int, db: AsyncSession = Depends(get_async_db)
) -> GetControlResponse:
    """
    Retrieve a control by ID including its name and configuration data.

    Args:
        control_id: ID of the control
        db: Database session (injected)

    Returns:
        GetControlResponse with control id, name, and data

    Raises:
        HTTPException 404: Control not found
    """
    res = await db.execute(select(Control).where(Control.id == control_id))
    control = res.scalars().first()
    if control is None:
        raise HTTPException(
            status_code=404, detail=f"Control with ID '{control_id}' not found"
        )

    # Parse data if present and non-empty
    control_data: ControlDefinition | None = None
    if control.data:
        try:
            control_data = ControlDefinition.model_validate(control.data)
        except ValidationError as e:
            # Data exists but is corrupted - log and return None
            _logger.warning(
                "Control '%s' (id=%s) has corrupted data that failed validation: %s",
                control.name,
                control_id,
                str(e),
            )
            control_data = None

    return GetControlResponse(
        id=control.id,
        name=control.name,
        data=control_data,
    )


@router.get(
    "/{control_id}/data",
    response_model=GetControlDataResponse,
    summary="Get control configuration data",
    response_description="Control data payload",
)
async def get_control_data(
    control_id: int, db: AsyncSession = Depends(get_async_db)
) -> GetControlDataResponse:
    """
    Retrieve the configuration data for a control.

    Control data is a JSONB field that must follow the ControlDefinition schema.

    Args:
        control_id: ID of the control
        db: Database session (injected)

    Returns:
        GetControlDataResponse with validated ControlDefinition

    Raises:
        HTTPException 404: Control not found
        HTTPException 422: Control data is corrupted
    """
    res = await db.execute(select(Control).where(Control.id == control_id))
    control = res.scalars().first()
    if control is None:
        raise HTTPException(
            status_code=404, detail=f"Control with ID '{control_id}' not found"
        )
    try:
        control_def = ControlDefinition.model_validate(control.data)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Control '{control.name}' has corrupted data: {e}",
        )
    return GetControlDataResponse(data=control_def)


@router.put(
    "/{control_id}/data",
    response_model=SetControlDataResponse,
    summary="Update control configuration data",
    response_description="Success confirmation",
)
async def set_control_data(
    control_id: int,
    request: SetControlDataRequest,
    db: AsyncSession = Depends(get_async_db),
) -> SetControlDataResponse:
    """
    Update the configuration data for a control.

    This replaces the entire data payload. The data is validated against
    the ControlDefinition schema.

    Args:
        control_id: ID of the control
        request: New control data (replaces existing)
        db: Database session (injected)

    Returns:
        SetControlDataResponse with success flag

    Raises:
        HTTPException 404: Control not found
        HTTPException 500: Database error during update
    """
    res = await db.execute(select(Control).where(Control.id == control_id))
    control = res.scalars().first()
    if control is None:
        raise HTTPException(
            status_code=404, detail=f"Control with ID '{control_id}' not found"
        )

    # Validate evaluator config
    plugin_ref = request.data.evaluator.plugin
    agent_name, eval_name = parse_evaluator_ref(plugin_ref)

    if agent_name is not None:
        # Agent-scoped evaluator: validate against agent's registered schema
        agent_result = await db.execute(
            select(Agent).where(Agent.name == agent_name)
        )
        agent = agent_result.scalars().first()
        if agent is None:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' not found. "
                f"Ensure the agent exists before creating controls that reference its evaluators.",
            )

        try:
            agent_data = AgentData.model_validate(agent.data)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail=f"Agent '{agent_name}' has corrupted data.",
            )

        evaluator = next(
            (e for e in (agent_data.evaluators or []) if e.name == eval_name),
            None,
        )
        if evaluator is None:
            available = [e.name for e in (agent_data.evaluators or [])]
            raise HTTPException(
                status_code=422,
                detail=f"Evaluator '{eval_name}' is not registered with agent '{agent_name}'. "
                f"Available evaluators: {available or 'none'}. "
                f"Register it via initAgent first.",
            )

        # Validate config against evaluator's schema
        if evaluator.config_schema:
            try:
                validate_config_against_schema(
                    request.data.evaluator.config, evaluator.config_schema
                )
            except JSONSchemaValidationError as e:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Config validation failed for evaluator "
                        f"'{agent_name}:{eval_name}': {e.message}"
                    ),
                )
    else:
        # Built-in or server-side plugin: validate if registered
        plugin_cls = get_plugin(eval_name)
        if plugin_cls is not None:
            try:
                plugin_cls.config_model(**request.data.evaluator.config)
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Config validation failed for plugin '{eval_name}': {e}",
                )
        # If plugin not found, allow it - might be a server-side registered plugin
        # that will be validated at runtime

    data_json = request.data.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    # Pydantic's exclude_none doesn't propagate into nested model dicts after
    # serialization, so we re-dump the selector separately to strip null keys.
    try:
        selector_json = request.data.selector.model_dump(exclude_none=True, exclude_unset=True)  # type: ignore[attr-defined]
        selector_json = {k: v for k, v in selector_json.items() if v is not None}
        if selector_json:
            data_json["selector"] = selector_json
    except Exception:
        pass
    control.data = data_json
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        _logger.error(
            f"Failed to update data for control '{control.name}' ({control_id})",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update data for control '{control.name}': database error",
        )
    return SetControlDataResponse(success=True)
