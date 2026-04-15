from __future__ import annotations
import inspect, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from tinyloom.core.types import ToolDef  # re-export for convenience

__all__ = ["Tool", "ToolRegistry", "tool", "ToolDef", "get_builtin_tools"]

@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    function: Callable[[dict], Any]

    def to_def(self) -> ToolDef:
        return ToolDef(name=self.name, description=self.description, input_schema=self.input_schema)

def tool(name: str, description: str, input_schema: dict):
    def decorator(fn: Callable[[dict], str]) -> Tool:
        return Tool(name=name, description=description, input_schema=input_schema, function=fn)
    return decorator

class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {t.name: t for t in tools} if tools else {}

    def register(self, t: Tool):
        self._tools[t.name] = t

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all_defs(self) -> list[ToolDef]:
        return [t.to_def() for t in self._tools.values()]

    async def execute(self, name: str, input_data: dict) -> str:
        t = self._tools.get(name)
        if not t:
            return f"Error: unknown tool '{name}'"
        try:
            result = t.function(input_data)
            if inspect.isawaitable(result):
                result = await result
            return str(result)
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

@tool(
    "read",
    "Read file contents. Adds line numbers for files longer than 50 lines.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to file"},
        },
        "required": ["path"],
    },
)
def _read_tool(input_data: dict) -> str:
    path = Path(input_data["path"])
    if not path.exists():
        return f"Error: file not found: {path}"
    text = path.read_text(errors="replace")
    lines = text.splitlines(keepends=True)
    if len(lines) > 50:
        return "".join(f"{i + 1}\t{line}" for i, line in enumerate(lines))
    return text

@tool(
    "write",
    "Write content to a file, creating parent directories as needed.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
)
def _write_tool(input_data: dict) -> str:
    path = Path(input_data["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(input_data["content"])
    return f"Written: {path}"

@tool(
    "edit",
    "Replace an exact string in a file (str_replace). old_str must match exactly once. "
    "If old_str is empty and the file does not exist, creates it with new_str as content.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to file"},
            "old_str": {"type": "string", "description": "Exact string to find and replace"},
            "new_str": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_str", "new_str"],
    },
)
def _edit_tool(input_data: dict) -> str:
    path = Path(input_data["path"])
    old_str = input_data["old_str"]
    new_str = input_data["new_str"]

    if old_str == "" and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_str)
        return f"Created: {path}"

    if old_str == new_str:
        return "Error: old_str and new_str are identical — no change would be made"

    text = path.read_text(errors="replace")
    count = text.count(old_str)
    if count == 0:
        return f"Error: old_str not found in {path}"
    if count > 1:
        return f"Error: old_str matched {count} times in {path} — must match exactly once"

    path.write_text(text.replace(old_str, new_str, 1))
    return f"Edited: {path}"

@tool(
    "bash",
    "Run a shell command. Returns stdout and stderr combined. Supports optional timeout in seconds.",
    {
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "number", "description": "Timeout in seconds (default 120)"},
        },
        "required": ["cmd"],
    },
)
def _bash_tool(input_data: dict) -> str:
    cmd = input_data["cmd"]
    timeout = input_data.get("timeout", 120)
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + (proc.stderr or "")
        if proc.returncode != 0: output += f"\n[exit code: {proc.returncode}]"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"Error: Timeout after {timeout}s"

def get_builtin_tools() -> list[Tool]:
    return [_read_tool, _write_tool, _edit_tool, _bash_tool]
