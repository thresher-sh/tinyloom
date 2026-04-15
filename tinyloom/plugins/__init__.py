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
            module_path, sep, func_name = path.rpartition(":")
            if not sep:
                # No colon: the whole path is the module, use default "activate"
                module_path = path
                func_name = "activate"
            module = importlib.import_module(module_path)
            fn = getattr(module, func_name)
            fn(agent)
        except Exception as e:
            print(f"Plugin error ({path}): {e}", file=sys.stderr)
