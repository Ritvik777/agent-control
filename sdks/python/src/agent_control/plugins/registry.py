"""Plugin registry for discovering and managing plugins."""

import logging
import os
from typing import Any

from .base import PluginEvaluator

logger = logging.getLogger(__name__)

# Global plugin registry
_PLUGIN_REGISTRY: dict[str, type[PluginEvaluator]] = {}
_DISCOVERY_COMPLETE = False


def register_plugin(plugin_class: type[PluginEvaluator]) -> None:
    """Register a plugin by its metadata name.

    Args:
        plugin_class: Plugin class to register

    Raises:
        ValueError: If plugin name already registered
    """
    name = plugin_class.metadata.name

    if name in _PLUGIN_REGISTRY:
        raise ValueError(f"Plugin '{name}' is already registered")

    _PLUGIN_REGISTRY[name] = plugin_class
    logger.debug(f"Registered plugin: {name} v{plugin_class.metadata.version}")


def get_plugin(plugin_name: str) -> type[PluginEvaluator] | None:
    """Get a plugin class by name.

    Triggers lazy discovery on first call if not already done.

    Args:
        plugin_name: Name of the plugin to retrieve

    Returns:
        Plugin class or None if not found
    """
    _ensure_discovered()
    return _PLUGIN_REGISTRY.get(plugin_name)


def list_plugins() -> dict[str, dict[str, Any]]:
    """List all registered plugins with their metadata.

    Triggers lazy discovery if not already done.

    Returns:
        Dictionary mapping plugin names to their metadata
    """
    _ensure_discovered()
    return {
        name: {
            "name": plugin_class.metadata.name,
            "version": plugin_class.metadata.version,
            "description": plugin_class.metadata.description,
            "requires_api_key": plugin_class.metadata.requires_api_key,
            "timeout_ms": plugin_class.metadata.timeout_ms,
            "config_schema": plugin_class.metadata.config_schema,
        }
        for name, plugin_class in _PLUGIN_REGISTRY.items()
    }


def _ensure_discovered() -> None:
    """Ensure plugin discovery has been run (lazy discovery)."""
    global _DISCOVERY_COMPLETE
    if not _DISCOVERY_COMPLETE:
        discover_plugins()


def discover_plugins() -> None:
    """Discover and register all available plugins.

    This function:
    1. Registers built-in plugins (none yet, but could add)
    2. Attempts to load optional first-party plugins (Luna-2)
    3. Discovers third-party plugins via entry points

    Can be disabled by setting AGENT_CONTROL_DISABLE_PLUGIN_DISCOVERY=1
    """
    global _DISCOVERY_COMPLETE

    # Check if discovery is disabled via env var
    if os.environ.get("AGENT_CONTROL_DISABLE_PLUGIN_DISCOVERY", "").lower() in ("1", "true"):
        logger.debug("Plugin discovery disabled via environment variable")
        _DISCOVERY_COMPLETE = True
        return

    # Try to load optional first-party plugins
    _load_luna2_plugin()

    # Try to load third-party plugins via entry points
    _load_entry_point_plugins()

    _DISCOVERY_COMPLETE = True


def _load_luna2_plugin() -> None:
    """Attempt to load the Luna-2 plugin from agent_control_plugins."""
    try:
        from agent_control_plugins.luna2 import LUNA2_AVAILABLE, Luna2Plugin  # type: ignore

        if not LUNA2_AVAILABLE:
            logger.debug("Luna-2 plugin: galileo SDK not installed")
            return

        # Only register if not already registered
        if "galileo-luna2" not in _PLUGIN_REGISTRY:
            register_plugin(Luna2Plugin)
            logger.debug("Luna-2 plugin loaded successfully")
    except ImportError as e:
        logger.debug(f"Luna-2 plugin not available: {e}")
    except ValueError:
        # Already registered
        pass
    except Exception as e:
        logger.warning(f"Failed to load Luna-2 plugin: {e}")


def _load_entry_point_plugins() -> None:
    """Load third-party plugins via entry points."""
    try:
        import importlib.metadata

        for entry_point in importlib.metadata.entry_points(group="agent_control.plugins"):
            try:
                plugin_class = entry_point.load()
                if plugin_class.metadata.name not in _PLUGIN_REGISTRY:
                    register_plugin(plugin_class)
                    logger.debug(f"Loaded third-party plugin: {entry_point.name}")
            except ValueError:
                # Already registered
                pass
            except Exception as e:
                logger.warning(f"Failed to load plugin {entry_point.name}: {e}")
    except Exception as e:
        logger.debug(f"Entry point discovery not available: {e}")
