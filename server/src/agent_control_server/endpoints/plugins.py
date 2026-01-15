"""Plugin discovery endpoints."""

from typing import Any

from agent_control_engine import list_plugins
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginInfo(BaseModel):
    """Information about a registered plugin."""

    name: str = Field(..., description="Plugin name")
    version: str = Field(..., description="Plugin version")
    description: str = Field(..., description="Plugin description")
    requires_api_key: bool = Field(..., description="Whether plugin requires API key")
    timeout_ms: int = Field(..., description="Default timeout in milliseconds")
    config_schema: dict[str, Any] = Field(..., description="JSON Schema for config")


@router.get(
    "",
    response_model=dict[str, PluginInfo],
    summary="List available plugins",
    response_description="Dictionary of plugin name to plugin info",
)
async def get_plugins() -> dict[str, PluginInfo]:
    """List all available evaluator plugins.

    Returns metadata and JSON Schema for each built-in plugin.

    Built-in plugins:
    - **regex**: Regular expression pattern matching
    - **list**: List-based value matching with flexible logic

    Custom evaluators are registered per-agent via initAgent.
    Use GET /agents/{agent_id}/evaluators to list agent-specific schemas.
    """
    plugins = list_plugins()

    return {
        name: PluginInfo(
            name=plugin_cls.metadata.name,
            version=plugin_cls.metadata.version,
            description=plugin_cls.metadata.description,
            requires_api_key=plugin_cls.metadata.requires_api_key,
            timeout_ms=plugin_cls.metadata.timeout_ms,
            config_schema=plugin_cls.config_model.model_json_schema(),
        )
        for name, plugin_cls in plugins.items()
    }
