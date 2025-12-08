# Contributing to Agent Protect

Thanks for contributing! This document covers conventions, setup, and workflows for all contributors.

## Project Architecture

Agent Protect is a **uv workspace monorepo** with these components:

```
agent-protect/
├── models/          # Shared Pydantic models (agent-control-models)
├── server/          # FastAPI server (agent-control-server)
├── sdks/python/     # Python SDK (agent-control)
├── engine/          # Control evaluation engine (agent-control-engine)
├── plugins/         # Plugin implementations (agent-control-plugins)
└── examples/        # Usage examples
```

**Dependency flow:**
```
SDK ──────────────────────────────────────┐
                                          ▼
Server ──► Engine ──► Models ◄── Plugins
```

---

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker (for server database)

### Initial Setup

```bash
# Clone the repository
git clone <repo-url>
cd agent-protect

# Install all dependencies (creates single .venv for workspace)
make sync

# Install git hooks (recommended)
make hooks-install
```

---

## Working with Components

### Models (`models/`)

Shared Pydantic models used by both server and SDK.

```bash
# Location
models/src/agent_control_models/

# Key files
├── agent.py       # Agent, ToolCall, LlmCall models
├── controls.py    # Control definitions, evaluators
├── evaluation.py  # EvaluationRequest/Response
├── policy.py      # Policy model
└── health.py      # Health response
```

**When to modify:**
- Adding new API request/response models
- Changing shared data structures
- Adding validation rules

**Testing:**
```bash
cd models
uv run pytest
```

---

### Server (`server/`)

FastAPI server providing the Agent Control API.

```bash
# Location
server/src/agent_control_server/

# Key files
├── main.py        # FastAPI app entrypoint
├── endpoints/     # API route handlers
├── services/      # Business logic
└── db/            # Database models & queries
```

**Running the server:**
```bash
cd server

# Start dependencies (PostgreSQL via Docker)
make start-dependencies

# Run database migrations
make alembic-upgrade

# Start server with hot-reload
make run
```

**Database migrations:**
```bash
cd server

# Create new migration
make alembic-migrate MSG="add new column"

# Apply migrations
make alembic-upgrade

# Rollback one migration
make alembic-downgrade

# View migration history
make alembic-history
```

**Testing:**
```bash
cd server
make test
```

---

### SDK (`sdks/python/`)

Python client SDK for interacting with the Agent Control server.

```bash
# Location
sdks/python/src/agent_control/

# Key files
├── __init__.py           # Public API exports, init() function
├── client.py             # AgentControlClient (HTTP client)
├── agents.py             # Agent registration operations
├── policies.py           # Policy management
├── controls.py           # Control management
├── control_sets.py       # Control set management
├── evaluation.py         # Evaluation checks
├── control_decorators.py # @control decorator
└── plugins/              # Plugin system
```

**Key exports:**
```python
import agent_control

# Initialization
agent_control.init(agent_name="...", agent_id="...")

# Decorator
@agent_control.control()
async def my_function(): ...

# Client
async with agent_control.AgentControlClient() as client:
    await agent_control.agents.get_agent(client, "id")
```

**Testing:**
```bash
cd sdks/python
make test  # Starts server automatically
```

**Adding new SDK functionality:**
1. Add operation function in appropriate module (e.g., `policies.py`)
2. Export in `__init__.py` if needed
3. Add tests in `tests/`
4. Update docstrings with examples

---

### Engine (`engine/`)

Control evaluation logic (regex, list matching, plugin execution).

```bash
# Location
engine/src/agent_control_engine/

# Key files
├── core.py        # Main ControlEngine class
├── evaluators.py  # RegexEvaluator, ListEvaluator, PluginEvaluator
└── selectors.py   # Data selection from payloads
```

**Testing:**
```bash
cd engine
make test
```

