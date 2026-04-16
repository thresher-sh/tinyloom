"""Mask plugin — replaces configured words with asterisks in TUI output.

Config (tinyloom.yaml):
    mask_words:
      - josephduncan
      - /Users/josephduncan

Or env: TINYLOOM_MASK="josephduncan,/Users/josephduncan"
"""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent

def activate(agent: Agent):
    words: list[str] = [w for w in os.environ.get("TINYLOOM_MASK", "").split(",") if w]
    from tinyloom.core.config import _load_yaml
    words.extend(_load_yaml(None).get("mask_words", []))
    if not words: return

    def mask(text: str) -> str:
        for w in words: text = text.replace(w, "*" * len(w))
        return text

    if not hasattr(agent, "_tui_text_filters"): agent._tui_text_filters = []
    agent._tui_text_filters.append(mask)
