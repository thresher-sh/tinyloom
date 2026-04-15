from __future__ import annotations

import stat
import sys
import types

from tinyloom.core.config import Config
from tinyloom.core.hooks import HookRunner
from tinyloom.core.tools import ToolRegistry
from tinyloom.core.agent import Agent
from tinyloom.plugins import load_plugins_from_config
from tinyloom.plugins.hook_scripts import activate as hook_scripts_activate, _serialize_ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent() -> Agent:
    from unittest.mock import MagicMock
    provider = MagicMock()
    config = Config()
    registry = ToolRegistry()
    hooks = HookRunner()
    return Agent(config=config, provider=provider, tools=registry, hooks=hooks)


def _make_temp_module(name: str, activate_fn) -> None:
    """Inject a temporary module into sys.modules."""
    mod = types.ModuleType(name)
    mod.activate = activate_fn
    sys.modules[name] = mod


# ---------------------------------------------------------------------------
# Task 12: Plugin Loader tests
# ---------------------------------------------------------------------------

def test_load_plugins_from_config_activates_plugin():
    agent = _make_agent()

    def activate(a):
        a._test_activated = True

    _make_temp_module("_test_plugin_activate", activate)
    load_plugins_from_config(agent, ["_test_plugin_activate:activate"])
    assert getattr(agent, "_test_activated", False) is True


def test_load_plugins_from_config_default_activate_name():
    agent = _make_agent()

    def activate(a):
        a._default_activated = True

    _make_temp_module("_test_plugin_default", activate)
    load_plugins_from_config(agent, ["_test_plugin_default"])
    assert getattr(agent, "_default_activated", False) is True


def test_load_plugins_from_config_bad_path_does_not_crash(capsys):
    agent = _make_agent()
    # Should not raise; should print to stderr
    load_plugins_from_config(agent, ["nonexistent.module.that.does.not.exist"])
    captured = capsys.readouterr()
    assert "Plugin error" in captured.err


def test_load_plugins_from_config_bad_function_does_not_crash(capsys):
    agent = _make_agent()

    def activate(a):
        raise RuntimeError("intentional error")

    _make_temp_module("_test_plugin_bad_fn", activate)
    load_plugins_from_config(agent, ["_test_plugin_bad_fn:activate"])
    captured = capsys.readouterr()
    assert "Plugin error" in captured.err


# ---------------------------------------------------------------------------
# Task 13: Todo Plugin tests
# ---------------------------------------------------------------------------

def test_todo_activate_registers_tool():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    assert agent.tools.get("todo") is not None
    assert hasattr(agent, "_todo_plugin")


async def test_todo_create_task():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    result = await agent.tools.execute("todo", {"action": "create", "description": "Write tests"})
    assert "Task 1 created" in result
    assert "Write tests" in result


async def test_todo_list_tasks():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    await agent.tools.execute("todo", {"action": "create", "description": "Task A"})
    await agent.tools.execute("todo", {"action": "create", "description": "Task B"})
    result = await agent.tools.execute("todo", {"action": "list"})
    assert "Task A" in result
    assert "Task B" in result


async def test_todo_list_empty():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    result = await agent.tools.execute("todo", {"action": "list"})
    assert result == "No tasks."


async def test_todo_update_status():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    await agent.tools.execute("todo", {"action": "create", "description": "Do something"})
    result = await agent.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "in_progress"})
    assert "updated to in_progress" in result


async def test_todo_update_status_done():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    await agent.tools.execute("todo", {"action": "create", "description": "Finish me"})
    result = await agent.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "done"})
    assert "updated to done" in result


async def test_todo_update_status_invalid_status():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    await agent.tools.execute("todo", {"action": "create", "description": "Task"})
    result = await agent.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "wip"})
    assert "Error" in result
    assert "invalid status" in result


async def test_todo_update_status_not_found():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    result = await agent.tools.execute("todo", {"action": "update_status", "task_id": "99", "status": "done"})
    assert "not found" in result


async def test_todo_has_incomplete_tasks():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    plugin = agent._todo_plugin
    await agent.tools.execute("todo", {"action": "create", "description": "Pending task"})
    assert plugin.has_incomplete_tasks() is True


async def test_todo_no_incomplete_when_all_done():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    plugin = agent._todo_plugin
    await agent.tools.execute("todo", {"action": "create", "description": "Task"})
    await agent.tools.execute("todo", {"action": "update_status", "task_id": "1", "status": "done"})
    assert plugin.has_incomplete_tasks() is False


async def test_todo_create_missing_description():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    result = await agent.tools.execute("todo", {"action": "create"})
    assert "Error" in result
    assert "description" in result


