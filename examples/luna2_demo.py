"""Demo: Luna-2 Plugin for Toxicity Detection.

This example demonstrates using the Luna-2 plugin with Galileo Protect
to detect toxic content in user inputs.

Setup:
    1. Set your Galileo API key:
       export GALILEO_API_KEY="your-api-key"

    2. Set your Galileo console URL (optional):
       export GALILEO_CONSOLE_URL="https://console.demo-v2.galileocloud.io"

    3. Run this script:
       python luna2_demo.py

Requirements:
    pip install agent-control-plugins[luna2]
"""

import os
import sys

# Set environment variables BEFORE importing galileo SDK
os.environ.setdefault("GALILEO_CONSOLE_URL", "https://console.demo-v2.galileocloud.io")

# Check for API key
if not os.getenv("GALILEO_API_KEY"):
    print("❌ Error: GALILEO_API_KEY environment variable is required")
    print("   Set it with: export GALILEO_API_KEY='your-api-key'")
    sys.exit(1)

# Import after setting env vars
from agent_control_plugins.luna2 import (
    LUNA2_AVAILABLE,
    Luna2Config,
    Luna2Plugin,
)

if not LUNA2_AVAILABLE:
    print("❌ Luna-2 plugin not available - galileo SDK not installed")
    print("   Install with: pip install agent-control-plugins[luna2]")
    sys.exit(1)


def main() -> None:
    """Demonstrate Luna-2 toxicity detection with typed config."""
    print("=" * 60)
    print("Luna-2 Plugin Demo - Toxicity Detection")
    print("=" * 60)

    # Configure using Pydantic model (type-safe!)
    config = Luna2Config(
        stage_type="local",
        metric="input_toxicity",
        operator="gt",
        target_value="0.5",
        galileo_project="demo",
        timeout_ms=10000,
    )

    # Initialize plugin with config (new pattern!)
    plugin = Luna2Plugin(config.model_dump())
    print(f"✓ Plugin: {plugin.metadata.name} v{plugin.metadata.version}")

    # Test inputs
    test_cases = [
        "Hello, how can I help you?",
        "You are so stupid and I hate you!",
    ]

    print(f"\nConfig: {config.model_dump()}\n")
    print("Testing toxicity detection:\n")

    for text in test_cases:
        # evaluate() now only takes data (config was set at init)
        result = plugin.evaluate(data=text)

        status = "🚫 TOXIC" if result.matched else "✅ Safe"
        print(f"Input: '{text}'")
        print(f"Result: {status}")
        print(f"Metadata: {result.metadata}\n")

    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
