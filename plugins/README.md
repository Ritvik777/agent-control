# Agent Control Plugins

Plugin implementations for agent-control.

## Installation

```bash
# Base package (no plugins)
pip install agent-control-plugins

# With Luna-2 plugin (uses direct HTTP API, no Galileo SDK required)
pip install agent-control-plugins[luna2]
```

## Available Plugins

### Luna-2 Plugin

Galileo Luna-2 enterprise runtime protection plugin for real-time safety and quality checks.
This plugin calls the Galileo Protect API directly via HTTP - no Galileo SDK required.

**Environment Variables:**
- `GALILEO_API_KEY`: Your Galileo API key (required)
- `GALILEO_CONSOLE_URL`: Galileo Console URL (optional, defaults to production)

```python
import asyncio
from agent_control_plugins.luna2 import Luna2Plugin, Luna2Config

# Configure
config = Luna2Config(
    stage_type="local",
    metric="input_toxicity",
    operator="gt",
    target_value=0.5,  # Use numeric values for thresholds
    galileo_project="my-project",
)

# Create plugin instance with config
plugin = Luna2Plugin(config)

# Evaluate (async)
async def check_content():
    result = await plugin.evaluate(data="Some text to check")
    if result.matched:
        print("Content flagged!")
    return result

asyncio.run(check_content())
```

### Using the HTTP Client Directly

You can also use the `GalileoProtectClient` directly for more control:

```python
import asyncio
from agent_control_plugins.luna2 import GalileoProtectClient, Payload

async def main():
    async with GalileoProtectClient() as client:
        response = await client.invoke_protect(
            payload=Payload(input="Hello world", output=""),
            project_name="my-project",
            stage_name="my-stage",
        )
        print(f"Status: {response.status}")

asyncio.run(main())
```

## Creating Custom Plugins

Extend `PluginEvaluator` to create your own plugins:

```python
from typing import Any
from pydantic import BaseModel
from agent_control_models import (
    EvaluatorResult,
    PluginEvaluator,
    PluginMetadata,
    register_plugin,
)

class MyConfig(BaseModel):
    threshold: float = 0.5

@register_plugin
class MyPlugin(PluginEvaluator[MyConfig]):
    metadata = PluginMetadata(
        name="my-plugin",
        version="1.0.0",
        description="My custom plugin",
    )
    config_model = MyConfig

    async def evaluate(self, data: Any) -> EvaluatorResult:
        # Your evaluation logic
        return EvaluatorResult(
            matched=True,
            confidence=0.9,
            message="Evaluation complete"
        )
```

### Entry Point Registration (Third-Party Plugins)

For distributable plugins, register via Python entry points in your `pyproject.toml`:

```toml
[project.entry-points."agent_control.plugins"]
my-plugin = "my_package.plugin:MyPlugin"
```

Plugins registered this way are automatically discovered when Agent Control starts.

### Optional Dependencies with `is_available()`

If your plugin has optional dependencies, override `is_available()` to check them:

```python
# Check if optional dependency is installed
try:
    import some_optional_lib
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False

@register_plugin
class MyPlugin(PluginEvaluator[MyConfig]):
    metadata = PluginMetadata(name="my-plugin", ...)
    config_model = MyConfig

    @classmethod
    def is_available(cls) -> bool:
        """Only register if dependencies are installed."""
        return DEPS_AVAILABLE

    async def evaluate(self, data: Any) -> EvaluatorResult:
        ...
```

When `is_available()` returns `False`, the plugin is silently skipped during registration. This allows plugins with optional dependencies (like Luna-2 which requires `httpx`) to be included in the package without causing import errors.
