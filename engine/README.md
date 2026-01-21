# Agent Control Engine

Core evaluation logic for Agent Control.

## Responsibilities

- **Plugin Discovery**: Auto-discover plugins via Python entry points
- **Selector Evaluation**: Extract data from payloads using selector paths
- **Evaluator Execution**: Run plugin evaluators against selected data
- **Caching**: Cache plugin instances for performance

## Plugin Discovery

The engine provides the public API for plugin discovery:

```python
from agent_control_engine import discover_plugins, list_plugins

# Discover all plugins (runs once, safe to call multiple times)
discover_plugins()

# Get all available plugins
plugins = list_plugins()  # Returns dict[str, PluginClass]

# Access a specific plugin
regex_plugin = plugins.get("regex")
```

Plugins are discovered via the `agent_control.plugins` entry point group. Discovery:
1. Scans all installed packages for the entry point
2. Loads each plugin class
3. Checks `is_available()` to verify dependencies
4. Registers available plugins

## Key Functions

| Function | Description |
|----------|-------------|
| `discover_plugins()` | Scan entry points and register plugins |
| `list_plugins()` | Get all registered plugins (triggers discovery) |
| `ensure_plugins_discovered()` | Ensure discovery has run |
| `get_evaluator(config)` | Get cached evaluator instance |
| `evaluate_control(control, payload)` | Evaluate a single control |
