# Custom Hooks

Hooks let you react to agent events programmatically. Register them with `HookRunner.on(event, fn)`.

## Registering hooks

```python
from tinyloom import Agent, HookRunner, load_config

hooks = HookRunner()

def my_hook(ctx):
    print(f"Event: {ctx['type']}")

hooks.on("tool_call", my_hook)

agent = Agent(load_config(), hooks=hooks)
```

Or from within a plugin:

```python
def activate(agent):
    agent.hooks.on("tool_call", my_hook)
```

## Available events

| Event | When it fires | Key ctx fields |
|-------|--------------|----------------|
| `agent_start` | Agent begins a run | `type` |
| `agent_stop` | Agent finishes | `type` |
| `text_delta` | LLM streams a text chunk | `type`, `text` |
| `tool_call` | LLM requests a tool | `type`, `tool_name`, `tool_call` |
| `tool_result` | Tool execution completed | `type`, `tool_name`, `result` |
| `compaction` | Context was compacted | `type` |
| `response_complete` | LLM finished responding | `type`, `message` |
| `error` | Something went wrong | `type`, `error` |
| `message:user` | User message appended | `type`, `message` |
| `message:assistant` | Assistant message appended | `type`, `message` |
| `message:tool_result` | Tool result message appended | `type`, `message` |

## The ctx dict

Every hook receives a mutable `ctx` dict. You can read, modify, or cancel:

```python
def my_hook(ctx):
    # Read
    tool_name = ctx.get("tool_name", "")

    # Cancel the event
    ctx["skip"] = True
```

Setting `ctx["skip"] = True` has these effects:

- **`tool_call`**: skips tool execution, returns a denial message to the LLM
- **`text_delta`**: suppresses the text event from reaching consumers
- **Other events**: suppresses the event from being yielded

## Sync and async hooks

Both sync and async functions work. Async hooks are awaited automatically:

```python
def sync_hook(ctx):
    print(f"tool: {ctx['tool_name']}")

async def async_hook(ctx):
    await some_async_operation(ctx)

hooks.on("tool_call", sync_hook)
hooks.on("tool_call", async_hook)
```

## Error handling

Hook exceptions are caught and logged to stderr. They never crash the agent:

```
Hook error (tool_call): division by zero
```

## Config-based hooks

You can also register hooks via `tinyloom.yaml` using dotted import paths:

```yaml
hooks:
  tool_call:
    - mypackage.hooks.approve_writes
  message:user:
    - mypackage.hooks.log_input
```

Each path is `module.path.function_name`. The function is imported and registered at startup.

## Example: approval gate

Block dangerous tools unless the user confirms:

```python
DANGEROUS = {"bash", "write", "edit"}

def approve_dangerous(ctx):
    tool_name = ctx.get("tool_name", "")
    if tool_name not in DANGEROUS:
        return

    tool_call = ctx.get("tool_call")
    preview = str(tool_call.input)[:200] if tool_call else ""
    answer = input(f"Allow {tool_name}({preview})? [y/N] ")
    if answer.lower() != "y":
        ctx["skip"] = True
```

Register it:

```python
agent.hooks.on("tool_call", approve_dangerous)
```

## Example: logging hook

Log all events to a file:

```python
import json
from pathlib import Path

LOG = Path("agent-events.jsonl")

def log_all(ctx):
    safe = {k: str(v)[:500] for k, v in ctx.items()}
    with LOG.open("a") as f:
        f.write(json.dumps(safe) + "\n")

# Register for every event type you care about
for event in ("tool_call", "tool_result", "text_delta", "error"):
    hooks.on(event, log_all)
```
