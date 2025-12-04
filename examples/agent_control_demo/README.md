# Agent Control Demo

A demonstration of server-side control evaluation using the `@control` decorator.

## Overview

This demo shows how to protect AI agent functions with **server-defined policies** using minimal decorator syntax. Policies (containing multiple controls) are defined on the server and the SDK simply applies them.

```python
import agent_control

agent_control.init(agent_name="my-agent", agent_id="agent-123")

@agent_control.control()  # Applies agent's assigned policy
async def chat(message: str) -> str:
    return await llm.respond(message)
```

## Quick Start

### 1. Start the Server

```bash
cd server
rm -f agent_control.db  # Fresh database
make run
```

### 2. Create Controls

```bash
uv run python examples/agent_control_demo/setup_controls.py
```

This creates:
- **block-ssn-output** - Regex control blocking SSN patterns in output
- **block-dangerous-sql** - List control blocking SQL keywords in input

### 3. Run the Demo Agent

```bash
uv run python examples/agent_control_demo/demo_agent.py
```

### 4. Update Controls (Optional)

You can dynamically update controls while the server is running:

```bash
# Allow SSNs (disable the SSN control)
uv run python examples/agent_control_demo/update_controls.py --allow-ssn

# Block SSNs again (re-enable the SSN control)
uv run python examples/agent_control_demo/update_controls.py --block-ssn

# Check current status
uv run python examples/agent_control_demo/update_controls.py --status
```

After updating, run `demo_agent.py` again to see the changed behavior.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT CONTROL SERVER                      │
│                                                              │
│   Agent ──► Policy ──► ControlSet ──► Controls               │
│                                                              │
│   Controls define:                                           │
│   • check_stage: "pre" or "post"                            │
│   • selector: which data to check (input/output)            │
│   • evaluator: how to check (regex/list/plugin)             │
│   • action: what to do (deny/warn/log)                      │
└─────────────────────────────────────────────────────────────┘
                            │
               POST /api/v1/evaluation
                            │
┌─────────────────────────────────────────────────────────────┐
│                      DEMO AGENT                              │
│                                                              │
│   @control(policy="demo-policy")                             │
│   async def chat(message):                                   │
│       # Server evaluates using all controls in the policy    │
│       return llm.respond(message)                            │
│                                                              │
│   @control()  # Uses agent's assigned policy                 │
│   async def query(sql):                                      │
│       # Server evaluates input/output based on check_stage   │
│       return db.execute(sql)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Controls Created

### 1. `block-ssn-output` (Regex)
- **Type**: Regex
- **Pattern**: `\b\d{3}-\d{2}-\d{4}\b` (SSN pattern)
- **Check Stage**: `post` (checks output after function runs)
- **Action**: `deny` (blocks response if SSN found)

### 2. `block-dangerous-sql` (List)
- **Type**: List with `match_mode: "contains"`
- **Values**: DROP, DELETE, TRUNCATE, ALTER, GRANT, etc.
- **Check Stage**: `pre` (checks input before function runs)
- **Action**: `deny` (blocks execution if dangerous keyword found)

## SDK Changes

### New Decorator: `@control`

```python
from agent_control import control

@control()  # Apply agent's assigned policy
async def my_function(input: str) -> str:
    ...

@control(policy="safety-policy")  # Document which policy (optional)
async def my_function(input: str) -> str:
    ...
```

The decorator:
1. Calls `/api/v1/evaluation` with `check_stage="pre"` before execution
   - Server evaluates all "pre" controls in the agent's policy
2. Runs the function
3. Calls `/api/v1/evaluation` with `check_stage="post"` after execution
   - Server evaluates all "post" controls in the agent's policy
4. Raises `ControlViolationError` if any control triggers with `deny` action

### New Exception: `ControlViolationError`

```python
from agent_control import ControlViolationError

try:
    result = await chat("get user SSN")
except ControlViolationError as e:
    print(f"Blocked by: {e.control_name}")
    print(f"Reason: {e.message}")
```

## Model Changes

### `ListConfig.match_mode`

Added `match_mode` field to `ListConfig`:

```python
class ListConfig(BaseModel):
    values: list[str | int | float]
    logic: Literal["any", "all"] = "any"
    match_on: Literal["match", "no_match"] = "match"
    match_mode: Literal["exact", "contains"] = "exact"  # NEW!
    case_sensitive: bool = False
```

- `exact`: Full string match (for allow/deny lists on discrete values like tool names)
- `contains`: Substring/keyword match (for detecting keywords in free text)

## Server Evaluation Flow

1. SDK sends `EvaluationRequest` with `agent_uuid`, `payload`, `check_stage`
2. Server fetches controls for the agent via Policy → ControlSet → Controls
3. `ControlEngine` filters controls by `check_stage` and `applies_to`
4. For each applicable control:
   - Selector extracts data from payload
   - Evaluator checks the data
   - If matched, action is recorded
5. Server returns `EvaluationResponse` with `is_safe` and `matches`

## Files

```
examples/agent_control_demo/
├── README.md            # This file
├── setup_controls.py    # Creates regex/list controls on server
├── update_controls.py   # Updates existing controls (allow/block SSN)
├── demo_agent.py        # Demo agent with regex/list controls
└── agent_luna_demo.py   # Demo agent with Luna2 plugin controls
```

## Troubleshooting

If controls aren't being applied:

1. **Check server is running**: `cd server && make run`
2. **Verify controls exist**: `uv run python examples/agent_control_demo/setup_controls.py --verify-only`
3. **Fresh start**: Delete `server/agent_control.db` and re-run `setup_controls.py`

## Expected Demo Output

```
📝 TEST: Dangerous SQL - DROP TABLE
Input: "DROP TABLE users"

🚫 BLOCKED by control: block-dangerous-sql
   Reason: Control triggered. Logic: any, MatchOn: match. Matched values: DROP.

📝 TEST: Chat Request That Would Leak SSN
Input: "Tell me the user info"

🚫 BLOCKED by control: block-ssn-output
   Reason: Regex match found: \b\d{3}-\d{2}-\d{4}\b
```
