# Agent Control

**Runtime guardrails for AI agents — configurable, extensible, and production-ready.**

AI agents interact with users, tools, and external systems in unpredictable ways. Agent Control provides an extensible, policy-based runtime layer that evaluates inputs and outputs against configurable rules — blocking prompt injections, PII leakage, and other risks without modifying your agent's code.

---

## See It In Action

```python
import agent_control
from agent_control import control, ControlViolationError

# Initialize once at startup
agent_control.init(
    agent_name="my-agent",
    agent_id="my-agent-v1",
    server_url="http://localhost:8000"
)

# Protect any function with a decorator
@control()
async def chat(message: str) -> str:
    return await llm.generate(message)

# Violations are caught automatically
try:
    response = await chat(user_input)
except ControlViolationError as e:
    print(f"Blocked by {e.control_name}: {e.message}")
```

---

## Key Features

- **Safety Without Code Changes** — Add guardrails with a `@control()` decorator
- **Runtime Configuration** — Update controls without redeploying your application
- **Centralized Policies** — Define controls once, apply to multiple agents
- **Web Dashboard** — Manage agents and controls through the UI
- **API Key Authentication** — Secure your control server in production
- **Pluggable Evaluators** — Regex, list matching, AI-powered detection (Luna-2), or custom plugins
- **Fail-Safe Defaults** — Deny controls fail closed on error; plugins like Luna-2 support configurable error handling

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **uv** — Fast Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Docker** — For running PostgreSQL
- **Node.js 18+** — For the web dashboard (optional)

### 1. Clone and Install

```bash
git clone https://github.com/rungalileo/agent-control.git
cd agent-control
make sync
```

### 2. Start the Server

```bash
# Start database and run migrations
cd server && docker-compose up -d && make alembic-upgrade && cd ..

# Start the server
make server-run
```

Server is now running at `http://localhost:8000`.

### 3. Start the Dashboard (Optional)

```bash
cd ui && npm install && npm run dev
```

Dashboard is now running at `http://localhost:4000`.

### 4. Use the SDK

```python
import agent_control
from agent_control import control, ControlViolationError

# Initialize — connects to server and loads assigned policy
agent_control.init(
    agent_name="my-agent",
    agent_id="my-agent-v1",
    server_url="http://localhost:8000"
)

# Apply the agent's policy to any function
@control()
async def chat(message: str) -> str:
    return await llm.generate(message)

# Handle violations gracefully
async def main():
    try:
        response = await chat("Hello!")
        print(response)
    except ControlViolationError as e:
        print(f"Blocked by {e.control_name}: {e.message}")
```

> **Note**: Authentication is disabled by default for local development. See [docs/REFERENCE.md](docs/REFERENCE.md#authentication) for production setup.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CONTROL_URL` | `http://localhost:8000` | Server URL for SDK |
| `AGENT_CONTROL_API_KEY` | — | API key for authentication |
| `AGENT_CONTROL_API_KEY_ENABLED` | `false` | Enable API key auth on server |
| `GALILEO_API_KEY` | — | Required for Luna-2 AI evaluator |

---

## Defining Controls

Controls are defined via the API or dashboard. Each control specifies what to check and what action to take.

### Example: Block PII in Output (Regex)

```json
{
  "name": "block-ssn-output",
  "description": "Block Social Security Numbers in responses",
  "enabled": true,
  "applies_to": "llm_call",
  "check_stage": "post",
  "selector": { "path": "output" },
  "evaluator": {
    "plugin": "regex",
    "config": { "pattern": "\\b\\d{3}-\\d{2}-\\d{4}\\b" }
  },
  "action": { "decision": "deny" }
}
```

### Example: Block Toxic Input (Luna-2 AI)

```json
{
  "name": "block-toxic-input",
  "description": "Block toxic or harmful user messages",
  "enabled": true,
  "applies_to": "llm_call",
  "check_stage": "pre",
  "selector": { "path": "input" },
  "evaluator": {
    "plugin": "galileo-luna2",
    "config": {
      "metric": "input_toxicity",
      "operator": "gt",
      "target_value": 0.5
    }
  },
  "action": { "decision": "deny" }
}
```

See [docs/REFERENCE.md](docs/REFERENCE.md#evaluators) for full evaluator documentation.

---

## Architecture

Agent Control is built as a monorepo with these components:

```
┌──────────────────────────────────────────────────────────────────┐
│                         Your Application                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                     @control() decorator                    │  │
│  │                            │                                │  │
│  │                            ▼                                │  │
│  │  ┌──────────┐    ┌─────────────────┐    ┌──────────────┐   │  │
│  │  │  Input   │───▶│  Agent Control  │───▶│    Output    │   │  │
│  │  │          │    │     Engine      │    │              │   │  │
│  │  └──────────┘    └─────────────────┘    └──────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Agent Control Server                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │  Controls  │  │  Policies  │  │  Plugins   │  │   Agents   │  │
│  │    API     │  │    API     │  │  Registry  │  │    API     │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                         Plugin Ecosystem                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │   Regex    │  │    List    │  │   Luna-2   │  │   Custom   │  │
│  │ Evaluator  │  │ Evaluator  │  │   Plugin   │  │  Plugins   │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

| Package | Description |
|:--------|:------------|
| `agent-control` | Python SDK with `@control()` decorator |
| `agent-control-server` | FastAPI server with Control Management API |
| `agent-control-engine` | Core evaluation logic and plugin system |
| `agent-control-models` | Shared Pydantic v2 models |
| `agent-control-plugins` | Built-in evaluator plugins |
| `ui` | Next.js web dashboard |

---

## Development

### Directory Structure

```
agent-control/
├── sdks/python/     # Python SDK (agent-control)
├── server/          # FastAPI server (agent-control-server)
├── engine/          # Evaluation engine (agent-control-engine)
├── models/          # Shared models (agent-control-models)
├── plugins/         # Plugin implementations (agent-control-plugins)
├── ui/              # Next.js dashboard
└── examples/        # Usage examples
```

### Makefile Commands

| Command | Description |
|:--------|:------------|
| `make sync` | Install dependencies for all packages |
| `make test` | Run tests across all packages |
| `make lint` | Run ruff linting |
| `make typecheck` | Run mypy type checking |
| `make check` | Run all quality checks |
| `make server-run` | Start the server |

---

## Documentation

- **[Reference](docs/REFERENCE.md)** — Concepts, evaluators, SDK, API, configuration
- **[Examples](examples/README.md)** — Working code examples and patterns
- **[Contributing](CONTRIBUTING.md)** — Development setup and guidelines
- **[SDK Documentation](sdks/python/README.md)** — Python SDK details
- **[UI Documentation](ui/README.md)** — Dashboard setup and usage

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes (ensure `make check` passes)
4. Submit a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

Apache 2.0 — See [LICENSE](LICENSE) for details.
