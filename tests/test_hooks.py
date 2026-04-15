"""Tests for tinyloom.core.hooks."""

from __future__ import annotations

import pytest

from tinyloom.core.hooks import HookRunner


@pytest.mark.asyncio
async def test_sync_hook_called():
    runner = HookRunner()
    called = []

    def on_start(ctx):
        called.append(ctx["x"])

    runner.on("start", on_start)
    await runner.emit("start", {"x": 42})
    assert called == [42]


@pytest.mark.asyncio
async def test_async_hook_called():
    runner = HookRunner()
    results = []

    async def on_start(ctx):
        results.append(ctx["val"])

    runner.on("start", on_start)
    await runner.emit("start", {"val": "async_ok"})
    assert results == ["async_ok"]


@pytest.mark.asyncio
async def test_multiple_hooks_same_event():
    runner = HookRunner()
    order = []

    runner.on("ev", lambda ctx: order.append("a"))
    runner.on("ev", lambda ctx: order.append("b"))
    runner.on("ev", lambda ctx: order.append("c"))

    await runner.emit("ev", {})
    assert order == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_no_hooks_no_error():
    runner = HookRunner()
    ctx = await runner.emit("no_such_event", {"key": "value"})
    assert ctx == {"key": "value"}


@pytest.mark.asyncio
async def test_hook_exception_logged_not_raised(capsys):
    runner = HookRunner()

    def bad_hook(ctx):
        raise ValueError("boom")

    runner.on("ev", bad_hook)
    # Should not raise
    await runner.emit("ev", {})
    captured = capsys.readouterr()
    assert "Hook error" in captured.err
    assert "boom" in captured.err


@pytest.mark.asyncio
async def test_hook_can_mutate_ctx():
    runner = HookRunner()

    def add_value(ctx):
        ctx["added"] = True

    runner.on("ev", add_value)
    ctx = await runner.emit("ev", {"existing": 1})
    assert ctx["added"] is True
    assert ctx["existing"] == 1


@pytest.mark.asyncio
async def test_hook_can_set_skip_flag():
    runner = HookRunner()

    def set_skip(ctx):
        ctx["skip"] = True

    runner.on("ev", set_skip)
    ctx = await runner.emit("ev", {})
    assert ctx.get("skip") is True


@pytest.mark.asyncio
async def test_register_from_config(capsys):
    runner = HookRunner()
    # Use a real importable function from the standard library
    config_hooks = {
        "start": ["os.path.exists"],
    }
    runner.register_from_config(config_hooks)
    # Verify no load errors were printed
    captured = capsys.readouterr()
    assert "Hook load error" not in captured.err
    # Verify the hook is registered and callable (exists is a valid callable)
    assert len(runner._hooks.get("start", [])) == 1


@pytest.mark.asyncio
async def test_register_from_config_bad_path_logged(capsys):
    runner = HookRunner()
    config_hooks = {
        "start": ["nonexistent.module.func"],
    }
    runner.register_from_config(config_hooks)
    captured = capsys.readouterr()
    assert "Hook load error" in captured.err
