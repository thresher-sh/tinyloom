# tinyloom Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build tinyloom, a tiny SDK-first coding agent harness in Python with Anthropic/OpenAI support, built-in tools, hooks, plugins, compaction, CLI, and TUI.

**Architecture:** Layered core (SDK in `tinyloom/core/`), provider adapters wrapping official SDKs, opt-in plugins, thin CLI + Textual TUI. The agent loop is an async iterator yielding events consumed by all layers.

**Tech Stack:** Python 3.11+, anthropic/openai SDKs, pyyaml, textual, ripgrep, tiktoken, uv for tooling.

**Spec:** `docs/superpowers/specs/2026-04-15-tinyloom-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package metadata, deps, entry points |
| `tinyloom/__init__.py` | Public API exports |
| `tinyloom/__main__.py` | `python -m tinyloom` entry |
| `tinyloom/core/__init__.py` | Core package init |
| `tinyloom/core/types.py` | Message, ToolCall, StreamEvent, AgentEvent, ToolDef |
| `tinyloom/core/config.py` | Config dataclasses + YAML loader |
| `tinyloom/core/hooks.py` | HookRunner |
| `tinyloom/core/tools.py` | Tool, ToolRegistry, @tool decorator, all 6 built-in tools |
| `tinyloom/core/compact.py` | Context compaction (summarize/truncate) |
| `tinyloom/core/agent.py` | Agent class + the loop |
| `tinyloom/providers/__init__.py` | Provider package init |
| `tinyloom/providers/base.py` | LLMProvider protocol |
| `tinyloom/providers/anthropic.py` | Anthropic SDK wrapper |
| `tinyloom/providers/openai.py` | OpenAI SDK wrapper |
| `tinyloom/plugins/__init__.py` | Plugin loader |
| `tinyloom/plugins/todo.py` | Todo middleware plugin |
| `tinyloom/plugins/mcp.py` | MCP tool extension plugin |
| `tinyloom/cli.py` | CLI entry point |
| `tinyloom/tui.py` | Textual TUI |
| `tests/test_types.py` | Types tests |
| `tests/test_config.py` | Config tests |
| `tests/test_hooks.py` | Hooks tests |
| `tests/test_tools.py` | Tool system + built-in tools tests |
| `tests/test_providers.py` | Provider tests (mocked SDKs) |
| `tests/test_agent.py` | Agent loop tests (mocked provider) |
| `tests/test_compact.py` | Compaction tests |
| `tests/test_plugins.py` | Plugin loader + todo plugin tests |
| `tests/test_cli.py` | CLI arg parsing + mode tests |

---

## Chunk 1: Project Scaffolding + Core Types + Config + Hooks

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `tinyloom/__init__.py`
- Create: `tinyloom/__main__.py`
- Create: `tinyloom/core/__init__.py`
- Create: `tinyloom/providers/__init__.py`
- Create: `tinyloom/plugins/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "tinyloom"
version = "0.1.0"
description = "A tiny, SDK-first coding agent harness"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40",
    "openai>=1.50",
    "pyyaml>=6.0",
    "textual>=1.0",
    "ripgrep>=0.1",
    "tiktoken>=0.7",
]

[project.optional-dependencies]
mcp = ["mcp>=1.0,<2"]
dev = ["pytest", "pytest-asyncio", "ruff"]

[project.scripts]
tinyloom = "tinyloom.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create package init files**

`tinyloom/__init__.py`:
```python
"""tinyloom - A tiny, SDK-first coding agent harness."""

__version__ = "0.1.0"
```

`tinyloom/__main__.py`:
```python
from tinyloom.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

`tinyloom/core/__init__.py`:
```python
```

`tinyloom/providers/__init__.py`:
```python
```

`tinyloom/plugins/__init__.py` (placeholder, real implementation in Task 13):
```python
```

- [ ] **Step 3: Install dev deps and verify**

Run: `uv sync --extra dev`
Expected: installs all deps successfully

- [ ] **Step 4: Verify basic import works**

Run: `uv run python -c "import tinyloom; print(tinyloom.__version__)"`
Expected: `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tinyloom/ tests/
git commit -m "Scaffold project structure"
```

---

### Task 2: Core Types

**Files:**
- Create: `tinyloom/core/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write failing tests for core types**

`tests/test_types.py`:
```python
from tinyloom.core.types import Message, ToolCall, StreamEvent, AgentEvent, ToolDef


class TestMessage:
    def test_user_message_minimal(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_calls == []
        assert msg.tool_call_id == ""
        assert msg.name == ""

    def test_assistant_message_with_tool_calls(self):
        tc = ToolCall(id="tc_01", name="read", input={"path": "foo.py"})
        msg = Message(role="assistant", content="Let me read that.", tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "read"

    def test_tool_result_message(self):
        msg = Message(role="tool_result", content="file contents", tool_call_id="tc_01", name="read")
        assert msg.tool_call_id == "tc_01"
        assert msg.name == "read"


class TestToolCall:
    def test_creation(self):
        tc = ToolCall(id="tc_01", name="bash", input={"command": "ls"})
        assert tc.id == "tc_01"
        assert tc.name == "bash"
        assert tc.input == {"command": "ls"}


class TestToolDef:
    def test_creation(self):
        td = ToolDef(
            name="read",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        assert td.name == "read"
        assert td.description == "Read a file"


class TestStreamEvent:
    def test_text_event(self):
        evt = StreamEvent(type="text", text="hello")
        assert evt.type == "text"
        assert evt.text == "hello"
        assert evt.tool_call is None

    def test_tool_call_event(self):
        tc = ToolCall(id="tc_01", name="read", input={})
        evt = StreamEvent(type="tool_call", tool_call=tc)
        assert evt.tool_call.name == "read"

    def test_done_event(self):
        msg = Message(role="assistant", content="done")
        evt = StreamEvent(type="done", message=msg)
        assert evt.message.content == "done"

    def test_error_event(self):
        evt = StreamEvent(type="error", error="API failed")
        assert evt.error == "API failed"


class TestAgentEvent:
    def test_text_delta(self):
        evt = AgentEvent(type="text_delta", text="hello")
        assert evt.type == "text_delta"

    def test_to_dict_drops_empty_fields(self):
        evt = AgentEvent(type="agent_start")
        d = evt.to_dict()
        assert d == {"type": "agent_start"}
        assert "text" not in d
        assert "tool_call" not in d

    def test_to_dict_includes_populated_fields(self):
        evt = AgentEvent(type="text_delta", text="hello")
        d = evt.to_dict()
        assert d == {"type": "text_delta", "text": "hello"}

    def test_to_dict_tool_call(self):
        tc = ToolCall(id="tc_01", name="read", input={"path": "x"})
        evt = AgentEvent(type="tool_call", tool_call=tc)
        d = evt.to_dict()
        assert d["tool_call"] == {"id": "tc_01", "name": "read", "input": {"path": "x"}}

    def test_to_dict_tool_result(self):
        evt = AgentEvent(type="tool_result", tool_call_id="tc_01", tool_name="read", result="contents")
        d = evt.to_dict()
        assert d["tool_call_id"] == "tc_01"
        assert d["tool_name"] == "read"
        assert d["result"] == "contents"

    def test_to_dict_response_complete(self):
        msg = Message(role="assistant", content="done")
        evt = AgentEvent(type="response_complete", message=msg)
        d = evt.to_dict()
        assert d["message"] == {"role": "assistant", "content": "done"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement core types**

`tinyloom/core/types.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict


@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


@dataclass
class StreamEvent:
    type: str
    text: str = ""
    tool_call: ToolCall | None = None
    message: Message | None = None
    error: str = ""


@dataclass
class AgentEvent:
    type: str
    text: str = ""
    tool_call: ToolCall | None = None
    tool_call_id: str = ""
    tool_name: str = ""
    result: str = ""
    message: Message | None = None
    error: str = ""

    def to_dict(self) -> dict:
        d: dict = {"type": self.type}
        if self.text:
            d["text"] = self.text
        if self.tool_call is not None:
            d["tool_call"] = {
                "id": self.tool_call.id,
                "name": self.tool_call.name,
                "input": self.tool_call.input,
            }
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.result:
            d["result"] = self.result
        if self.message is not None:
            d["message"] = {"role": self.message.role, "content": self.message.content}
        if self.error:
            d["error"] = self.error
        return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_types.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/core/types.py tests/test_types.py
git commit -m "Add core types: Message, ToolCall, StreamEvent, AgentEvent"
```

---

### Task 3: Config

**Files:**
- Create: `tinyloom/core/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config**

`tests/test_config.py`:
```python
import os
import tempfile
from pathlib import Path

from tinyloom.core.config import Config, ModelConfig, CompactionConfig, load_config


class TestConfigDefaults:
    def test_config_all_defaults(self):
        cfg = Config()
        assert cfg.model.provider == "anthropic"
        assert cfg.model.model == "claude-sonnet-4-20250514"
        assert cfg.model.base_url is None
        assert cfg.model.max_tokens == 8192
        assert cfg.model.context_window == 200_000
        assert cfg.model.temperature == 0.0
        assert cfg.compaction.enabled is True
        assert cfg.compaction.threshold == 0.8
        assert cfg.compaction.strategy == "summarize"
        assert cfg.plugins == []
        assert cfg.hooks == {}
        assert cfg.max_turns == 200

    def test_model_config_defaults(self):
        mc = ModelConfig()
        assert mc.provider == "anthropic"

    def test_compaction_config_defaults(self):
        cc = CompactionConfig()
        assert cc.enabled is True
        assert cc.strategy == "summarize"


class TestLoadConfig:
    def test_load_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = load_config()
        assert cfg.model.provider == "anthropic"

    def test_load_from_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_content = """
model:
  provider: openai
  model: gpt-4o
  max_tokens: 4096
compaction:
  threshold: 0.7
max_turns: 50
"""
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.model.provider == "openai"
        assert cfg.model.model == "gpt-4o"
        assert cfg.model.max_tokens == 4096
        assert cfg.compaction.threshold == 0.7
        assert cfg.max_turns == 50

    def test_load_from_explicit_path(self, tmp_path):
        yaml_content = """
model:
  provider: openai
"""
        p = tmp_path / "custom.yaml"
        p.write_text(yaml_content)
        cfg = load_config(p)
        assert cfg.model.provider == "openai"

    def test_env_var_overrides_api_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        cfg = load_config()
        assert cfg.model.api_key == "sk-test-123"

    def test_env_var_openai_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_content = """
model:
  provider: openai
"""
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-123")
        cfg = load_config()
        assert cfg.model.api_key == "sk-openai-123"

    def test_partial_yaml_keeps_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_content = """
max_turns: 10
"""
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.max_turns == 10
        assert cfg.model.provider == "anthropic"
        assert cfg.compaction.enabled is True

    def test_system_prompt_from_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_content = """
system_prompt: "You are a helpful assistant."
"""
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.system_prompt == "You are a helpful assistant."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement config**

`tinyloom/core/config.py`:
```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int = 8192
    context_window: int = 200_000
    temperature: float = 0.0


