# Agent Protect SDK

Python SDK for interacting with Agent Protect services.

## Features

- Simple async/await API
- Type-safe with Pydantic models
- Automatic connection management
- Comprehensive error handling
- Full type hints support

## Installation

### For Development (within monorepo)

```bash
# From the root directory
uv sync
```

### For Production Use

```bash
# Install from PyPI (when published)
pip install agent-protect-sdk

# Or install from wheel
pip install agent_protect_sdk-0.1.0-py3-none-any.whl
```

## Quick Start

```python
import asyncio
from agent_protect_sdk import AgentProtectClient

async def main():
    # Create client
    async with AgentProtectClient(base_url="http://localhost:8000") as client:
        # Check server health
        health = await client.health_check()
        print(f"Server status: {health['status']}")
        
        # Check content protection
        result = await client.check_protection(
            content="Is this text safe?",
            context={"source": "user_input"}
        )
        
        print(f"Is safe: {result.is_safe}")
        print(f"Confidence: {result.confidence}")
        print(f"Reason: {result.reason}")

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### AgentProtectClient

Main client class for interacting with the Agent Protect server.

#### Constructor

```python
AgentProtectClient(
    base_url: str = "http://localhost:8000",
    timeout: float = 30.0
)
```

**Parameters:**
- `base_url`: Base URL of the Agent Protect server
- `timeout`: Request timeout in seconds

#### Methods

##### health_check()

Check the server health status.

```python
async def health_check() -> Dict[str, str]
```

**Returns:** Dictionary with `status` and `version` keys

##### check_protection()

Analyze content for safety.

```python
async def check_protection(
    content: str,
    context: Optional[Dict[str, str]] = None
) -> ProtectionResult
```

**Parameters:**
- `content`: Text content to analyze
- `context`: Optional context information

**Returns:** `ProtectionResult` object with analysis results

### ProtectionResult

Result model from protection checks.

**Attributes:**
- `is_safe` (bool): Whether the content is considered safe
- `confidence` (float): Confidence score (0.0 to 1.0)
- `reason` (Optional[str]): Explanation for the result

## Advanced Usage

### Manual Connection Management

```python
from agent_protect_sdk import AgentProtectClient

client = AgentProtectClient(base_url="http://localhost:8000")

# Use the client
result = await client.check_protection("test content")

# Don't forget to close
await client.close()
```

### Custom Timeout

```python
# Create client with 60 second timeout
async with AgentProtectClient(
    base_url="http://localhost:8000",
    timeout=60.0
) as client:
    result = await client.check_protection("test content")
```

## Development

### Building the SDK

```bash
cd sdk
uv build
```

### Running Tests

```bash
cd sdk
uv run pytest
```

### Type Checking

```bash
cd sdk
uv run mypy src/
```

## Publishing

See [DEPLOYMENT.md](../DEPLOYMENT.md) for deployment and publishing instructions.

