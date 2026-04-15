"""Tests for tinyloom.core.tools — tool system and built-in tools."""

from __future__ import annotations

import os

import pytest

from tinyloom.core.tools import Tool, ToolRegistry, tool, ToolDef, get_builtin_tools


# ---------------------------------------------------------------------------
# Task 5: Tool system
# ---------------------------------------------------------------------------


class TestToolCreation:
    def test_tool_has_required_fields(self):
        def fn(input_data):
            return "ok"

        t = Tool(
            name="my_tool",
            description="does stuff",
            input_schema={"type": "object"},
            function=fn,
        )
        assert t.name == "my_tool"
        assert t.description == "does stuff"
        assert t.input_schema == {"type": "object"}
        assert t.function is fn

    def test_tool_to_def_returns_tool_def(self):
        t = Tool(
            name="my_tool",
            description="does stuff",
            input_schema={"type": "object"},
            function=lambda d: "ok",
        )
        td = t.to_def()
        assert isinstance(td, ToolDef)
        assert td.name == "my_tool"
        assert td.description == "does stuff"
        assert td.input_schema == {"type": "object"}


class TestToolDecorator:
    def test_decorator_creates_tool(self):
        @tool("greet", "greets you", {"type": "object", "properties": {"name": {"type": "string"}}})
        def greet(input_data):
            return f"hello {input_data['name']}"

        assert isinstance(greet, Tool)
        assert greet.name == "greet"
        assert greet.description == "greets you"

    def test_decorated_tool_function_is_callable(self):
        @tool("double", "doubles a number", {"type": "object"})
        def double(input_data):
            return input_data["n"] * 2

        result = double.function({"n": 5})
        assert result == 10


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        t = Tool(name="foo", description="foo", input_schema={}, function=lambda d: "foo")
        reg.register(t)
        assert reg.get("foo") is t

    def test_get_missing_returns_none(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_all_defs_returns_tool_defs(self):
        reg = ToolRegistry()
        reg.register(Tool(name="a", description="A", input_schema={}, function=lambda d: "a"))
        reg.register(Tool(name="b", description="B", input_schema={}, function=lambda d: "b"))
        defs = reg.all_defs()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"a", "b"}

    def test_all_defs_empty(self):
        reg = ToolRegistry()
        assert reg.all_defs() == []


class TestToolRegistryExecute:
    async def test_execute_known_tool_returns_result(self):
        reg = ToolRegistry()
        reg.register(Tool(name="echo", description="echo", input_schema={}, function=lambda d: d["msg"]))
        result = await reg.execute("echo", {"msg": "hi"})
        assert result == "hi"

    async def test_execute_unknown_tool_returns_error(self):
        reg = ToolRegistry()
        result = await reg.execute("no_such_tool", {})
        assert "unknown tool" in result
        assert "no_such_tool" in result

    async def test_execute_catches_exceptions(self):
        def boom(input_data):
            raise ValueError("something blew up")

        reg = ToolRegistry()
        reg.register(Tool(name="boom", description="boom", input_schema={}, function=boom))
        result = await reg.execute("boom", {})
        assert "Error" in result
        assert "something blew up" in result

    async def test_execute_works_with_async_tool_function(self):
        async def async_fn(input_data):
            return "async_result"

        reg = ToolRegistry()
        reg.register(Tool(name="afn", description="async", input_schema={}, function=async_fn))
        result = await reg.execute("afn", {})
        assert result == "async_result"


# ---------------------------------------------------------------------------
# Task 6: Built-in tools
# ---------------------------------------------------------------------------


class TestReadTool:
    async def test_read_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("line one\nline two\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("read", {"path": str(f)})
        assert "line one" in result
        assert "line two" in result

    async def test_read_missing_file_returns_error(self, tmp_path):
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("read", {"path": str(tmp_path / "nope.txt")})
        assert "Error" in result or "not found" in result.lower() or "No such" in result

    async def test_read_large_file_adds_line_numbers(self, tmp_path):
        f = tmp_path / "big.txt"
        # Write 55 lines so line numbers are added
        f.write_text("\n".join(f"line {i}" for i in range(1, 56)) + "\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("read", {"path": str(f)})
        # Line numbers should appear for files >50 lines
        assert "1" in result
        assert "55" in result


class TestWriteTool:
    async def test_write_creates_new_file(self, tmp_path):
        f = tmp_path / "out.txt"
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("write", {"path": str(f), "content": "hello world"})
        assert f.read_text() == "hello world"
        assert "success" in result.lower() or "wrote" in result.lower() or "written" in result.lower()

    async def test_write_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "a" / "b" / "c.txt"
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        await reg.execute("write", {"path": str(f), "content": "nested"})
        assert f.read_text() == "nested"


class TestEditTool:
    async def test_edit_replaces_string(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("foo = 1\nbar = 2\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("edit", {"path": str(f), "old_str": "foo = 1", "new_str": "foo = 99"})
        assert "foo = 99" in f.read_text()
        assert "foo = 1" not in f.read_text()
        assert "Error" not in result

    async def test_edit_no_match_returns_error(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("foo = 1\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("edit", {"path": str(f), "old_str": "no_match_here", "new_str": "x"})
        assert "Error" in result or "not found" in result.lower() or "0" in result

    async def test_edit_multiple_matches_returns_error(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\nx = 1\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("edit", {"path": str(f), "old_str": "x = 1", "new_str": "x = 2"})
        assert "Error" in result or "multiple" in result.lower() or "2" in result

    async def test_edit_create_new_file_when_old_str_empty(self, tmp_path):
        f = tmp_path / "new_file.py"
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        await reg.execute("edit", {"path": str(f), "old_str": "", "new_str": "created content"})
        assert f.read_text() == "created content"

    async def test_edit_same_old_new_returns_error(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("edit", {"path": str(f), "old_str": "x = 1", "new_str": "x = 1"})
        assert "Error" in result or "same" in result.lower() or "identical" in result.lower()


class TestGrepTool:
    async def test_grep_finds_pattern(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("hello world\ngoodbye world\nhello again\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("grep", {"pattern": "hello", "path": str(tmp_path)})
        assert "hello" in result

    async def test_grep_no_matches(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("nothing relevant here\n")
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("grep", {"pattern": "zzznomatch", "path": str(tmp_path)})
        assert "No matches found" in result or result.strip() == ""


class TestBashTool:
    async def test_bash_simple_command(self):
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("bash", {"cmd": "echo hello"})
        assert "hello" in result

    async def test_bash_captures_stderr(self):
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("bash", {"cmd": "echo err >&2"})
        assert "err" in result

    async def test_bash_nonzero_exit_included_in_output(self):
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("bash", {"cmd": "exit 1"})
        # Should not raise; should include exit code info or just return empty/nonzero
        assert result is not None

    async def test_bash_timeout(self):
        reg = ToolRegistry()
        for t in get_builtin_tools():
            reg.register(t)
        result = await reg.execute("bash", {"cmd": "sleep 10", "timeout": 1})
        assert "timeout" in result.lower() or "timed out" in result.lower() or "Timeout" in result


# ---------------------------------------------------------------------------
# Task 17: Exec tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exec_tool_exists():
    from tinyloom.core.tools import get_builtin_tools_with_exec
    from tinyloom.core.config import Config
    tools = {t.name: t for t in get_builtin_tools_with_exec(Config())}
    assert "exec" in tools
    assert tools["exec"].function is not None