@dataclass
class CompactionConfig:
    enabled: bool = True
    threshold: float = 0.8
    strategy: str = "summarize"


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    system_prompt: str = "You are a skilled coding assistant. Be concise."
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
    plugins: list[str] = field(default_factory=list)
    hooks: dict[str, list[str]] = field(default_factory=dict)
    max_turns: int = 200


def load_config(path: str | Path | None = None) -> Config:
    raw = _load_yaml(path)
    cfg = Config()

    if "model" in raw:
        for k, v in raw["model"].items():
            if hasattr(cfg.model, k):
                setattr(cfg.model, k, v)

    if "compaction" in raw:
        for k, v in raw["compaction"].items():
            if hasattr(cfg.compaction, k):
                setattr(cfg.compaction, k, v)

    for k in ("system_prompt", "max_turns", "plugins", "hooks"):
        if k in raw:
            setattr(cfg, k, raw[k])

    _apply_env_vars(cfg)
    return cfg


def _load_yaml(path: str | Path | None) -> dict:
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path("tinyloom.yaml"))
    candidates.append(Path.home() / ".config" / "tinyloom" / "tinyloom.yaml")

    for p in candidates:
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    return {}


def _apply_env_vars(cfg: Config) -> None:
    if cfg.model.provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
    else:
        key = os.environ.get("OPENAI_API_KEY")
    if key:
        cfg.model.api_key = key
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/core/config.py tests/test_config.py
git commit -m "Add config system with YAML loading and env var overrides"
```

---

### Task 4: Hooks

**Files:**
- Create: `tinyloom/core/hooks.py`
- Create: `tests/test_hooks.py`

- [ ] **Step 1: Write failing tests for hooks**

`tests/test_hooks.py`:
```python
import asyncio
import pytest

from tinyloom.core.hooks import HookRunner


