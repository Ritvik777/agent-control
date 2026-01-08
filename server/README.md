# Agent Protect Server

Server component for Agent Protect - provides agent protection services via REST API.

## Features

- FastAPI-based REST API
- Health check endpoint
- Content protection analysis endpoint
- Configurable via environment variables
- Async/await support

## Installation

### For Development (within monorepo)

```bash
# From the root directory
uv sync

# Run the server
cd server
uv run python -m agent_protect_server.main
```

### For Production Deployment

```bash
# Build the package
cd server
uv build

# Install the built package
uv pip install dist/agent_protect_server-0.1.0-py3-none-any.whl

# Run the server
agent-protect-server
```

## Configuration

Create a `.env` file in the server directory:

```env
# Server settings
HOST=0.0.0.0
PORT=8000
DEBUG=false
API_VERSION=v1
API_PREFIX=/api

# Authentication
AGENT_CONTROL_API_KEY_ENABLED=true
AGENT_CONTROL_API_KEYS=your-api-key-here
AGENT_CONTROL_ADMIN_API_KEYS=your-admin-key-here
```

## Authentication

The Agent Control Server supports API key authentication via the `X-API-Key` header.

### Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `AGENT_CONTROL_API_KEY_ENABLED` | Enable/disable authentication | `false` |
| `AGENT_CONTROL_API_KEYS` | Comma-separated list of valid API keys | (none) |
| `AGENT_CONTROL_ADMIN_API_KEYS` | Comma-separated list of admin API keys | (none) |

### Access Levels

| Level | Endpoints | Key Type |
|-------|-----------|----------|
| Public | `/health` | None required |
| Protected | All `/api/v1/*` endpoints | Regular or Admin |

### Key Rotation

Multiple API keys are supported to enable zero-downtime key rotation:

1. Add the new key to `AGENT_CONTROL_API_KEYS`
2. Update clients to use the new key  
3. Remove the old key from `AGENT_CONTROL_API_KEYS`
4. Redeploy the server

### Example Usage

```bash
# With curl
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/agents/...

# With Python SDK
from agent_control import AgentControlClient

async with AgentControlClient(api_key="your-api-key") as client:
    await client.health_check()

# Or via environment variable
export AGENT_CONTROL_API_KEY="your-api-key"
async with AgentControlClient() as client:
    await client.health_check()
```

### Disabling Authentication

For local development, you can disable authentication:

```env
AGENT_CONTROL_API_KEY_ENABLED=false
```

**Warning**: Never disable authentication in production environments.

## API Endpoints

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Protection Check

```bash
POST /protect
Content-Type: application/json

{
  "content": "Text to analyze",
  "context": {
    "source": "user_input"
  }
}
```

Response:
```json
{
  "is_safe": true,
  "confidence": 0.95,
  "reason": "Content appears safe"
}
```

## Development

### Running Tests

```bash
cd server
uv run pytest
```

### Type Checking

```bash
cd server
uv run mypy src/
```

### Linting

```bash
cd server
uv run ruff check src/
```

## Deployment

See [DEPLOYMENT.md](../DEPLOYMENT.md) for detailed deployment instructions.

