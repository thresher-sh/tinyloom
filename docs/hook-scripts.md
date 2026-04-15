# Hook Scripts

The `hook_scripts` plugin lets you run shell commands as hooks. Scripts receive event context as JSON on stdin and use exit codes to control behavior.

## Enable the plugin

Add `tinyloom.plugins.hook_scripts` to your plugins list in `tinyloom.yaml`:

```yaml
plugins:
  - tinyloom.plugins.hook_scripts
```

## Config format

Define hook scripts in `tinyloom.yaml` under `hook_scripts`:

```yaml
hook_scripts:
  tool_call:
    - command: "./hooks/approve-tool.sh"
    - command: "python hooks/audit.py"
  message:user:
    - command: "./hooks/input-filter.sh"
```

Each key is an event name (same events as [custom hooks](custom-hooks.md)). Each entry has a `command` that is run via the shell.

## How scripts work

1. The script receives the hook context as JSON on **stdin**
2. The script's **exit code** determines what happens:

| Exit code | Behavior |
|-----------|----------|
| `0` | Pass -- event continues normally |
| `1` | Error -- logged to stderr, event continues |
| `2` | Deny -- sets `ctx["skip"] = True`, stdout is used as the denial reason |

3. Scripts have a **30-second timeout**. Timeouts are logged and the event continues.

## Stdin JSON format

The JSON object contains the same fields as the hook `ctx` dict. Example for a `tool_call` event:

```json
{
  "type": "tool_call",
  "tool_name": "bash",
  "tool_call": "ToolCall(id='tc_01', name='bash', input={'cmd': 'rm -rf /'})"
}
```

Non-serializable values are converted to strings.

## Example: block dangerous commands

A bash script that blocks `rm -rf`:

```bash
#!/bin/bash
# hooks/approve-tool.sh

# Read JSON context from stdin
ctx=$(cat)

# Extract the tool call input
tool_name=$(echo "$ctx" | jq -r '.tool_name // ""')
tool_input=$(echo "$ctx" | jq -r '.tool_call // ""')

# Block rm -rf
if [ "$tool_name" = "bash" ] && echo "$tool_input" | grep -q "rm -rf"; then
    echo "Blocked: rm -rf is not allowed"
    exit 2
fi

exit 0
```

Make it executable:

```bash
chmod +x hooks/approve-tool.sh
```

Config:

```yaml
plugins:
  - tinyloom.plugins.hook_scripts

hook_scripts:
  tool_call:
    - command: "./hooks/approve-tool.sh"
```

## Example: Python audit logger

A Python script that logs all tool calls:

```python
#!/usr/bin/env python3
# hooks/audit.py

import json
import sys
from datetime import datetime

ctx = json.load(sys.stdin)

entry = {
    "timestamp": datetime.utcnow().isoformat(),
    "event": ctx.get("type"),
    "tool": ctx.get("tool_name", ""),
}

with open("audit.jsonl", "a") as f:
    f.write(json.dumps(entry) + "\n")

sys.exit(0)
```

Config:

```yaml
hook_scripts:
  tool_call:
    - command: "python hooks/audit.py"
  tool_result:
    - command: "python hooks/audit.py"
```
