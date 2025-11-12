# Workspace Migration Guide

## Overview

The Agent Protect project has been migrated from a single monorepo workspace to **separate independent workspaces** for the SDK and server components.

## What Changed?

### Before (Single Workspace)

```
agent-protect/
├── pyproject.toml  (workspace root with members: models, server, sdk)
├── models/
├── server/
└── sdk/
```

All packages were managed by a single root workspace configuration.

### After (Separate Workspaces)

```
agent-protect/
├── pyproject.toml  (root config, no workspace)
├── models/
├── server/
│   └── pyproject.toml  (independent workspace)
└── sdks/
    ├── pyproject.toml  (independent workspace)
    └── python/
```

Each major component (server and SDKs) now has its own independent workspace.

## Benefits of Separate Workspaces

1. **Independent Development**: Server and SDK teams can work completely independently
2. **Isolated Dependencies**: Each workspace manages its own dependencies without conflicts
3. **Separate Testing**: Run tests in each workspace without affecting others
4. **Flexible Deployment**: Deploy server and SDK on different schedules
5. **Clear Ownership**: Easier to assign ownership and manage permissions
6. **Future Multi-Language SDKs**: Easy to add TypeScript, Go, or other SDK implementations

## How It Works

### Dependency Management

Both workspaces reference the shared `models` package via **path references**:

**Server** (`server/pyproject.toml`):
```toml
[tool.uv.sources]
agent-protect-models = { path = "../models", editable = true }
```

**SDK** (`sdks/python/pyproject.toml`):
```toml
[tool.uv.sources]
agent-protect-models = { path = "../../models", editable = true }
```

This allows:
- ✅ Local development with live updates
- ✅ Easy transition to PyPI for production
- ✅ Type safety across all components

### Working with Each Workspace

#### Server Workspace

```bash
cd server

# Install dependencies
uv sync

# Run server
uv run agent-protect-server

# Run tests
uv run pytest

# Lint
uv run ruff check .

# Type check
uv run mypy src
```

#### SDK Workspace

```bash
cd sdks

# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check .

# Type check
uv run mypy python/src
```

## Migration Steps Completed

1. ✅ Created `sdks/pyproject.toml` as a new workspace root
2. ✅ Moved `sdk/` to `sdks/python/`
3. ✅ Updated `server/pyproject.toml` to be an independent workspace
4. ✅ Changed all `{ workspace = true }` references to path-based references
5. ✅ Updated root `pyproject.toml` to remove workspace configuration
6. ✅ Updated all documentation (README, SETUP, DEPLOYMENT)

## What You Need to Do

### For Development

1. **Install dependencies in each workspace**:
   ```bash
   cd server && uv sync
   cd ../sdks && uv sync
   ```

2. **Run commands from the workspace directory**:
   ```bash
   # Server commands
   cd server
   uv run agent-protect-server
   
   # SDK commands
   cd sdks
   uv run pytest
   ```

### For CI/CD

Update your CI/CD pipelines to work with separate workspaces:

```yaml
# Example: Test both workspaces
jobs:
  test-server:
    steps:
      - run: cd server && uv sync && uv run pytest
  
  test-sdk:
    steps:
      - run: cd sdks && uv sync && uv run pytest
```

## Adding New SDKs

With this structure, adding new language SDKs is straightforward:

```bash
cd sdks

# Add TypeScript SDK
mkdir typescript
cd typescript
# Create TypeScript SDK implementation

# Add to workspace
# Edit sdks/pyproject.toml:
# members = ["python", "typescript"]
```

## Troubleshooting

### Issue: ModuleNotFoundError for agent_protect_models

**Solution**: Run `uv sync` in the workspace directory (server/ or sdks/)

### Issue: Changes to models not reflected

**Solution**: The path references are editable by default, so changes should be immediate. If not:
```bash
cd server && uv sync --force
cd ../sdks && uv sync --force
```

### Issue: Want to go back to single workspace

**Solution**: You can revert by:
1. Restoring the root `pyproject.toml` with `[tool.uv.workspace]`
2. Changing path references back to `{ workspace = true }`
3. Moving `sdks/python/` back to `sdk/`

## Questions?

- Read the updated [README.md](README.md) for architecture overview
- Check [SETUP.md](SETUP.md) for development workflow
- See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment strategies

## Summary

This migration provides better separation of concerns and makes it easier to:
- Develop server and SDK independently
- Add new SDK implementations in other languages
- Deploy components on different schedules
- Manage dependencies without conflicts

The transition is seamless - all existing code works as before, just with clearer boundaries and better organization.

