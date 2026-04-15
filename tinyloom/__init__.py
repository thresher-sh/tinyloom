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
    "Agent", "Config", "ModelConfig", "CompactionConfig", "load_config",
    "Message", "ToolCall", "ToolDef", "StreamEvent", "AgentEvent",
    "Tool", "ToolRegistry", "tool", "get_builtin_tools",
    "HookRunner", "LLMProvider", "create_provider",
]
