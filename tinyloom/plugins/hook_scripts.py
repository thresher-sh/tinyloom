from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


def activate(agent: Agent):
    """Register shell command hooks from config."""
    hook_scripts = agent.config.hook_scripts
    if not hook_scripts:
        return

    for event_name, commands in hook_scripts.items():
        for cmd_config in commands:
            command = cmd_config if isinstance(cmd_config, str) else cmd_config.get("command", "")
            if not command:
                continue

            agent.hooks.on(event_name, _make_hook(command))


def _make_hook(cmd: str):
    """Create a hook function that runs a shell command."""
    def hook(ctx: dict):
        ctx_json = _serialize_ctx(ctx)
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                input=ctx_json,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                pass  # Hook passes
            elif result.returncode == 2:
                reason = result.stdout.strip()
                ctx["skip"] = True
                ctx["reason"] = reason
            else:
                # Exit 1 or any other non-zero code: log error, continue
                print(f"Hook script error ({cmd}): {result.stderr}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"Hook script timed out ({cmd})", file=sys.stderr)
        except Exception as e:
            print(f"Hook script failed ({cmd}): {e}", file=sys.stderr)
    return hook


def _serialize_ctx(ctx: dict) -> str:
    """Serialize hook context to JSON, handling non-serializable objects."""
    safe = {}
    for k, v in ctx.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = str(v)
    return json.dumps(safe)
