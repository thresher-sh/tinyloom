from __future__ import annotations
import json, subprocess, sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent

def activate(agent: Agent):
    hook_scripts = agent.config.hook_scripts
    if not hook_scripts: return
    for event_name, commands in hook_scripts.items():
        for cmd_config in commands:
            command = cmd_config if isinstance(cmd_config, str) else cmd_config.get("command", "")
            if command: agent.hooks.on(event_name, _make_hook(command))

def _make_hook(cmd: str):
    def hook(ctx: dict):
        ctx_json = _serialize_ctx(ctx)
        try:
            result = subprocess.run(cmd, shell=True, input=ctx_json, capture_output=True, text=True, timeout=30)
            if result.returncode == 2:
                ctx["skip"] = True
                ctx["reason"] = result.stdout.strip()
            elif result.returncode != 0:
                print(f"Hook script error ({cmd}): {result.stderr}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"Hook script timed out ({cmd})", file=sys.stderr)
        except Exception as e:
            print(f"Hook script failed ({cmd}): {e}", file=sys.stderr)
    return hook

def _serialize_ctx(ctx: dict) -> str:
    safe = {}
    for k, v in ctx.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = str(v)
    return json.dumps(safe)
