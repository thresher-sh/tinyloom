from __future__ import annotations
import sys
from typing import TYPE_CHECKING
from tinyloom.core.types import Message

if TYPE_CHECKING:
    from tinyloom.core.config import Config
    from tinyloom.providers.base import LLMProvider

SUMMARY_PROMPT = (
    "Summarize the following conversation concisely. Include:\n" + "- What files were modified\n"
    "- What's been accomplished\n" + "- Key decisions made\n" + "- Errors encountered and how they were resolved\n"
    "- What task is being worked on\n What still needs to be done\n\n"
)

KEEP_RECENT_SUMMARIZE = 4
KEEP_RECENT_TRUNCATE = 10

def estimate_tokens_heuristic(messages: list[Message]) -> int:
    return sum(len(m.content) + sum(len(tc.name) + len(str(tc.input)) for tc in m.tool_calls) for m in messages) // 4

async def maybe_compact(
    provider: LLMProvider,
    messages: list[Message],
    config: Config,
) -> list[Message] | None:
    try:
        current_tokens = await provider.count_tokens(messages)
    except Exception:
        current_tokens = estimate_tokens_heuristic(messages)

    if current_tokens < int(config.model.context_window * config.compaction.threshold):
        return None

    summary_provider = _get_summary_provider(provider, config)

    if config.compaction.strategy == "summarize":
        return await _summarize(summary_provider, messages)
    return _truncate(messages)

def _get_summary_provider(default_provider: LLMProvider, config: Config) -> LLMProvider:
    """Return a separate provider for compaction if config overrides model/provider."""
    comp = config.compaction
    if comp.model is None and comp.provider is None: return default_provider
    from copy import copy
    from tinyloom.providers import create_provider
    mc = copy(config.model)
    if comp.model is not None: mc.model = comp.model
    if comp.provider is not None: mc.provider = comp.provider
    return create_provider(mc)

def _truncate(messages: list[Message]) -> list[Message]:
    return [Message(role="user", content="[Previous conversation was truncated]")] + messages[-KEEP_RECENT_TRUNCATE:]

async def _summarize(provider: LLMProvider, messages: list[Message]) -> list[Message]:
    try:
        text = "\n".join(f"[{m.role}]: {m.content[:500]}" for m in messages)
        result = await provider.chat([Message(role="user", content=SUMMARY_PROMPT + text)], max_tokens=2048)
        return [Message(role="user", content=f"[Conversation summary: {result.content}]")] + messages[-KEEP_RECENT_SUMMARIZE:]
    except Exception as e:
        print(f"Compaction summarize failed, falling back to truncate: {e}", file=sys.stderr)
        return _truncate(messages)
