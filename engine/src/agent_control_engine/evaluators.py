"""Control evaluator implementations."""
import logging
import re
from typing import Any

import re2
from agent_control_models import ControlEvaluator, Evaluator, EvaluatorResult
from agent_control_models.controls import ListConfig, PluginConfig, RegexConfig
from agent_control_plugins import PluginEvaluator

logger = logging.getLogger(__name__)

# Plugin registry - lazy loaded to avoid import errors when optional plugins not installed
_plugin_registry: dict[str, type[PluginEvaluator]] | None = None


def _get_plugin_registry() -> dict[str, type[PluginEvaluator]]:
    """Get or initialize the plugin registry."""
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = {}
        _discover_plugins()
    return _plugin_registry


def _discover_plugins() -> None:
    """Discover and register available plugins."""
    # Try to load Luna-2 plugin if galileo SDK is available
    try:
        from agent_control_plugins.luna2 import LUNA2_AVAILABLE, Luna2Plugin

        if LUNA2_AVAILABLE:
            _plugin_registry["galileo-luna2"] = Luna2Plugin  # type: ignore
            logger.debug("Registered Luna-2 plugin")
    except ImportError:
        logger.debug("Luna-2 plugin not available")


def get_plugin(plugin_name: str) -> type[PluginEvaluator] | None:
    """Get a plugin class by name."""
    return _get_plugin_registry().get(plugin_name)


class RegexControlEvaluator(Evaluator):
    """Evaluator using Regular Expressions (re2)."""

    def __init__(self, config: RegexConfig):
        self.pattern = config.pattern
        self.flags = config.flags

        # re2 python wrapper often has limited flag support compared to 're'
        self._regex = re2.compile(self.pattern)

    def evaluate(self, data: Any) -> EvaluatorResult:
        # Convert data to string for regex matching
        if data is None:
            return EvaluatorResult(matched=False, confidence=1.0, message="No data to match")

        text_data = str(data)

        # re2 search
        match = self._regex.search(text_data)
        is_match = match is not None

        return EvaluatorResult(
            matched=is_match,
            confidence=1.0,  # Regex is deterministic
            message=f"Regex match found: {self.pattern}" if is_match else "No match",
            metadata={"pattern": self.pattern},
        )


class ListControlEvaluator(Evaluator):
    """Evaluator for checking if values exist in a list.

    Supports two modes:
    - exact: Full string match (for allow/deny lists on discrete values)
    - contains: Word boundary match (for keyword detection in free text)
    """

    def __init__(self, config: ListConfig):
        self.values = [str(v) for v in config.values]
        self.logic = config.logic
        self.match_on = config.match_on
        # Default to exact for backward compat
        self.match_mode = getattr(config, 'match_mode', 'exact')
        self.case_sensitive = config.case_sensitive

        # Compile regex for matching values
        if not self.values:
            self._regex = None
        else:
            escaped = [re.escape(v) for v in self.values]

            if self.match_mode == "contains":
                # Word boundary matching for substring/keyword detection
                self.pattern = f"\\b({'|'.join(escaped)})\\b"
            else:
                # Exact match using anchors (original behavior)
                self.pattern = f"^({'|'.join(escaped)})$"

            if not self.case_sensitive:
                self.pattern = f"(?i){self.pattern}"

            self._regex = re2.compile(self.pattern)

    def evaluate(self, data: Any) -> EvaluatorResult:
        # 1. Normalize input
        if data is None:
            input_values = []
        elif isinstance(data, list):
            input_values = [str(item) for item in data]
        else:
            input_values = [str(data)]

        # 2. Short-circuit if input is empty (Control Ignored -> Safe)
        if not input_values:
            return EvaluatorResult(
                matched=False,
                confidence=1.0,
                message="Empty input - Control ignored",
                metadata={"input_count": 0},
            )

        # 3. Short-circuit if control values are empty (Control Ignored -> Safe)
        if self._regex is None:
            return EvaluatorResult(
                matched=False,
                confidence=1.0,
                message="Empty control values - Control ignored",
                metadata={"input_count": len(input_values)},
            )

        # 4. Perform matching on each item
        matches = []
        for val in input_values:
            if self._regex.search(val):
                matches.append(val)

        match_count = len(matches)
        total_count = len(input_values)

        # 5. Determine if logic condition is met
        condition_met = False
        if self.logic == "any":
            condition_met = match_count > 0
        elif self.logic == "all":
            condition_met = match_count == total_count

        # 6. Apply match_on inversion
        is_match = condition_met
        if self.match_on == "no_match":
            is_match = not condition_met

        # Construct message
        msg_parts = []
        if is_match:
            msg_parts.append("Control triggered.")
        else:
            msg_parts.append("Control not triggered.")

        msg_parts.append(f"Logic: {self.logic}, MatchOn: {self.match_on}.")
        if matches:
            msg_parts.append(f"Matched values: {', '.join(matches)}.")
        else:
            msg_parts.append("No values matched.")

        return EvaluatorResult(
            matched=is_match,
            confidence=1.0,
            message=" ".join(msg_parts),
            metadata={
                "logic": self.logic,
                "match_on": self.match_on,
                "matches": matches,
                "input_count": total_count,
            },
        )


def _create_plugin_evaluator(config: PluginConfig) -> Evaluator:
    """Create a plugin evaluator instance.

    Args:
        config: Plugin configuration with plugin_name and plugin_config

    Returns:
        Plugin instance (which is an Evaluator)

    Raises:
        ValueError: If plugin not found or cannot be loaded
    """
    plugin_name = config.plugin_name
    plugin_config = config.plugin_config

    # Get plugin class from registry
    plugin_class = get_plugin(plugin_name)
    if plugin_class is None:
        raise ValueError(
            f"Plugin '{plugin_name}' not found. "
            f"Available plugins can be listed with: agent_control.plugins.list_plugins()"
        )

    # Instantiate plugin with config
    try:
        plugin = plugin_class(plugin_config)
        logger.info(f"Loaded plugin: {plugin_name}")
        return plugin
    except Exception as e:
        logger.error(f"Failed to initialize plugin {plugin_name}: {e}")
        raise ValueError(f"Failed to initialize plugin '{plugin_name}': {e}") from e


def get_evaluator(control_evaluator: ControlEvaluator) -> Evaluator:
    """Factory to create an evaluator instance from configuration.

    All evaluators implement the same interface:
        - __init__(config) - initialize with configuration
        - evaluate(data) -> EvaluatorResult - evaluate data

    Args:
        control_evaluator: The control evaluator configuration

    Returns:
        Evaluator instance ready to use

    Raises:
        NotImplementedError: If evaluator type not supported
        ValueError: If plugin not found (for plugin type)
    """
    if control_evaluator.type == "regex":
        return RegexControlEvaluator(control_evaluator.config)  # type: ignore

    elif control_evaluator.type == "list":
        return ListControlEvaluator(control_evaluator.config)  # type: ignore

    elif control_evaluator.type == "plugin":
        # Plugins ARE Evaluators - no wrapper needed
        return _create_plugin_evaluator(control_evaluator.config)  # type: ignore

    raise NotImplementedError(f"Evaluator type '{control_evaluator.type}' not yet implemented")