class TestHookRunner:
    @pytest.fixture
    def hooks(self):
        return HookRunner()

    @pytest.mark.asyncio
    async def test_register_and_emit_sync(self, hooks):
        calls = []
        hooks.on("test_event", lambda ctx: calls.append(ctx))
        await hooks.emit("test_event", {"data": "hello"})
        assert len(calls) == 1
        assert calls[0]["data"] == "hello"

    @pytest.mark.asyncio
    async def test_register_and_emit_async(self, hooks):
        calls = []

        async def async_hook(ctx):
            calls.append(ctx)

        hooks.on("test_event", async_hook)
        await hooks.emit("test_event", {"data": "hello"})
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_multiple_hooks_same_event(self, hooks):
        calls = []
        hooks.on("evt", lambda ctx: calls.append("a"))
        hooks.on("evt", lambda ctx: calls.append("b"))
        await hooks.emit("evt", {})
        assert calls == ["a", "b"]

    @pytest.mark.asyncio
    async def test_no_hooks_registered(self, hooks):
        await hooks.emit("nonexistent", {})

    @pytest.mark.asyncio
    async def test_hook_exception_logged_not_raised(self, hooks, capsys):
        def bad_hook(ctx):
            raise ValueError("boom")

        hooks.on("evt", bad_hook)
        await hooks.emit("evt", {})
        captured = capsys.readouterr()
        assert "boom" in captured.err

    @pytest.mark.asyncio
    async def test_hook_can_mutate_ctx(self, hooks):
        def mutator(ctx):
            ctx["modified"] = True

        hooks.on("evt", mutator)
        ctx = {"modified": False}
        await hooks.emit("evt", ctx)
        assert ctx["modified"] is True

    @pytest.mark.asyncio
    async def test_hook_can_set_skip(self, hooks):
        def skipper(ctx):
            ctx["skip"] = True

        hooks.on("evt", skipper)
        ctx = {}
        await hooks.emit("evt", ctx)
        assert ctx.get("skip") is True

    @pytest.mark.asyncio
    async def test_register_from_config(self, hooks, tmp_path, monkeypatch):
        # Create a temporary module with a hook function
        mod_file = tmp_path / "my_hooks.py"
        mod_file.write_text("def my_hook(ctx):\n    ctx['called'] = True\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        hooks.register_from_config({"evt": ["my_hooks.my_hook"]})
        ctx = {}
        await hooks.emit("evt", ctx)
        assert ctx["called"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hooks.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement hooks**

`tinyloom/core/hooks.py`:
```python
from __future__ import annotations

import importlib
import inspect
import sys
from typing import Any, Callable


HookFn = Callable[..., Any]


class HookRunner:
    def __init__(self):
        self._hooks: dict[str, list[HookFn]] = {}

    def on(self, event: str, fn: HookFn):
        self._hooks.setdefault(event, []).append(fn)

    async def emit(self, event: str, ctx: dict) -> dict:
        for fn in self._hooks.get(event, []):
            try:
                result = fn(ctx)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                print(f"Hook error ({event}): {e}", file=sys.stderr)
        return ctx

    def register_from_config(self, config_hooks: dict[str, list[str]]):
        for event, paths in config_hooks.items():
            for dotted_path in paths:
                try:
                    module_path, _, func_name = dotted_path.rpartition(".")
                    module = importlib.import_module(module_path)
                    fn = getattr(module, func_name)
                    self.on(event, fn)
                except Exception as e:
                    print(f"Hook load error ({dotted_path}): {e}", file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hooks.py -v`
Expected: all PASS

- [ ] **Step 5: Update public API exports**

`tinyloom/__init__.py`:
```python
"""tinyloom - A tiny, SDK-first coding agent harness."""

__version__ = "0.1.0"

from tinyloom.core.types import Message, ToolCall, StreamEvent, AgentEvent, ToolDef
from tinyloom.core.config import Config, ModelConfig, CompactionConfig, load_config
from tinyloom.core.hooks import HookRunner
```

- [ ] **Step 6: Commit**

```bash
git add tinyloom/core/hooks.py tests/test_hooks.py tinyloom/__init__.py
git commit -m "Add hook system with sync/async support, mutation, and skip"
```

---

## Chunk 2: Tool System + Built-in Tools

### Task 5: Tool System (Registry + Decorator)

**Files:**
- Create: `tinyloom/core/tools.py` (just the system, not built-ins yet)
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests for tool system**

`tests/test_tools.py`:
```python
import pytest

from tinyloom.core.tools import Tool, ToolRegistry, tool, ToolDef


class TestTool:
    def test_tool_creation(self):
        t = Tool(
            name="test",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
            function=lambda inp: "ok",
        )
        assert t.name == "test"

    def test_tool_to_def(self):
        t = Tool(
            name="test",
            description="A test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            function=lambda inp: "ok",
        )
        td = t.to_def()
        assert isinstance(td, ToolDef)
        assert td.name == "test"
        assert td.description == "A test tool"
        assert td.input_schema == t.input_schema


class TestToolDecorator:
    def test_decorator_creates_tool(self):
        @tool(
            name="greet",
            description="Say hello",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        )
        def greet(inp):
            return f"Hello, {inp['name']}!"

        assert isinstance(greet, Tool)
        assert greet.name == "greet"
        assert greet.function({"name": "World"}) == "Hello, World!"


class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_register_and_get(self, registry):
        t = Tool(name="test", description="", input_schema={}, function=lambda i: "ok")
        registry.register(t)
        assert registry.get("test") is t

    def test_get_unknown_returns_none(self, registry):
        assert registry.get("nonexistent") is None

    def test_all_defs(self, registry):
        t1 = Tool(name="a", description="A", input_schema={}, function=lambda i: "")
        t2 = Tool(name="b", description="B", input_schema={}, function=lambda i: "")
        registry.register(t1)
        registry.register(t2)
        defs = registry.all_defs()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"a", "b"}

    @pytest.mark.asyncio
    async def test_execute_success(self, registry):
        t = Tool(name="echo", description="", input_schema={}, function=lambda i: i["msg"])
        registry.register(t)
        result = await registry.execute("echo", {"msg": "hello"})
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, registry):
        result = await registry.execute("nonexistent", {})
        assert "Error" in result
        assert "nonexistent" in result

    @pytest.mark.asyncio
    async def test_execute_catches_exceptions(self, registry):
        def bad_tool(inp):
            raise RuntimeError("boom")

        t = Tool(name="bad", description="", input_schema={}, function=bad_tool)
        registry.register(t)
        result = await registry.execute("bad", {})
        assert "Error" in result
        assert "boom" in result

    @pytest.mark.asyncio
    async def test_execute_async_tool(self, registry):
        async def async_tool(inp):
            return "async result"

        t = Tool(name="async_t", description="", input_schema={}, function=async_tool)
        registry.register(t)
        result = await registry.execute("async_t", {})
        assert result == "async result"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement tool system**

Add to top of `tinyloom/core/tools.py`:
```python
from __future__ import annotations

import inspect
from dataclasses import dataclass
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
        return ToolDef(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )


def tool(name: str, description: str, input_schema: dict):
    def decorator(fn: Callable[[dict], str]) -> Tool:
        return Tool(name=name, description=description, input_schema=input_schema, function=fn)
    return decorator


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/core/tools.py tests/test_tools.py
git commit -m "Add tool system: Tool, ToolRegistry, @tool decorator"
```

---

### Task 6: Built-in Tools (read, write, edit, grep, bash)

**Files:**
- Modify: `tinyloom/core/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests for built-in tools**

Append to `tests/test_tools.py`:
```python
import os
import subprocess

from tinyloom.core.tools import get_builtin_tools


class TestBuiltinRead:
    def test_read_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["read"].function({"path": str(f)})
        assert "line1" in result
        assert "line2" in result

    def test_read_file_not_found(self, tmp_path):
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["read"].function({"path": str(tmp_path / "nope.txt")})
        assert "Error" in result or "not found" in result.lower()

    def test_read_adds_line_numbers(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("\n".join(f"line {i}" for i in range(100)))
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["read"].function({"path": str(f)})
        assert "1" in result


class TestBuiltinWrite:
    def test_write_new_file(self, tmp_path):
        target = tmp_path / "new.txt"
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["write"].function({"path": str(target), "content": "hello world"})
        assert target.read_text() == "hello world"
        assert "Successfully" in result or "wrote" in result.lower()

    def test_write_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c.txt"
        tools = {t.name: t for t in get_builtin_tools()}
        tools["write"].function({"path": str(target), "content": "deep"})
        assert target.read_text() == "deep"


class TestBuiltinEdit:
    def test_edit_replace(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("hello world")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["edit"].function({"path": str(f), "old_str": "world", "new_str": "earth"})
        assert f.read_text() == "hello earth"
        assert "Successfully" in result or "edited" in result.lower()

    def test_edit_no_match(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("hello world")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["edit"].function({"path": str(f), "old_str": "xyz", "new_str": "abc"})
        assert "not found" in result.lower() or "error" in result.lower()

    def test_edit_multiple_matches(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("aa aa aa")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["edit"].function({"path": str(f), "old_str": "aa", "new_str": "bb"})
        assert "3 times" in result or "multiple" in result.lower() or "error" in result.lower()

    def test_edit_create_new_file(self, tmp_path):
        f = tmp_path / "brand_new.txt"
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["edit"].function({"path": str(f), "old_str": "", "new_str": "new content"})
        assert f.read_text() == "new content"

    def test_edit_same_old_new(self, tmp_path):
        f = tmp_path / "same.txt"
        f.write_text("hello")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["edit"].function({"path": str(f), "old_str": "hello", "new_str": "hello"})
        assert "error" in result.lower() or "different" in result.lower()


class TestBuiltinGrep:
    def test_grep_finds_pattern(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    return 'world'\n")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["grep"].function({"pattern": "hello", "path": str(tmp_path)})
        assert "hello" in result

    def test_grep_no_matches(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    return 'world'\n")
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["grep"].function({"pattern": "zzzznothere", "path": str(tmp_path)})
        assert "no matches" in result.lower() or result.strip() == ""


class TestBuiltinBash:
    def test_bash_simple_command(self):
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["bash"].function({"command": "echo hello"})
        assert "hello" in result

    def test_bash_captures_stderr(self):
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["bash"].function({"command": "echo err >&2"})
        assert "err" in result

    def test_bash_nonzero_exit(self):
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["bash"].function({"command": "exit 1"})
        assert "exit code" in result.lower() or "1" in result

    def test_bash_timeout(self):
        tools = {t.name: t for t in get_builtin_tools()}
        result = tools["bash"].function({"command": "sleep 10", "timeout": 1})
        assert "timeout" in result.lower() or "timed out" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools.py -v -k "Builtin"`
Expected: FAIL with `ImportError` (get_builtin_tools not found)

- [ ] **Step 3: Implement built-in tools**

Append to `tinyloom/core/tools.py`:
```python
import subprocess
from pathlib import Path


# ── Built-in tools ──────────────────────────────────────────────────

@tool(
    name="read",
    description=(
        "Read the contents of a file at the given path. "
        "Returns line-numbered output for files over 50 lines. "
        "Always read a file before editing it."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
        },
        "required": ["path"],
    },
)
def _read_tool(inp: dict) -> str:
    p = Path(inp["path"])
    if not p.exists():
        return f"Error: file not found: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"
    content = p.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines(True)
    if len(lines) > 50:
        return "".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))
    return content


@tool(
    name="write",
    description=(
        "Write content to a file. Creates the file and parent directories if needed. "
        "WARNING: This overwrites the entire file. For partial edits, use the 'edit' tool."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write to"},
            "content": {"type": "string", "description": "Complete file content to write"},
        },
        "required": ["path", "content"],
    },
)
def _write_tool(inp: dict) -> str:
    p = Path(inp["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(inp["content"], encoding="utf-8")
    return f"Successfully wrote {len(inp['content'])} bytes to {p}"


@tool(
    name="edit",
    description=(
        "Edit a file by replacing an exact string match with new content. "
        "The old_str must match exactly ONE location in the file. "
        "If old_str is empty and the file doesn't exist, creates the file with new_str. "
        "Always read the file first to see the exact content before editing."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to edit"},
            "old_str": {"type": "string", "description": "Exact string to find (must be unique)"},
            "new_str": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_str", "new_str"],
    },
)
def _edit_tool(inp: dict) -> str:
    p = Path(inp["path"])
    old_str = inp["old_str"]
    new_str = inp["new_str"]

    if old_str == new_str:
        return "Error: old_str and new_str must be different"

    if not p.exists():
        if old_str == "":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new_str, encoding="utf-8")
            return f"Created new file: {p}"
        return f"Error: file not found: {p}"

    content = p.read_text(encoding="utf-8")
    count = content.count(old_str)
    if count == 0:
        return f"Error: old_str not found in {p}"
    if count > 1:
        return f"Error: old_str found {count} times in {p} (must be unique)"

    new_content = content.replace(old_str, new_str, 1)
    p.write_text(new_content, encoding="utf-8")
    return f"Successfully edited {p}"


@tool(
    name="grep",
    description=(
        "Search for a pattern in files. Uses ripgrep (rg) with grep as fallback. "
        "Returns matching lines with file paths and line numbers."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {"type": "string", "description": "Directory or file to search", "default": "."},
            "flags": {"type": "string", "description": "Additional flags, e.g. '-i'", "default": ""},
        },
        "required": ["pattern"],
    },
)
def _grep_tool(inp: dict) -> str:
    pattern = inp["pattern"]
    path = inp.get("path", ".")
    flags = inp.get("flags", "")

    for cmd_base in ["rg -n", "grep -rn"]:
        cmd = f"{cmd_base} {flags} {pattern!r} {path}"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode <= 1:
                return result.stdout.strip() or "No matches found."
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            return "Error: search timed out after 30s"
    return "Error: neither 'rg' nor 'grep' available"


@tool(
    name="bash",
    description=(
        "Execute a shell command and return its output. "
        "Use for running tests, git operations, listing directories, etc. "
        "Timeout: 120 seconds by default."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
        },
        "required": ["command"],
    },
)
def _bash_tool(inp: dict) -> str:
    cmd = inp["command"]
    timeout = inp.get("timeout", 120)
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"


def get_builtin_tools() -> list[Tool]:
    return [_read_tool, _write_tool, _edit_tool, _grep_tool, _bash_tool]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: all PASS

- [ ] **Step 5: Update public API exports**

Add to `tinyloom/__init__.py`:
```python
from tinyloom.core.tools import Tool, ToolRegistry, tool, get_builtin_tools
```

- [ ] **Step 6: Commit**

```bash
git add tinyloom/core/tools.py tests/test_tools.py tinyloom/__init__.py
git commit -m "Add built-in tools: read, write, edit, grep, bash"
```

---

## Chunk 3: Provider Layer

### Task 7: Provider Base Protocol

**Files:**
- Create: `tinyloom/providers/base.py`

- [ ] **Step 1: Implement provider protocol**

`tinyloom/providers/base.py`:
```python
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from tinyloom.core.types import Message, StreamEvent, ToolDef


@runtime_checkable
class LLMProvider(Protocol):
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]: ...

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 8192,
    ) -> Message:
        """Non-streaming completion. Used for compaction summaries.
        Default implementation collects from stream()."""
        ...

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int: ...
```

- [ ] **Step 2: Verify import**

Run: `uv run python -c "from tinyloom.providers.base import LLMProvider; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tinyloom/providers/base.py
git commit -m "Add LLMProvider protocol"
```

---

### Task 8: Anthropic Provider

**Files:**
- Create: `tinyloom/providers/anthropic.py`
- Create: `tests/test_providers.py`

- [ ] **Step 1: Write failing tests for Anthropic provider**

`tests/test_providers.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tinyloom.core.types import Message, ToolCall, ToolDef, StreamEvent
from tinyloom.core.config import ModelConfig


