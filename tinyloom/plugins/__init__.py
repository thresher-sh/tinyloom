from __future__ import annotations
import importlib, sys
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
            ep.load()(agent)
        except Exception as e:
            print(f"Plugin error ({ep.name}): {e}", file=sys.stderr)

def load_plugins_from_config(agent: Agent, plugin_paths: list[str]):
    for path in plugin_paths:
        try:
            module_path, sep, func_name = path.rpartition(":")
            if not sep: module_path, func_name = path, "activate"
            module = importlib.import_module(module_path)
            getattr(module, func_name)(agent)
        except Exception as e:
            print(f"Plugin error ({path}): {e}", file=sys.stderr)
