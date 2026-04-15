from __future__ import annotations
import importlib, inspect, sys
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
