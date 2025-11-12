# Setup Instructions

This document walks you through setting up the Agent Protect project for the first time.

## Step 1: Install UV

UV is a fast Python package manager. Install it with:

### macOS/Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Alternative: Using pip

```bash
pip install uv
```

### Verify Installation

```bash
uv --version
```

You should see something like: `uv 0.x.x`

## Step 2: Install Project Dependencies

This project uses **separate workspaces** for server and SDKs. Install dependencies in each workspace:

### Install Server Dependencies

```bash
cd /path/to/agent-protect/server
uv sync
```

This will install the server and its dependencies, including the models package via path reference.

### Install SDK Dependencies

```bash
cd /path/to/agent-protect/sdks
uv sync
```

This will install the SDK and its dependencies, including the models package via path reference.

## Step 3: Verify Installation

Test that everything is installed correctly:

### Verify Server Installation

```bash
cd server
uv run agent-protect-server --help
```

### Verify SDK Installation

```bash
cd sdks
uv run python -c "from agent_protect_sdk import AgentProtectClient; print('✓ SDK imported successfully')"
```

## Step 4: Run the Server

Start the server:

```bash
uv run agent-protect-server
```

Or for development with auto-reload:

```bash
cd server
uv run uvicorn agent_protect_server.main:app --reload
```

You should see:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## Step 5: Test the API

In a new terminal, test the API:

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0"}

# Protection check
curl -X POST http://localhost:8000/protect \
  -H "Content-Type: application/json" \
  -d '{"content":"Hello, world!"}'

# Expected response:
# {"is_safe":true,"confidence":0.95,"reason":"Content appears safe"}
```

## Step 6: Test the SDK

Create a test file:

```python
# test_sdk.py
import asyncio
from agent_protect_sdk import AgentProtectClient