class TestAnthropicProvider:
    @pytest.fixture
    def config(self):
        return ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key="sk-test")

    def test_format_messages_user(self, config):
        from tinyloom.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(config)
        msgs = [Message(role="user", content="hello")]
        formatted = provider._format_messages(msgs)
        assert formatted == [{"role": "user", "content": "hello"}]

    def test_format_messages_tool_result(self, config):
        from tinyloom.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(config)
        msgs = [
            Message(role="assistant", content="", tool_calls=[ToolCall(id="tc_1", name="read", input={"path": "x"})]),
            Message(role="tool_result", content="file data", tool_call_id="tc_1", name="read"),
        ]
        formatted = provider._format_messages(msgs)
        # Tool results become user messages with tool_result content blocks
        assert formatted[-1]["role"] == "user"
        assert formatted[-1]["content"][0]["type"] == "tool_result"
        assert formatted[-1]["content"][0]["tool_use_id"] == "tc_1"

    def test_format_messages_merges_consecutive_user(self, config):
        from tinyloom.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(config)
        msgs = [
            Message(role="tool_result", content="result1", tool_call_id="tc_1", name="read"),
            Message(role="tool_result", content="result2", tool_call_id="tc_2", name="bash"),
        ]
        formatted = provider._format_messages(msgs)
        # Should be merged into one user message with two content blocks
        assert len(formatted) == 1
        assert len(formatted[0]["content"]) == 2

    def test_format_tools(self, config):
        from tinyloom.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(config)
        tools = [ToolDef(name="read", description="Read file", input_schema={"type": "object"})]
        formatted = provider._format_tools(tools)
        assert formatted[0]["name"] == "read"
        assert formatted[0]["input_schema"] == {"type": "object"}

    def test_format_assistant_with_tool_calls(self, config):
        from tinyloom.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(config)
        tc = ToolCall(id="tc_1", name="read", input={"path": "x.py"})
        msgs = [Message(role="assistant", content="Let me read that.", tool_calls=[tc])]
        formatted = provider._format_messages(msgs)
        content = formatted[0]["content"]
        # Should have text block + tool_use block
        assert any(b["type"] == "text" for b in content)
        assert any(b["type"] == "tool_use" for b in content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_providers.py -v -k "Anthropic"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement Anthropic provider**

`tinyloom/providers/anthropic.py`:
```python
from __future__ import annotations

import json
from typing import AsyncIterator

import anthropic

from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolCall, ToolDef


class AnthropicProvider:
    def __init__(self, config: ModelConfig):
        self.config = config
        self.client = anthropic.AsyncAnthropic(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": self._format_messages(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._format_tools(tools)
        kwargs["temperature"] = self.config.temperature

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                assistant_text = ""
                tool_calls: list[ToolCall] = []

                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            tool_calls.append(ToolCall(
                                id=event.content_block.id,
                                name=event.content_block.name,
                                input={},
                            ))
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            assistant_text += event.delta.text
                            yield StreamEvent(type="text", text=event.delta.text)
                        elif event.delta.type == "input_json_delta":
                            pass  # accumulated by SDK
                    elif event.type == "content_block_stop":
                        pass
                    elif event.type == "message_stop":
                        pass

                # Get the final message to extract complete tool call inputs
                final = await stream.get_final_message()
                tool_calls = []
                for block in final.content:
                    if block.type == "tool_use":
                        tc = ToolCall(id=block.id, name=block.name, input=block.input)
                        tool_calls.append(tc)
                        yield StreamEvent(type="tool_call", tool_call=tc)

                msg = Message(
                    role="assistant",
                    content=assistant_text,
                    tool_calls=tool_calls,
                )
                yield StreamEvent(type="done", message=msg)

        except anthropic.APIError as e:
            yield StreamEvent(type="error", error=str(e))

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 8192,
    ) -> Message:
        kwargs: dict = {
            "model": self.config.model,
            "max_tokens": max_tokens,
            "messages": self._format_messages(messages),
        }
        if system:
            kwargs["system"] = system
        kwargs["temperature"] = self.config.temperature
        response = await self.client.messages.create(**kwargs)
        content = "".join(b.text for b in response.content if b.type == "text")
        return Message(role="assistant", content=content)

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int:
        kwargs: dict = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
        }
        if system:
            kwargs["system"] = system
        result = await self.client.messages.count_tokens(**kwargs)
        return result.input_tokens

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        formatted: list[dict] = []

        for msg in messages:
            if msg.role == "assistant":
                content: list[dict] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })
                entry = {"role": "assistant", "content": content if content else msg.content}

            elif msg.role == "tool_result":
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content,
                }
                # Merge into previous user message if possible
                if formatted and formatted[-1]["role"] == "user" and isinstance(formatted[-1]["content"], list):
                    formatted[-1]["content"].append(block)
                    continue
                entry = {"role": "user", "content": [block]}

            else:
                entry = {"role": msg.role, "content": msg.content}

            # Merge consecutive same-role messages
            if formatted and formatted[-1]["role"] == entry["role"]:
                prev = formatted[-1]
                if isinstance(prev["content"], str):
                    prev["content"] = [{"type": "text", "text": prev["content"]}]
                if isinstance(entry["content"], str):
                    entry["content"] = [{"type": "text", "text": entry["content"]}]
                prev["content"].extend(entry["content"])
            else:
                formatted.append(entry)

        return formatted

    def _format_tools(self, tools: list[ToolDef]) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_providers.py -v -k "Anthropic"`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/providers/anthropic.py tests/test_providers.py
git commit -m "Add Anthropic provider with streaming and token counting"
```

---

### Task 9: OpenAI Provider

**Files:**
- Create: `tinyloom/providers/openai.py`
- Modify: `tests/test_providers.py`

- [ ] **Step 1: Write failing tests for OpenAI provider**

Append to `tests/test_providers.py`:
```python
class TestOpenAIProvider:
    @pytest.fixture
    def config(self):
        return ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test")

    def test_format_messages_user(self, config):
        from tinyloom.providers.openai import OpenAIProvider

        provider = OpenAIProvider(config)
        msgs = [Message(role="user", content="hello")]
        formatted = provider._format_messages(msgs, system="You are helpful.")
        assert formatted[0] == {"role": "system", "content": "You are helpful."}
        assert formatted[1] == {"role": "user", "content": "hello"}

    def test_format_messages_tool_result(self, config):
        from tinyloom.providers.openai import OpenAIProvider

        provider = OpenAIProvider(config)
        msgs = [Message(role="tool_result", content="file data", tool_call_id="call_1", name="read")]
        formatted = provider._format_messages(msgs)
        assert formatted[0]["role"] == "tool"
        assert formatted[0]["tool_call_id"] == "call_1"

    def test_format_messages_assistant_with_tool_calls(self, config):
        from tinyloom.providers.openai import OpenAIProvider

        provider = OpenAIProvider(config)
        tc = ToolCall(id="call_1", name="read", input={"path": "x.py"})
        msgs = [Message(role="assistant", content="Let me read.", tool_calls=[tc])]
        formatted = provider._format_messages(msgs)
        assert formatted[0]["tool_calls"][0]["id"] == "call_1"
        assert formatted[0]["tool_calls"][0]["function"]["name"] == "read"

    def test_format_tools(self, config):
        from tinyloom.providers.openai import OpenAIProvider

        provider = OpenAIProvider(config)
        tools = [ToolDef(name="read", description="Read file", input_schema={"type": "object"})]
        formatted = provider._format_tools(tools)
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "read"
        assert formatted[0]["function"]["parameters"] == {"type": "object"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_providers.py -v -k "OpenAI"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement OpenAI provider**

`tinyloom/providers/openai.py`:
```python
from __future__ import annotations

import json
from typing import AsyncIterator

import openai
import tiktoken

from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolCall, ToolDef


class OpenAIProvider:
    def __init__(self, config: ModelConfig):
        self.config = config
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": self._format_messages(messages, system),
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self._format_tools(tools)
        kwargs["temperature"] = self.config.temperature

        try:
            assistant_text = ""
            tool_call_accum: dict[int, dict] = {}

            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    assistant_text += delta.content
                    yield StreamEvent(type="text", text=delta.content)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_accum:
                            tool_call_accum[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name if tc_delta.function and tc_delta.function.name else "",
                                "arguments": "",
                            }
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_call_accum[idx]["arguments"] += tc_delta.function.arguments
                        if tc_delta.id:
                            tool_call_accum[idx]["id"] = tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            tool_call_accum[idx]["name"] = tc_delta.function.name

            tool_calls: list[ToolCall] = []
            for idx in sorted(tool_call_accum.keys()):
                acc = tool_call_accum[idx]
                inp = json.loads(acc["arguments"]) if acc["arguments"] else {}
                tc = ToolCall(id=acc["id"], name=acc["name"], input=inp)
                tool_calls.append(tc)
                yield StreamEvent(type="tool_call", tool_call=tc)

            msg = Message(role="assistant", content=assistant_text, tool_calls=tool_calls)
            yield StreamEvent(type="done", message=msg)

        except openai.APIError as e:
            yield StreamEvent(type="error", error=str(e))

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 8192,
    ) -> Message:
        kwargs: dict = {
            "model": self.config.model,
            "max_tokens": max_tokens,
            "messages": self._format_messages(messages, system),
        }
        kwargs["temperature"] = self.config.temperature
        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        return Message(role="assistant", content=content)

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int:
        text = system
        for msg in messages:
            text += msg.content
            for tc in msg.tool_calls:
                text += tc.name + json.dumps(tc.input)
        try:
            enc = tiktoken.encoding_for_model(self.config.model)
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def _format_messages(self, messages: list[Message], system: str = "") -> list[dict]:
        formatted: list[dict] = []
        if system:
            formatted.append({"role": "system", "content": system})

        for msg in messages:
            if msg.role == "assistant":
                entry: dict = {"role": "assistant", "content": msg.content or None}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.input)},
                        }
                        for tc in msg.tool_calls
                    ]
                formatted.append(entry)
            elif msg.role == "tool_result":
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
            else:
                formatted.append({"role": msg.role, "content": msg.content})

        return formatted

    def _format_tools(self, tools: list[ToolDef]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_providers.py -v -k "OpenAI"`
Expected: all PASS

- [ ] **Step 5: Add provider factory**

Update `tinyloom/providers/__init__.py`:
```python
from tinyloom.core.config import ModelConfig
from tinyloom.providers.base import LLMProvider


def create_provider(config: ModelConfig) -> LLMProvider:
    provider_type = config.provider
    if provider_type == "anthropic" or (not provider_type and "claude" in config.model):
        from tinyloom.providers.anthropic import AnthropicProvider
        return AnthropicProvider(config)
    else:
        from tinyloom.providers.openai import OpenAIProvider
        return OpenAIProvider(config)
```

- [ ] **Step 6: Update public API exports**

Add to `tinyloom/__init__.py`:
```python
from tinyloom.providers.base import LLMProvider
from tinyloom.providers import create_provider
```

- [ ] **Step 7: Commit**

```bash
git add tinyloom/providers/ tests/test_providers.py tinyloom/__init__.py
git commit -m "Add Anthropic and OpenAI providers with streaming and token counting"
```

---

## Chunk 4: Agent Loop + Compaction

### Task 10: Compaction

**Files:**
- Create: `tinyloom/core/compact.py`
- Create: `tests/test_compact.py`

- [ ] **Step 1: Write failing tests for compaction**

`tests/test_compact.py`:
```python
import pytest
from unittest.mock import AsyncMock

from tinyloom.core.types import Message
from tinyloom.core.compact import maybe_compact, estimate_tokens_heuristic


class TestEstimateTokens:
    def test_heuristic(self):
        msgs = [Message(role="user", content="a" * 400)]
        tokens = estimate_tokens_heuristic(msgs)
        assert tokens == 100  # 400 / 4


class TestMaybeCompact:
    @pytest.mark.asyncio
    async def test_no_compaction_below_threshold(self):
        provider = AsyncMock()
        provider.count_tokens = AsyncMock(return_value=1000)
        msgs = [Message(role="user", content="hello")]
        result = await maybe_compact(provider, msgs, context_window=200_000, threshold=0.8, strategy="summarize")
        assert result is None

    @pytest.mark.asyncio
    async def test_truncate_strategy(self):
        provider = AsyncMock()
        provider.count_tokens = AsyncMock(return_value=170_000)
        msgs = [Message(role="user", content=f"msg {i}") for i in range(20)]
        result = await maybe_compact(provider, msgs, context_window=200_000, threshold=0.8, strategy="truncate")
        assert result is not None
        assert len(result) == 11  # marker + last 10
        assert "truncated" in result[0].content.lower()

    @pytest.mark.asyncio
    async def test_summarize_strategy(self):
        provider = AsyncMock()
        provider.count_tokens = AsyncMock(return_value=170_000)

        summary_msg = Message(role="assistant", content="Summary: we did X, Y, Z.")
        provider.chat = AsyncMock(return_value=summary_msg)

        msgs = [Message(role="user", content=f"msg {i}") for i in range(20)]
        result = await maybe_compact(provider, msgs, context_window=200_000, threshold=0.8, strategy="summarize")
        assert result is not None
        # Should be: summary + last 4 messages
        assert len(result) == 5
        assert "summary" in result[0].content.lower()

    @pytest.mark.asyncio
    async def test_summarize_falls_back_to_truncate_on_error(self):
        provider = AsyncMock()
        provider.count_tokens = AsyncMock(return_value=170_000)
        provider.chat = AsyncMock(side_effect=Exception("LLM down"))

        msgs = [Message(role="user", content=f"msg {i}") for i in range(20)]
        result = await maybe_compact(provider, msgs, context_window=200_000, threshold=0.8, strategy="summarize")
        assert result is not None
        assert "truncated" in result[0].content.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_compact.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement compaction**

`tinyloom/core/compact.py`:
```python
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from tinyloom.core.types import Message

if TYPE_CHECKING:
    from tinyloom.providers.base import LLMProvider


SUMMARY_PROMPT = (
    "Summarize the following conversation concisely. Include:\n"
    "1. What task is being worked on\n"
    "2. What files were modified\n"
    "3. What's been accomplished\n"
    "4. Key decisions made\n"
    "5. Errors encountered and how they were resolved\n"
    "6. What still needs to be done\n\n"
    "Be specific about file names and code changes.\n\n"
)

KEEP_RECENT_SUMMARIZE = 4
KEEP_RECENT_TRUNCATE = 10


def estimate_tokens_heuristic(messages: list[Message]) -> int:
    text = ""
    for msg in messages:
        text += msg.content
        for tc in msg.tool_calls:
            text += tc.name + str(tc.input)
    return len(text) // 4


async def maybe_compact(
    provider: LLMProvider,
    messages: list[Message],
    context_window: int,
    threshold: float,
    strategy: str,
) -> list[Message] | None:
    try:
        current_tokens = await provider.count_tokens(messages)
    except Exception:
        current_tokens = estimate_tokens_heuristic(messages)

    limit = int(context_window * threshold)
    if current_tokens < limit:
        return None

    if strategy == "summarize":
        return await _summarize(provider, messages)
    else:
        return _truncate(messages)


def _truncate(messages: list[Message]) -> list[Message]:
    marker = Message(role="user", content="[Previous conversation was truncated]")
    recent = messages[-KEEP_RECENT_TRUNCATE:]
    return [marker] + recent


async def _summarize(provider: LLMProvider, messages: list[Message]) -> list[Message]:
    try:
        conversation_text = "\n".join(f"[{m.role}]: {m.content[:500]}" for m in messages)
        summary_prompt = [Message(role="user", content=SUMMARY_PROMPT + conversation_text)]
        summary_msg = await provider.chat(summary_prompt, max_tokens=2048)
        summary = Message(role="user", content=f"[Conversation summary: {summary_msg.content}]")
        recent = messages[-KEEP_RECENT_SUMMARIZE:]
        return [summary] + recent
    except Exception as e:
        print(f"Compaction summarize failed, falling back to truncate: {e}", file=sys.stderr)
        return _truncate(messages)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_compact.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/core/compact.py tests/test_compact.py
git commit -m "Add context compaction with summarize and truncate strategies"
```

---

### Task 11: Agent Loop

**Files:**
- Create: `tinyloom/core/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write failing tests for agent loop**

`tests/test_agent.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from tinyloom.core.agent import Agent
from tinyloom.core.types import Message, ToolCall, StreamEvent, AgentEvent
from tinyloom.core.config import Config
from tinyloom.core.tools import Tool, ToolRegistry
from tinyloom.core.hooks import HookRunner


def make_text_stream(*texts):
    """Helper: create a provider that streams text and yields done."""
    async def stream(messages, tools, system=""):
        full_text = "".join(texts)
        for t in texts:
            yield StreamEvent(type="text", text=t)
        yield StreamEvent(type="done", message=Message(role="assistant", content=full_text))
    return stream


def make_tool_then_text_stream(tool_calls, final_text):
    """Helper: first call returns tool_calls, second returns text."""
    call_count = 0

    async def stream(messages, tools, system=""):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            for tc in tool_calls:
                yield StreamEvent(type="tool_call", tool_call=tc)
            yield StreamEvent(type="done", message=Message(role="assistant", tool_calls=tool_calls))
        else:
            yield StreamEvent(type="text", text=final_text)
            yield StreamEvent(type="done", message=Message(role="assistant", content=final_text))
    return stream


class TestAgentRun:
    @pytest.mark.asyncio
    async def test_simple_text_response(self):
        provider = AsyncMock()
        provider.stream = make_text_stream("Hello ", "world!")
        provider.count_tokens = AsyncMock(return_value=100)

        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=provider, tools=ToolRegistry(), hooks=HookRunner())

        events = []
        async for evt in agent.run("hi"):
            events.append(evt)

        types = [e.type for e in events]
        assert "agent_start" in types
        assert "text_delta" in types
        assert "response_complete" in types
        assert "agent_stop" in types

    @pytest.mark.asyncio
    async def test_tool_call_and_response(self):
        tc = ToolCall(id="tc_1", name="echo", input={"msg": "hello"})
        provider = AsyncMock()
        provider.stream = make_tool_then_text_stream([tc], "Done!")
        provider.count_tokens = AsyncMock(return_value=100)

        registry = ToolRegistry()
        registry.register(Tool(name="echo", description="", input_schema={}, function=lambda i: i["msg"]))

        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=provider, tools=registry, hooks=HookRunner())

        events = []
        async for evt in agent.run("say hello"):
            events.append(evt)

        types = [e.type for e in events]
        assert "tool_call" in types
        assert "tool_result" in types
        assert "text_delta" in types

    @pytest.mark.asyncio
    async def test_hooks_receive_events(self):
        provider = AsyncMock()
        provider.stream = make_text_stream("hi")
        provider.count_tokens = AsyncMock(return_value=100)

        hook_calls = []
        hooks = HookRunner()
        hooks.on("text_delta", lambda ctx: hook_calls.append(ctx.get("type")))

        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=provider, tools=ToolRegistry(), hooks=hooks)

        async for _ in agent.run("hello"):
            pass
        assert "text_delta" in hook_calls

    @pytest.mark.asyncio
    async def test_skip_tool_via_hook(self):
        tc = ToolCall(id="tc_1", name="bash", input={"command": "rm -rf /"})
        provider = AsyncMock()
        provider.stream = make_tool_then_text_stream([tc], "ok")
        provider.count_tokens = AsyncMock(return_value=100)

        registry = ToolRegistry()
        registry.register(Tool(name="bash", description="", input_schema={}, function=lambda i: "executed"))

        hooks = HookRunner()
        hooks.on("tool_call", lambda ctx: ctx.update({"skip": True}))

        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=provider, tools=registry, hooks=hooks)

        events = []
        async for evt in agent.run("do it"):
            events.append(evt)

        # Tool should have been skipped
        results = [e for e in events if e.type == "tool_result"]
        assert any("skipped" in r.result.lower() or "denied" in r.result.lower() for r in results)

    @pytest.mark.asyncio
    async def test_max_turns_limit(self):
        """Agent should stop after max_turns even if LLM keeps requesting tools."""
        tc = ToolCall(id="tc_1", name="echo", input={"msg": "loop"})

        async def infinite_tools(messages, tools, system=""):
            yield StreamEvent(type="tool_call", tool_call=tc)
            yield StreamEvent(type="done", message=Message(role="assistant", tool_calls=[tc]))

        provider = AsyncMock()
        provider.stream = infinite_tools
        provider.count_tokens = AsyncMock(return_value=100)

        registry = ToolRegistry()
        registry.register(Tool(name="echo", description="", input_schema={}, function=lambda i: "ok"))

        config = Config()
        config.compaction.enabled = False
        config.max_turns = 3

        agent = Agent(config=config, provider=provider, tools=registry, hooks=HookRunner())

        events = []
        async for evt in agent.run("loop forever"):
            events.append(evt)

        # Should have stopped after 3 turns
        tool_calls = [e for e in events if e.type == "tool_call"]
        assert len(tool_calls) <= 3


class TestAgentStep:
    @pytest.mark.asyncio
    async def test_step_accumulates_state(self):
        provider = AsyncMock()
        provider.stream = make_text_stream("response")
        provider.count_tokens = AsyncMock(return_value=100)

        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=provider, tools=ToolRegistry(), hooks=HookRunner())

        async for _ in agent.step("first"):
            pass
        async for _ in agent.step("second"):
            pass

        # Should have 4 messages: user1, assistant1, user2, assistant2
        assert len(agent.state.messages) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement agent loop**

`tinyloom/core/agent.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, TYPE_CHECKING

from tinyloom.core.types import Message, ToolCall, AgentEvent, StreamEvent
from tinyloom.core.config import Config
from tinyloom.core.hooks import HookRunner
from tinyloom.core.tools import ToolRegistry, get_builtin_tools
from tinyloom.core.compact import maybe_compact

if TYPE_CHECKING:
    from tinyloom.providers.base import LLMProvider


@dataclass
class AgentState:
    messages: list[Message] = field(default_factory=list)
    turn: int = 0


class Agent:
    def __init__(
        self,
        config: Config,
        provider: LLMProvider | None = None,
        tools: ToolRegistry | None = None,
        hooks: HookRunner | None = None,
    ):
        self.config = config
        self.hooks = hooks or HookRunner()
        self.state = AgentState()

        if tools is not None:
            self.tools = tools
        else:
            self.tools = ToolRegistry()
            for t in get_builtin_tools():
                self.tools.register(t)

        if provider is not None:
            self.provider = provider
        else:
            from tinyloom.providers import create_provider
            self.provider = create_provider(config.model)

    async def run(self, prompt: str) -> AsyncIterator[AgentEvent]:
        self.state = AgentState()
        await self._add_message(Message(role="user", content=prompt))

        yield AgentEvent(type="agent_start")
        await self.hooks.emit("agent_start", {"type": "agent_start"})

        async for evt in self._loop():
            yield evt

        yield AgentEvent(type="agent_stop")
        await self.hooks.emit("agent_stop", {"type": "agent_stop"})

    async def step(self, user_input: str) -> AsyncIterator[AgentEvent]:
        await self._add_message(Message(role="user", content=user_input))
        self.state.turn = 0

        async for evt in self._loop():
            yield evt

    async def _loop(self) -> AsyncIterator[AgentEvent]:
        while self.state.turn < self.config.max_turns:
            skipped_tool_ids: set[str] = set()
            # Compaction check
            if self.config.compaction.enabled:
                compacted = await maybe_compact(
                    self.provider,
                    self.state.messages,
                    self.config.model.context_window,
                    self.config.compaction.threshold,
                    self.config.compaction.strategy,
                )
                if compacted is not None:
                    self.state.messages = compacted
                    evt = AgentEvent(type="compaction")
                    await self.hooks.emit("compaction", {"type": "compaction"})
                    yield evt

            # LLM call
            self.state.turn += 1
            assistant_msg = Message(role="assistant")
            tool_calls: list[ToolCall] = []

            async for stream_evt in self.provider.stream(
                messages=self.state.messages,
                tools=self.tools.all_defs(),
                system=self.config.system_prompt,
            ):
                if stream_evt.type == "text":
                    evt = AgentEvent(type="text_delta", text=stream_evt.text)
                    ctx = {"type": "text_delta", "text": stream_evt.text}
                    await self.hooks.emit("text_delta", ctx)
                    if not ctx.get("skip"):
                        yield evt

                elif stream_evt.type == "tool_call":
                    tool_calls.append(stream_evt.tool_call)
                    evt = AgentEvent(type="tool_call", tool_call=stream_evt.tool_call)
                    ctx = {
                        "type": "tool_call",
                        "tool_name": stream_evt.tool_call.name,
                        "tool_call": stream_evt.tool_call,
                    }
                    await self.hooks.emit("tool_call", ctx)
                    if ctx.get("skip"):
                        skipped_tool_ids.add(stream_evt.tool_call.id)
                    else:
                        yield evt

                elif stream_evt.type == "done":
                    assistant_msg = stream_evt.message

                elif stream_evt.type == "error":
                    evt = AgentEvent(type="error", error=stream_evt.error)
                    await self.hooks.emit("error", {"type": "error", "error": stream_evt.error})
                    yield evt
                    return

            await self._add_message(assistant_msg)

            # Tool execution
            if tool_calls:
                for tc in tool_calls:
                    if tc.id in skipped_tool_ids:
                        result = f"Tool '{tc.name}' was denied by hook"
                    else:
                        result = await self.tools.execute(tc.name, tc.input)

                    evt = AgentEvent(
                        type="tool_result",
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        result=result,
                    )
                    yield evt

                    await self._add_message(Message(
                        role="tool_result",
                        content=result,
                        tool_call_id=tc.id,
                        name=tc.name,
                    ))

                continue  # Go back to LLM with tool results

            # No tool calls: response complete
            evt = AgentEvent(type="response_complete", message=assistant_msg)
            await self.hooks.emit("response_complete", {
                "type": "response_complete",
                "message": assistant_msg,
            })
            yield evt
            return

    async def _add_message(self, msg: Message):
        self.state.messages.append(msg)
        await self.hooks.emit(f"message:{msg.role}", {
            "type": f"message:{msg.role}",
            "message": msg,
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent.py -v`
Expected: all PASS

- [ ] **Step 5: Update public API exports**

Add to `tinyloom/__init__.py`:
```python
from tinyloom.core.agent import Agent
```

- [ ] **Step 6: Commit**

```bash
git add tinyloom/core/agent.py tests/test_agent.py tinyloom/__init__.py
git commit -m "Add agent loop with tool execution, hooks, and compaction"
```

---

## Chunk 5: Plugin System + Todo Plugin

### Task 12: Plugin Loader

**Files:**
- Modify: `tinyloom/plugins/__init__.py`
- Create: `tests/test_plugins.py`

- [ ] **Step 1: Write failing tests for plugin loader**

`tests/test_plugins.py`:
```python
import pytest

from tinyloom.core.agent import Agent
from tinyloom.core.config import Config
from tinyloom.core.tools import ToolRegistry
from tinyloom.core.hooks import HookRunner


class TestPluginLoader:
    def test_load_from_config_path(self, tmp_path, monkeypatch):
        from tinyloom.plugins import load_plugins_from_config

        mod_file = tmp_path / "my_plugin.py"
        mod_file.write_text(
            "def activate(agent):\n"
            "    agent._test_activated = True\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))

        config = Config()
        config.compaction.enabled = False
        provider = None  # Won't be called

        agent = Agent(config=config, provider=provider, tools=ToolRegistry(), hooks=HookRunner())
        load_plugins_from_config(agent, ["my_plugin:activate"])
        assert getattr(agent, "_test_activated", False) is True

    def test_load_plugin_error_does_not_crash(self, capsys):
        from tinyloom.plugins import load_plugins_from_config

        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=None, tools=ToolRegistry(), hooks=HookRunner())
        load_plugins_from_config(agent, ["nonexistent_module:activate"])
        captured = capsys.readouterr()
        assert "error" in captured.err.lower() or "Error" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plugins.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement plugin loader**

`tinyloom/plugins/__init__.py`:
```python
from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


def load_plugins(agent: Agent):
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="tinyloom.plugins")
    except Exception:
        return

    for ep in eps:
        try:
            activate_fn = ep.load()
            activate_fn(agent)
        except Exception as e:
            print(f"Plugin error ({ep.name}): {e}", file=sys.stderr)


def load_plugins_from_config(agent: Agent, plugin_paths: list[str]):
    for path in plugin_paths:
        try:
            module_path, _, func_name = path.rpartition(":")
            if not func_name:
                func_name = "activate"
                module_path = path
            module = importlib.import_module(module_path)
            fn = getattr(module, func_name)
            fn(agent)
        except Exception as e:
            print(f"Plugin error ({path}): {e}", file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_plugins.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/plugins/__init__.py tests/test_plugins.py
git commit -m "Add plugin loader with entry_points and config path discovery"
```

---

### Task 13: Todo Plugin

**Files:**
- Create: `tinyloom/plugins/todo.py`
- Modify: `tests/test_plugins.py`

- [ ] **Step 1: Write failing tests for todo plugin**

Append to `tests/test_plugins.py`:
```python
from tinyloom.plugins.todo import activate as todo_activate, TodoPlugin


class TestTodoPlugin:
    @pytest.fixture
    def agent_with_todo(self):
        config = Config()
        config.compaction.enabled = False
        agent = Agent(config=config, provider=None, tools=ToolRegistry(), hooks=HookRunner())
        todo_activate(agent)
        return agent

    def test_registers_todo_tool(self, agent_with_todo):
        assert agent_with_todo.tools.get("todo") is not None

    @pytest.mark.asyncio
    async def test_create_task(self, agent_with_todo):
        result = await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Fix bug"})
        assert "created" in result.lower() or "1" in result

    @pytest.mark.asyncio
    async def test_list_tasks(self, agent_with_todo):
        await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Task A"})
        await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Task B"})
        result = await agent_with_todo.tools.execute("todo", {"action": "list"})
        assert "Task A" in result
        assert "Task B" in result

    @pytest.mark.asyncio
    async def test_update_status(self, agent_with_todo):
        await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Task A"})
        result = await agent_with_todo.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "done"})
        assert "done" in result.lower()

    @pytest.mark.asyncio
    async def test_list_shows_status(self, agent_with_todo):
        await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Task A"})
        await agent_with_todo.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "in_progress"})
        result = await agent_with_todo.tools.execute("todo", {"action": "list"})
        assert "in_progress" in result

    @pytest.mark.asyncio
    async def test_has_incomplete_tasks(self, agent_with_todo):
        await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Task A"})
        assert agent_with_todo._todo_plugin.has_incomplete_tasks()

    @pytest.mark.asyncio
    async def test_no_incomplete_when_all_done(self, agent_with_todo):
        await agent_with_todo.tools.execute("todo", {"action": "create", "description": "Task A"})
        await agent_with_todo.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "done"})
        assert not agent_with_todo._todo_plugin.has_incomplete_tasks()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plugins.py -v -k "Todo"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement todo plugin**

`tinyloom/plugins/todo.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tinyloom.core.tools import Tool

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


@dataclass
class TodoItem:
    id: int
    description: str
    status: str = "pending"  # "pending" | "in_progress" | "done"


class TodoPlugin:
    def __init__(self):
        self.tasks: list[TodoItem] = []
        self._next_id = 1

    def handle_todo(self, inp: dict) -> str:
        action = inp.get("action", "list")

        if action == "create":
            desc = inp.get("description", "")
            if not desc:
                return "Error: description is required"
            item = TodoItem(id=self._next_id, description=desc)
            self.tasks.append(item)
            self._next_id += 1
            return f"Task {item.id} created: {desc}"

        elif action == "update_status":
            task_id = int(inp.get("task_id", 0))
            status = inp.get("status", "")
            if status not in ("pending", "in_progress", "done"):
                return f"Error: invalid status '{status}'. Use: pending, in_progress, done"
            for task in self.tasks:
                if task.id == task_id:
                    task.status = status
                    return f"Task {task_id} updated to {status}"
            return f"Error: task {task_id} not found"

        elif action == "list":
            if not self.tasks:
                return "No tasks."
            lines = []
            for t in self.tasks:
                lines.append(f"  [{t.status}] {t.id}. {t.description}")
            return "Tasks:\n" + "\n".join(lines)

        else:
            return f"Error: unknown action '{action}'. Use: create, update_status, list"

    def has_incomplete_tasks(self) -> bool:
        return any(t.status != "done" for t in self.tasks)

    def incomplete_summary(self) -> str:
        incomplete = [t for t in self.tasks if t.status != "done"]
        if not incomplete:
            return ""
        lines = [f"  [{t.status}] {t.id}. {t.description}" for t in incomplete]
        return "Incomplete tasks:\n" + "\n".join(lines)


def activate(agent: Agent):
    plugin = TodoPlugin()
    agent._todo_plugin = plugin

    tool = Tool(
        name="todo",
        description=(
            "Manage a task list to track your work. Actions:\n"
            "- create: create a new task (requires 'description')\n"
            "- update_status: change task status (requires 'task_id' and 'status': pending/in_progress/done)\n"
            "- list: show all tasks and their status"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update_status", "list"],
                    "description": "Action to perform",
                },
                "description": {"type": "string", "description": "Task description (for create)"},
                "task_id": {"type": "string", "description": "Task ID (for update_status)"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done"],
                    "description": "New status (for update_status)",
                },
            },
            "required": ["action"],
        },
        function=plugin.handle_todo,
    )
    agent.tools.register(tool)

    async def on_response_complete(ctx):
        if plugin.has_incomplete_tasks():
            summary = plugin.incomplete_summary()
            # Inject a follow-up message so the loop continues
            from tinyloom.core.types import Message
            agent.state.messages.append(Message(
                role="user",
                content=f"You still have incomplete tasks. Please finish them:\n{summary}",
            ))
            # Signal the agent loop to continue rather than stopping
            ctx["continue"] = True

    agent.hooks.on("response_complete", on_response_complete)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_plugins.py -v -k "Todo"`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/plugins/todo.py tests/test_plugins.py
git commit -m "Add todo plugin with task management and agent_stop hook"
```

---

## Chunk 6: CLI + TUI

### Task 14: CLI

**Files:**
- Create: `tinyloom/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI**

`tests/test_cli.py`:
```python
import sys
import pytest
from unittest.mock import patch, AsyncMock

from tinyloom.cli import build_parser, detect_mode


class TestBuildParser:
    def test_no_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.prompt is None
        assert args.model is None

    def test_prompt_arg(self):
        parser = build_parser()
        args = parser.parse_args(["fix the bug"])
        assert args.prompt == "fix the bug"

    def test_model_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-m", "gpt-4o", "do X"])
        assert args.model == "gpt-4o"
        assert args.prompt == "do X"

    def test_provider_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-p", "openai", "do X"])
        assert args.provider == "openai"

    def test_stdin_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--stdin"])
        assert args.stdin is True

    def test_no_plugins_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--no-plugins", "do X"])
        assert args.no_plugins is True

    def test_system_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--system", "Be brief.", "do X"])
        assert args.system == "Be brief."


class TestDetectMode:
    def test_headless_with_prompt(self):
        parser = build_parser()
        args = parser.parse_args(["hello"])
        assert detect_mode(args) == "headless"

    def test_interactive_no_prompt(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert detect_mode(args) == "interactive"

    def test_headless_with_stdin_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--stdin"])
        assert detect_mode(args) == "headless"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement CLI**

`tinyloom/cli.py`:
```python
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from tinyloom import __version__
from tinyloom.core.config import load_config
from tinyloom.core.tools import ToolRegistry, get_builtin_tools
from tinyloom.core.hooks import HookRunner
from tinyloom.core.agent import Agent
from tinyloom.plugins import load_plugins, load_plugins_from_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tinyloom", description="tinyloom - tiny coding agent")
    parser.add_argument("prompt", nargs="?", help="Prompt (triggers headless mode)")
    parser.add_argument("-m", "--model", help="Override model")
    parser.add_argument("-p", "--provider", help="Override provider")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--stdin", action="store_true", help="Read prompt from stdin")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--json", action="store_true", help="Force JSON output")
    parser.add_argument("--no-plugins", action="store_true", help="Disable all plugins")
    parser.add_argument("--version", action="version", version=f"tinyloom {__version__}")
    return parser


def detect_mode(args: argparse.Namespace) -> str:
    if args.prompt or args.stdin:
        return "headless"
    return "interactive"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130


async def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.model:
        config.model.model = args.model
    if args.provider:
        config.model.provider = args.provider
    if args.system:
        config.system_prompt = args.system

    registry = ToolRegistry()
    for t in get_builtin_tools():
        registry.register(t)

    hooks = HookRunner()
    hooks.register_from_config(config.hooks)

    from tinyloom.providers import create_provider
    provider = create_provider(config.model)

    agent = Agent(config=config, provider=provider, tools=registry, hooks=hooks)

    if not args.no_plugins:
        load_plugins(agent)
        load_plugins_from_config(agent, config.plugins)

    mode = detect_mode(args)

    if mode == "headless":
        prompt = args.prompt
        if args.stdin:
            prompt = sys.stdin.read().strip()
        if not prompt:
            print("Error: no prompt provided", file=sys.stderr)
            return 1
        await _run_headless(agent, prompt)
    else:
        from tinyloom.tui import run_tui
        await run_tui(agent)

    return 0


async def _run_headless(agent: Agent, prompt: str):
    async for evt in agent.run(prompt):
        print(json.dumps(evt.to_dict()), flush=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tinyloom/cli.py tests/test_cli.py
git commit -m "Add CLI with headless and interactive mode detection"
```

---

### Task 15: TUI

**Files:**
- Create: `tinyloom/tui.py`

- [ ] **Step 1: Implement minimal Textual TUI**

`tinyloom/tui.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, Input, Static, Markdown
from textual.binding import Binding

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


class MessageWidget(Static):
    pass


class TinyloomApp(App):
    CSS = """
    VerticalScroll {
        height: 1fr;
    }
    #input {
        dock: bottom;
    }
    .tool-call {
        color: green;
    }
    .tool-result {
        color: $text-muted;
    }
    .error {
        color: red;
    }
    .compaction {
        color: yellow;
        text-style: dim;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent
        self.title = f"tinyloom - {agent.config.model.model}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="messages")
        yield Input(placeholder="Type a message...", id="input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return

        event.input.clear()

        # Handle slash commands
        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(MessageWidget(f"[bold]You:[/bold] {user_input}"))

        # Disable input during response
        self.query_one("#input", Input).disabled = True

        text_buffer = ""
        text_widget = MessageWidget("")
        messages.mount(text_widget)

        async for evt in self.agent.step(user_input):
            if evt.type == "text_delta":
                text_buffer += evt.text
                text_widget.update(text_buffer)

            elif evt.type == "tool_call":
                tc = evt.tool_call
                preview = str(tc.input)[:100]
                messages.mount(MessageWidget(
                    f"[green]> {tc.name}[/green]({preview})",
                    classes="tool-call",
                ))

            elif evt.type == "tool_result":
                preview = evt.result[:200] if evt.result else "(empty)"
                messages.mount(MessageWidget(
                    f"[dim]  -> {preview}[/dim]",
                    classes="tool-result",
                ))

            elif evt.type == "compaction":
                messages.mount(MessageWidget(
                    "[yellow dim]Context compacted[/yellow dim]",
                    classes="compaction",
                ))

            elif evt.type == "error":
                messages.mount(MessageWidget(
                    f"[red]Error: {evt.error}[/red]",
                    classes="error",
                ))

        messages.scroll_end()
        self.query_one("#input", Input).disabled = False
        self.query_one("#input", Input).focus()

    async def _handle_command(self, cmd: str):
        messages = self.query_one("#messages", VerticalScroll)
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == "/help":
            messages.mount(MessageWidget(
                "[bold]Commands:[/bold]\n"
                "  /help     - show this help\n"
                "  /clear    - clear conversation\n"
                "  /model    - show current model\n"
                "  /tokens   - show token estimate\n"
                "  /quit     - exit"
            ))
        elif command == "/clear":
            self.agent.state.messages.clear()
            await messages.remove_children()
            messages.mount(MessageWidget("[dim]Conversation cleared.[/dim]"))
        elif command == "/model":
            messages.mount(MessageWidget(f"Model: {self.agent.config.model.model}"))
        elif command == "/tokens":
            from tinyloom.core.compact import estimate_tokens_heuristic
            tokens = estimate_tokens_heuristic(self.agent.state.messages)
            window = self.agent.config.model.context_window
            pct = tokens / window * 100 if window else 0
            messages.mount(MessageWidget(f"Tokens: ~{tokens:,} / {window:,} ({pct:.0f}%)"))
        elif command == "/quit":
            self.exit()
        else:
            messages.mount(MessageWidget(f"[red]Unknown command: {command}[/red]"))


async def run_tui(agent: Agent):
    app = TinyloomApp(agent)
    await app.run_async()
```

- [ ] **Step 2: Verify TUI imports**

Run: `uv run python -c "from tinyloom.tui import TinyloomApp; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tinyloom/tui.py
git commit -m "Add minimal Textual TUI with streaming and slash commands"
```

---

## Chunk 7: MCP Plugin + Exec Tool + Final Wiring

### Task 16: MCP Plugin

**Files:**
- Create: `tinyloom/plugins/mcp.py`

- [ ] **Step 1: Implement MCP plugin**

`tinyloom/plugins/mcp.py`:
```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tinyloom.core.tools import Tool

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


def _load_mcp_json() -> dict:
    candidates = [Path(".mcp.json"), Path.home() / ".config" / "tinyloom" / ".mcp.json"]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text())
    return {}


async def _connect_and_register(agent: Agent, name: str, config: dict):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        print(
            f"MCP plugin: 'mcp' package not installed. "
            f"Install with: uv add 'tinyloom[mcp]'",
            file=sys.stderr,
        )
        return

    server_params = StdioServerParameters(
        command=config["command"],
        args=config.get("args", []),
        env=config.get("env"),
    )

    try:
        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = await ClientSession(read_stream, write_stream).__aenter__()
        await session.initialize()
        mcp_tools = await session.list_tools()

        for mt in mcp_tools.tools:
            tool_name = mt.name
            tool_session = session

            async def call_mcp(inp: dict, _name=tool_name, _session=tool_session) -> str:
                result = await _session.call_tool(_name, arguments=inp)
                return "\n".join(
                    block.text for block in result.content if hasattr(block, "text")
                )

            agent.tools.register(Tool(
                name=f"mcp_{tool_name}",
                description=mt.description or f"MCP tool: {tool_name}",
                input_schema=mt.inputSchema or {"type": "object", "properties": {}},
                function=call_mcp,
            ))
    except Exception as e:
        print(f"MCP server '{name}' failed: {e}", file=sys.stderr)


def activate(agent: Agent):
    import asyncio

    mcp_config = _load_mcp_json()
    servers = mcp_config.get("mcpServers", {})

    for server_name, server_config in servers.items():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_connect_and_register(agent, server_name, server_config))
            else:
                asyncio.run(_connect_and_register(agent, server_name, server_config))
        except Exception as e:
            print(f"MCP server '{server_name}' failed: {e}", file=sys.stderr)
```

- [ ] **Step 2: Verify import**

Run: `uv run python -c "from tinyloom.plugins.mcp import activate; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tinyloom/plugins/mcp.py
git commit -m "Add MCP plugin for tool extension via .mcp.json"
```

---

### Task 17: Exec Tool (Sub-agents)

**Files:**
- Modify: `tinyloom/core/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests for exec tool**

Append to `tests/test_tools.py`:
```python
from unittest.mock import AsyncMock
from tinyloom.core.types import StreamEvent, Message
from tinyloom.core.config import Config


class TestBuiltinExec:
    @pytest.mark.asyncio
    async def test_exec_tool_exists(self):
        from tinyloom.core.tools import get_builtin_tools_with_exec
        tools = {t.name: t for t in get_builtin_tools_with_exec(Config())}
        assert "exec" in tools

    @pytest.mark.asyncio
    async def test_exec_excludes_self(self):
        from tinyloom.core.tools import get_builtin_tools_with_exec
        # The exec tool's sub-agent should not have exec
        # This is tested implicitly by the implementation
        tools = get_builtin_tools_with_exec(Config())
        exec_tool = [t for t in tools if t.name == "exec"][0]
        assert exec_tool is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools.py -v -k "Exec"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement exec tool**

Append to `tinyloom/core/tools.py`:
```python
def _make_exec_tool(parent_config):
    """Create the exec tool with the parent's config for defaults."""

    async def exec_fn(inp: dict) -> str:
        """Async exec tool -- awaited by ToolRegistry.execute()."""
        from tinyloom.core.agent import Agent
        from copy import deepcopy

        config = deepcopy(parent_config)
        if inp.get("model"):
            config.model.model = inp["model"]
        if inp.get("system_prompt"):
            config.system_prompt = inp["system_prompt"]

        sub_registry = ToolRegistry()
        for t in get_builtin_tools():  # excludes exec
            sub_registry.register(t)

        from tinyloom.core.hooks import HookRunner
        sub_agent = Agent(config=config, tools=sub_registry, hooks=HookRunner())

        parts = []
        async for evt in sub_agent.run(inp["task"]):
            if evt.type == "text_delta":
                parts.append(evt.text)
        return "".join(parts)

    return Tool(
        name="exec",
        description=(
            "Launch a sub-agent to handle a specific task. "
            "The sub-agent gets its own context and all tools except exec. "
            "Use to delegate focused tasks like: 'write tests for X', 'refactor this file'. "
            "Returns the sub-agent's final text response."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task/prompt for the sub-agent"},
                "model": {"type": "string", "description": "Override model (optional)", "default": ""},
                "system_prompt": {"type": "string", "description": "Override system prompt (optional)", "default": ""},
            },
            "required": ["task"],
        },
        function=exec_fn,
    )


def get_builtin_tools_with_exec(config) -> list[Tool]:
    return get_builtin_tools() + [_make_exec_tool(config)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v -k "Exec"`
Expected: all PASS

- [ ] **Step 5: Update Agent to use exec tool**

Update `tinyloom/core/agent.py` in `__init__`:
```python
# Replace get_builtin_tools() with get_builtin_tools_with_exec(config)
from tinyloom.core.tools import get_builtin_tools_with_exec
# In the else branch of tools initialization:
for t in get_builtin_tools_with_exec(config):
    self.tools.register(t)
```

- [ ] **Step 6: Commit**

```bash
git add tinyloom/core/tools.py tinyloom/core/agent.py tests/test_tools.py
git commit -m "Add exec tool for one-level-deep sub-agents"
```

---

### Task 18: Final Wiring + Example Config

**Files:**
- Modify: `tinyloom/__init__.py`
- Create: `tinyloom.example.yaml`

- [ ] **Step 1: Finalize public API exports**

`tinyloom/__init__.py`:
```python
"""tinyloom - A tiny, SDK-first coding agent harness."""

__version__ = "0.1.0"

from tinyloom.core.types import Message, ToolCall, StreamEvent, AgentEvent, ToolDef
from tinyloom.core.config import Config, ModelConfig, CompactionConfig, load_config
from tinyloom.core.hooks import HookRunner
from tinyloom.core.tools import Tool, ToolRegistry, tool, get_builtin_tools
from tinyloom.core.agent import Agent
from tinyloom.providers.base import LLMProvider
from tinyloom.providers import create_provider

__all__ = [
    "Agent",
    "Config",
    "ModelConfig",
    "CompactionConfig",
    "load_config",
    "Message",
    "ToolCall",
    "ToolDef",
    "StreamEvent",
    "AgentEvent",
    "Tool",
    "ToolRegistry",
    "tool",
    "get_builtin_tools",
    "HookRunner",
    "LLMProvider",
    "create_provider",
]
```

- [ ] **Step 2: Create example config**

`tinyloom.example.yaml`:
```yaml
# tinyloom configuration
# All fields are optional - defaults work out of the box.
# Copy to tinyloom.yaml and customize.

model:
  provider: anthropic                    # anthropic | openai
  model: claude-sonnet-4-20250514    # any model identifier
  # base_url: https://my-proxy.com/v1  # custom endpoint
  max_tokens: 8192                       # max output tokens per response
  context_window: 200000                 # total context window
  temperature: 0.0

system_prompt: |
  You are a skilled coding assistant. You have access to tools for
  reading, writing, and editing files, searching code, and running
  shell commands. Be concise. When editing files, always read them
  first to see the exact content.

compaction:
  enabled: true
  threshold: 0.8            # compact at 80% of context window
  strategy: summarize       # summarize | truncate

# Plugins (dotted paths to activator functions)
plugins:
  # - tinyloom.plugins.todo
  # - tinyloom.plugins.mcp

# Lifecycle hooks (dotted paths to callables)
hooks:
  # tool_call:
  #   - my_hooks.approve_writes

max_turns: 200
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Run linter**

Run: `uv run ruff check tinyloom/ tests/`
Expected: no errors (fix any that appear)

- [ ] **Step 5: Commit**

```bash
git add tinyloom/__init__.py tinyloom.example.yaml
git commit -m "Finalize public API and add example config"
```

- [ ] **Step 6: Verify end-to-end import**

Run: `uv run python -c "from tinyloom import Agent, Config, load_config, Tool, HookRunner; print('All exports OK')"`
Expected: `All exports OK`
