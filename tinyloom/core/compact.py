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