**Adding a new evaluator:**
1. Create class in `evaluators.py` inheriting from `Evaluator`
2. Implement `evaluate(data: str, config: dict) -> EvaluatorResult`
3. Register in `core.py` evaluator registry
4. Add tests in `tests/test_evaluators.py`

---

### Plugins (`plugins/`)

External integrations (e.g., Galileo Luna-2).

```bash
# Location
plugins/src/agent_control_plugins/

# Key files
├── base.py        # PluginEvaluator base class
└── luna2/         # Galileo Luna-2 integration
    ├── plugin.py  # Luna2Plugin implementation
    └── config.py  # Luna2Config model
```

**Adding a new plugin:**
1. Create directory under `plugins/src/agent_control_plugins/`
2. Implement `PluginEvaluator` interface
3. Register via entry points or manual registration
4. Add optional dependencies in `plugins/pyproject.toml`

---

## Code Quality

### Linting (Ruff)

```bash
# Check all packages
make lint

# Auto-fix issues
make lint-fix

# Single package
cd server && make lint
```

### Type Checking (mypy)

```bash
# Check all packages
make typecheck

# Single package
cd sdks/python && make typecheck
```

### Pre-push Checks

```bash
# Run all checks (test + lint + typecheck)
make check

# Or manually run pre-push hook
make prepush
```

---

## Testing Conventions

Write tests using **Given/When/Then** comments:

```python
def test_create_control(client: TestClient) -> None:
    # Given: a valid control payload
    payload = {"name": "pii-protection"}

    # When: creating the control via API
    response = client.put("/api/v1/controls", json=payload)

    # Then: the control is created successfully
    assert response.status_code == 200
    assert "control_id" in response.json()
```

**Guidelines:**
- Keep tests small and focused
- Use explicit setup over hidden fixtures
- Test both success and error cases
- Mock external services (database, Galileo API)

---

## Building & Publishing

### Build Packages

```bash
# Build all
make build

# Build individual packages
make build-models
make build-server
make build-sdk
cd engine && make build
```

### Publish Packages

```bash
# Publish all (requires PyPI credentials)
make publish

# Publish individual packages
make publish-models
make publish-server
make publish-sdk
```

**Version bumping:**
Update `version` in respective `pyproject.toml` files:
- `models/pyproject.toml`
- `server/pyproject.toml`
- `sdks/python/pyproject.toml`
- `engine/pyproject.toml`
- `plugins/pyproject.toml`

---

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `refactor/description` - Code refactoring

### Commit Messages

Use conventional commits:
```
feat: add policy assignment endpoint
fix: handle missing agent gracefully
refactor: extract evaluator logic to engine
docs: update SDK usage examples
test: add control set integration tests
```

### Pull Request Checklist

- [ ] Tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] Documentation updated if needed
- [ ] Examples updated if API changed

---

## Common Tasks

### Add a new API endpoint

1. Add Pydantic models in `models/` if needed
2. Add route handler in `server/src/agent_control_server/endpoints/`
3. Add service logic in `server/src/agent_control_server/services/`
4. Add SDK wrapper in `sdks/python/src/agent_control/`
5. Add tests for both server and SDK
6. Update examples if user-facing

### Add a new control evaluator type

1. Add evaluator class in `engine/src/agent_control_engine/evaluators.py`
2. Register in engine's evaluator registry
3. Add server support in evaluation endpoint
4. Add SDK convenience methods if needed
5. Add comprehensive tests

### Update shared models

1. Modify models in `models/src/agent_control_models/`
2. Run tests across all packages: `make test`
3. Update any affected server endpoints
4. Update SDK if client-facing

---

## Quick Reference

| Task | Command |
|------|---------|
| Install dependencies | `make sync` |
| Run server | `cd server && make run` |
| Run all tests | `make test` |
| Run linting | `make lint` |
| Run type checks | `make typecheck` |
| Run all checks | `make check` |
| Build packages | `make build` |
| Database migration | `cd server && make alembic-migrate MSG="..."` |
