"""Unified evaluator factory using plugin registry with caching."""

import json
import logging
import os
from collections import OrderedDict
from typing import Any

from agent_control_models import EvaluatorConfig, PluginEvaluator

from .discovery import list_plugins

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_CACHE_SIZE = 100
MIN_CACHE_SIZE = 1  # Minimum to avoid infinite loop in eviction


def _parse_cache_size() -> int:
    """Parse EVALUATOR_CACHE_SIZE from env with safe fallback."""
    raw = os.environ.get("EVALUATOR_CACHE_SIZE")
    if raw is None:
        return DEFAULT_CACHE_SIZE
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            f"Invalid EVALUATOR_CACHE_SIZE '{raw}', using default {DEFAULT_CACHE_SIZE}"
        )
        return DEFAULT_CACHE_SIZE


EVALUATOR_CACHE_SIZE = max(_parse_cache_size(), MIN_CACHE_SIZE)

# LRU cache for evaluator instances: cache_key -> PluginEvaluator instance
_EVALUATOR_CACHE: OrderedDict[str, PluginEvaluator[Any]] = OrderedDict()


def _config_hash(config: dict[str, Any]) -> str:
    """Create a hashable key from config dict."""
    return json.dumps(config, sort_keys=True, default=str)


def get_evaluator(evaluator_config: EvaluatorConfig) -> PluginEvaluator[Any]:
    """Get or create a cached evaluator instance from configuration.

    Uses LRU caching to reuse evaluator instances with the same config.
    Cache key is: {plugin_name}:{config_hash}

    WARNING: Plugin instances are cached and reused across requests!
    Plugin implementations MUST be stateless - do not store mutable
    request-scoped state on the plugin instance. See PluginEvaluator
    docstring for details on safe patterns.

    Args:
        evaluator_config: The evaluator configuration with plugin name and config

    Returns:
        PluginEvaluator instance (cached or new)

    Raises:
        ValueError: If plugin not found
    """
    # Build cache key
    cache_key = f"{evaluator_config.plugin}:{_config_hash(evaluator_config.config)}"

    # Check cache
    if cache_key in _EVALUATOR_CACHE:
        # Move to end (most recently used)
        _EVALUATOR_CACHE.move_to_end(cache_key)
        logger.debug(f"Cache hit for evaluator: {evaluator_config.plugin}")
        return _EVALUATOR_CACHE[cache_key]

    # Cache miss - create new instance
    plugins = list_plugins()
    plugin_cls = plugins.get(evaluator_config.plugin)

    if plugin_cls is None:
        raise ValueError(
            f"Plugin '{evaluator_config.plugin}' not found. "
            f"Available plugins: {', '.join(plugins.keys())}"
        )

    logger.debug(f"Cache miss, creating evaluator: {evaluator_config.plugin}")
    instance = plugin_cls.from_dict(evaluator_config.config)

    # Evict oldest if cache is full
    while len(_EVALUATOR_CACHE) >= EVALUATOR_CACHE_SIZE:
        evicted_key, _ = _EVALUATOR_CACHE.popitem(last=False)
        logger.debug(f"Evicted evaluator from cache: {evicted_key}")

    # Cache the instance
    _EVALUATOR_CACHE[cache_key] = instance
    return instance


def clear_evaluator_cache() -> None:
    """Clear all cached evaluator instances. Useful for testing."""
    _EVALUATOR_CACHE.clear()