async def test_todo_unknown_action():
    from tinyloom.plugins.todo import activate
    agent = _make_agent()
    activate(agent)
    result = await agent.tools.execute("todo", {"action": "delete"})
    assert "Error" in result
    assert "unknown action" in result


# ---------------------------------------------------------------------------
# Hook Scripts Plugin tests
# ---------------------------------------------------------------------------

def _make_script(tmp_path, name, body):
    """Write an executable shell script and return its path."""
    script = tmp_path / name
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _make_agent_with_hook_scripts(hook_scripts):
    from unittest.mock import MagicMock
    provider = MagicMock()
    config = Config(hook_scripts=hook_scripts)
    registry = ToolRegistry()
    hooks = HookRunner()
    return Agent(config=config, provider=provider, tools=registry, hooks=hooks)


def test_hook_scripts_activate_registers_hooks():
    agent = _make_agent_with_hook_scripts({
        "tool_call": [{"command": "echo ok"}],
        "message:user": [{"command": "echo hi"}],
    })
    hook_scripts_activate(agent)
    assert len(agent.hooks._hooks.get("tool_call", [])) == 1
    assert len(agent.hooks._hooks.get("message:user", [])) == 1


def test_hook_scripts_activate_skips_empty_command():
    agent = _make_agent_with_hook_scripts({
        "tool_call": [{"command": ""}],
    })
    hook_scripts_activate(agent)
    assert len(agent.hooks._hooks.get("tool_call", [])) == 0


def test_hook_scripts_activate_no_scripts():
    agent = _make_agent_with_hook_scripts({})
    hook_scripts_activate(agent)
    assert len(agent.hooks._hooks) == 0


def test_hook_scripts_exit_0_passes(tmp_path):
    script = _make_script(tmp_path, "pass.sh", "exit 0")
    agent = _make_agent_with_hook_scripts({
        "tool_call": [{"command": script}],
    })
    hook_scripts_activate(agent)
    ctx = {"type": "tool_call", "tool_name": "bash"}
    agent.hooks._hooks["tool_call"][0](ctx)
    assert ctx.get("skip") is not True


def test_hook_scripts_exit_1_logs_error(tmp_path, capsys):
    script = _make_script(tmp_path, "err.sh", 'echo "bad thing" >&2\nexit 1')
    agent = _make_agent_with_hook_scripts({
        "tool_call": [{"command": script}],
    })
    hook_scripts_activate(agent)
    ctx = {"type": "tool_call", "tool_name": "bash"}
    agent.hooks._hooks["tool_call"][0](ctx)
    captured = capsys.readouterr()
    assert "Hook script error" in captured.err
    assert ctx.get("skip") is not True


def test_hook_scripts_exit_2_sets_skip_and_reason(tmp_path):
    script = _make_script(tmp_path, "deny.sh", 'echo "dangerous tool"\nexit 2')
    agent = _make_agent_with_hook_scripts({
        "tool_call": [{"command": script}],
    })
    hook_scripts_activate(agent)
    ctx = {"type": "tool_call", "tool_name": "bash"}
    agent.hooks._hooks["tool_call"][0](ctx)
    assert ctx["skip"] is True
    assert ctx["reason"] == "dangerous tool"


def test_hook_scripts_receives_ctx_as_json(tmp_path):
    # Script that writes stdin to a file so we can verify what was passed
    output_file = tmp_path / "received.json"
    script = _make_script(
        tmp_path, "capture.sh",
        f'cat > {output_file}\nexit 0'
    )
    agent = _make_agent_with_hook_scripts({
        "tool_call": [{"command": script}],
    })
    hook_scripts_activate(agent)
    ctx = {"type": "tool_call", "tool_name": "bash", "extra": 42}
    agent.hooks._hooks["tool_call"][0](ctx)
    import json
    received = json.loads(output_file.read_text())
    assert received["type"] == "tool_call"
    assert received["tool_name"] == "bash"
    assert received["extra"] == 42


def test_serialize_ctx_handles_non_serializable():
    ctx = {"key": "value", "obj": object()}
    result = _serialize_ctx(ctx)
    import json
    parsed = json.loads(result)
    assert parsed["key"] == "value"
    assert isinstance(parsed["obj"], str)


def test_hook_scripts_string_command_format():
    """hook_scripts can accept plain strings instead of dicts."""
    agent = _make_agent_with_hook_scripts({
        "tool_call": ["echo ok"],
    })
    hook_scripts_activate(agent)
    assert len(agent.hooks._hooks.get("tool_call", [])) == 1
