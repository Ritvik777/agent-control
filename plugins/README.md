# Agent Control Plugins

Plugin implementations for agent-control.

## Installation

```bash
# Base package (no plugins)
pip install agent-control-plugins

# With Luna-2 plugin
pip install agent-control-plugins[luna2]
```

## Available Plugins

### Luna-2 Plugin

Galileo Luna-2 enterprise runtime protection plugin for real-time safety and quality checks.

```python
from agent_control_plugins.luna2 import Luna2Plugin, Luna2Config

# Configure
config = Luna2Config(
    stage_type="local",
    metric="input_toxicity",
    operator="gt",
    target_value="0.5",
    galileo_project="my-project",
)

# Evaluate
plugin = Luna2Plugin()
result = plugin.evaluate(data="Some text to check", config=config)

if result.matched:
    print("Content flagged!")
```

## Creating Custom Plugins

Extend `PluginEvaluator` to create your own plugins:

```python
from agent_control_plugins.base import PluginEvaluator, PluginMetadata
from agent_control_models.controls import EvaluatorResult

class MyPlugin(PluginEvaluator):
    metadata = PluginMetadata(
        name="my-plugin",
        version="1.0.0",
        description="My custom plugin",
    )

    def evaluate(self, data, config):
        # Your evaluation logic
        return EvaluatorResult(
            matched=True,
            confidence=0.9,
            message="Evaluation complete"
        )
```