async def main():
    async with AgentProtectClient(base_url="http://localhost:8000") as client:
        # Health check
        health = await client.health_check()
        print(f"✓ Server health: {health}")
        
        # Protection check
        result = await client.check_protection("Hello, world!")
        print(f"✓ Protection result: {result}")
        
        # Use boolean check
        if result:
            print("✓ Content is safe")
        
        # Check confidence
        if result.is_confident(threshold=0.9):
            print(f"✓ High confidence: {result.confidence}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
uv run python test_sdk.py
```

Expected output:

```
✓ Server health: {'status': 'healthy', 'version': '0.1.0'}
✓ Protection result: [SAFE] Confidence: 95% - Content appears safe
✓ Content is safe
✓ High confidence: 0.95
```

## Step 7: Run the Examples

Try the included examples:

```bash
# Basic usage example
uv run python examples/basic_usage.py

# Batch processing example
uv run python examples/batch_processing.py

# Models usage example
uv run python examples/models_usage.py
```

## Project Structure Overview

After setup, your project structure should look like this:

```
agent-protect/
├── pyproject.toml          # Root configuration
├── .gitignore
├── README.md               # Main documentation
├── QUICKSTART.md           # Quick start guide
├── SETUP.md                # This file
├── DEPLOYMENT.md           # Deployment guide
│
├── models/                 # Shared Pydantic models
│   ├── pyproject.toml
│   ├── README.md
│   └── src/
│       └── agent_protect_models/
│           ├── __init__.py
│           ├── base.py
│           ├── health.py
│           └── protection.py
│
├── server/                 # FastAPI server (separate workspace)
│   ├── pyproject.toml      # Server workspace config
│   ├── README.md
│   └── src/
│       └── agent_protect_server/
│           ├── __init__.py
│           ├── main.py
│           └── config.py
│
├── sdks/                   # SDKs (separate workspace)
│   ├── pyproject.toml      # SDKs workspace config
│   ├── README.md
│   └── python/             # Python SDK implementation
│       ├── pyproject.toml
│       ├── README.md
│       └── src/
│           └── agent_protect_sdk/
│               ├── __init__.py
│               └── client.py
│
└── examples/               # Usage examples
    ├── basic_usage.py
    ├── batch_processing.py
    └── models_usage.py
```

## Understanding the Architecture

### Multi-Workspace Structure

This project uses a **multi-workspace structure** with separate workspaces:

1. **models** (`agent-protect-models`):
   - Foundation package
   - Contains all Pydantic data models
   - Used by both server and SDK via path references
   - Ensures type safety and consistency

2. **server workspace** (`agent-protect-server`):
   - FastAPI application
   - Independent workspace at `server/`
   - References `models` via relative path
   - Can be developed and deployed independently

3. **sdks workspace** (`agent-protect-sdk`):
   - Python client library workspace at `sdks/`
   - Contains Python SDK implementation
   - References `models` via relative path
   - Can be developed and deployed independently

### Dependency Flow

```
models (foundation)
  ↓ (path reference)
  ├─→ server (uses ../models)
  └─→ sdks/python (uses ../../models)
```

### Workspace Configuration

**Server workspace** (`server/pyproject.toml`):
```toml
[tool.uv.sources]
agent-protect-models = { path = "../models", editable = true }
```

**SDK workspace** (`sdks/pyproject.toml`):
```toml
[tool.uv.workspace]
members = ["python"]
```

**SDK package** (`sdks/python/pyproject.toml`):
```toml
[tool.uv.sources]
agent-protect-models = { path = "../../models", editable = true }
```

This structure allows independent development while maintaining shared models.

## Common Issues and Solutions

### Issue: `command not found: uv`

**Solution**: Install UV following Step 1 above, then restart your terminal.

### Issue: `ModuleNotFoundError: No module named 'agent_protect_models'`

**Solution**: Run `uv sync` in the workspace directory (server/ or sdks/) to install dependencies including the models path reference.

### Issue: Server won't start

**Solution**: 
1. Check if port 8000 is already in use: `lsof -i :8000`
2. Kill the process: `kill -9 <PID>`
3. Or use a different port: `uv run uvicorn agent_protect_server.main:app --port 8001`

### Issue: SDK can't connect to server

**Solution**:
1. Make sure the server is running: `curl http://localhost:8000/health`
2. Check the base URL in your client code
3. Check firewall settings

### Issue: Import errors after changes

**Solution**: After modifying models, reinstall the workspace:

```bash
uv sync --force
```

## Development Workflow

### Making Changes

1. **Edit files** in the appropriate package
2. **Test locally** (in the workspace directory):
   ```bash
   # For server
   cd server && uv run pytest
   
   # For SDK
   cd sdks && uv run pytest
   ```
3. **Lint and format** (in the workspace directory):
   ```bash
   cd server && uv run ruff check .
   cd sdks && uv run ruff check .
   ```
4. **Type check** (in the workspace directory):
   ```bash
   cd server && uv run mypy src
   cd sdks && uv run mypy python/src
   ```

### Adding a New Dependency

For a specific workspace:

```bash
# Add to server workspace
cd server
uv add fastapi-users

# Add to SDK workspace
cd sdks
uv add --dev pytest-cov

# Add to models
cd models
uv add pydantic-extra-types
```

### Running Tests

```bash
# Server tests
cd server && uv run pytest

# SDK tests
cd sdks && uv run pytest

# With coverage
cd server && uv run pytest --cov=src

# All workspaces
cd server && uv run pytest && cd ../sdks && uv run pytest
```

## Next Steps

Now that you have everything set up:

1. ✅ Read [QUICKSTART.md](QUICKSTART.md) for quick usage examples
2. ✅ Explore [README.md](README.md) for comprehensive documentation
3. ✅ Check [DEPLOYMENT.md](DEPLOYMENT.md) for deployment options
4. ✅ Review package-specific READMEs:
   - [models/README.md](models/README.md)
   - [server/README.md](server/README.md)
   - [sdks/README.md](sdks/README.md)
   - [sdks/python/README.md](sdks/python/README.md)

## Getting Help

- 📖 Read the documentation in each package
- 🐛 Check GitHub Issues
- 💬 Join GitHub Discussions
- 📧 Contact the team

## Additional Resources

- **UV Documentation**: https://github.com/astral-sh/uv
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **Pydantic Documentation**: https://docs.pydantic.dev
- **HTTPX Documentation**: https://www.python-httpx.org

Happy coding! 🚀

