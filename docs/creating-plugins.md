# Creating Plugins

A plugin is a function that receives the full `Agent` instance. It can register tools, add hooks, and modify config.

## Basic plugin

```python
# my_plugin.py
from tinyloom import Agent

def activate(agent: Agent):
    """Called when the plugin is loaded."""
    print(f"Plugin loaded! Model: {agent.config.model.model}")
```

## Registering tools

```python
from tinyloom import Agent, Tool

def activate(agent: Agent):
    agent.tools.register(Tool(
        name="timestamp",
        description="Return the current UTC timestamp",
        input_schema={"type": "object", "properties": {}},
        function=lambda inp: __import__("datetime").datetime.utcnow().isoformat(),
    ))
```

## Adding hooks

```python
from tinyloom import Agent

def activate(agent: Agent):
    def log_tool_calls(ctx):
        if ctx.get("tool_name"):
            print(f"[audit] tool called: {ctx['tool_name']}")

    agent.hooks.on("tool_call", log_tool_calls)
```

## Modifying config

```python
def activate(agent: Agent):
    agent.config.max_turns = 50
```

## Activation

### Via config (recommended)

Add the module path to `tinyloom.yaml`:

```yaml
plugins:
  - my_plugin                    # calls my_plugin.activate(agent)
  - mypackage.plugins.custom     # calls mypackage.plugins.custom.activate(agent)
  - mypackage.stuff:setup        # calls mypackage.stuff.setup(agent)
```

By default, tinyloom calls the `activate` function. Use `:function_name` to specify a different entry point.

### Via entry_points (for distributable packages)

In your package's `pyproject.toml`:

```toml
[project.entry-points."tinyloom.plugins"]
my-plugin = "my_package.plugin:activate"
```

Entry point plugins are discovered automatically when installed -- no config needed.

## Example: logging plugin

A plugin that logs every tool call and result to a file:

```python
import json
from pathlib import Path
from tinyloom import Agent

def activate(agent: Agent):
    log_file = Path("tinyloom-audit.jsonl")

    def log_tool_call(ctx):
        entry = {
            "event": "tool_call",
            "tool": ctx.get("tool_name", ""),
            "input": str(ctx.get("tool_call", "")),
        }
        with log_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_tool_result(ctx):
        entry = {
            "event": "tool_result",
            "tool": ctx.get("tool_name", ""),
            "result_preview": str(ctx.get("result", ""))[:200],
        }
        with log_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    agent.hooks.on("tool_call", log_tool_call)
    agent.hooks.on("tool_result", log_tool_result)
```
