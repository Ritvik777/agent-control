"""Plugin discovery via entry points."""

from __future__ import annotations

import logging
import threading
from importlib.metadata import entry_points
from typing import Any

from agent_control_models import (
    PluginEvaluator,
    get_all_plugins,
    get_plugin,
    register_plugin,
)

logger = logging.getLogger(__name__)

_DISCOVERY_COMPLETE = False
_DISCOVERY_LOCK = threading.Lock()


def discover_plugins() -> int:
    """Discover and register plugins via entry points.

    All plugins (built-in and third-party) are discovered via the
    'agent_control.plugins' entry point group. Plugins are only registered
    if their `is_available()` method returns True.

    Safe to call multiple times - only runs discovery once.
    Thread-safe via lock.

    Returns:
        Number of plugins discovered
    """
    global _DISCOVERY_COMPLETE

    # Fast path without lock
    if _DISCOVERY_COMPLETE:
        return 0

    with _DISCOVERY_LOCK:
        # Double-check after acquiring lock
        if _DISCOVERY_COMPLETE:
            return 0

        discovered = 0

        # Discover ALL plugins (built-in and third-party) via entry points.
        # Only register plugins where is_available() returns True.
        try:
            eps = entry_points(group="agent_control.plugins")
            for ep in eps:
                try:
                    plugin_class = ep.load()
                    name = plugin_class.metadata.name

                    # Skip if already registered
                    if get_plugin(name) is not None:
                        continue

                    # Check if plugin dependencies are satisfied
                    if not plugin_class.is_available():
                        logger.debug(f"Plugin '{name}' not available, skipping")
                        continue

                    register_plugin(plugin_class)
                    logger.debug(f"Registered plugin: {name}")
                    discovered += 1
                except Exception as e:
                    logger.warning(f"Failed to load plugin '{ep.name}': {e}")
        except Exception as e:
            logger.debug(f"Entry point discovery not available: {e}")

        _DISCOVERY_COMPLETE = True
        logger.debug(f"Plugin discovery complete: {discovered} new plugins")
        return discovered


def ensure_plugins_discovered() -> None:
    """Ensure plugin discovery has run. Call this before using plugins."""
    if not _DISCOVERY_COMPLETE:
        discover_plugins()


def reset_discovery() -> None:
    """Reset discovery state. Useful for testing."""
    global _DISCOVERY_COMPLETE
    with _DISCOVERY_LOCK:
        _DISCOVERY_COMPLETE = False


# =============================================================================
# Public plugin API
# =============================================================================


def list_plugins() -> dict[str, type[PluginEvaluator[Any]]]:
    """List all registered plugins.

    This function ensures plugin discovery has run before returning results.

    Returns:
        Dictionary mapping plugin names to plugin classes
    """
    ensure_plugins_discovered()
    return get_all_plugins()
