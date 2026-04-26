"""Exa search plugin — registers a `web_search` tool backed by Exa's web search API.

Config (tinyloom.yaml):
    plugins:
      - tinyloom.plugins.exa_search

Env:
    EXA_API_KEY=...

Install:
    uv add 'tinyloom[exa]'
"""
from __future__ import annotations
import os, sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from tinyloom.core.tools import Tool

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent

INTEGRATION_HEADER = "tinyloom"

@dataclass
class SearchHit:
    title: str
    url: str
    published_date: str | None
    author: str | None
    content: str

    def render(self) -> str:
        head = f"## {self.title or '(untitled)'}\n{self.url}"
        meta = " · ".join(x for x in (self.published_date, self.author) if x)
        if meta: head += f"\n{meta}"
        if self.content: head += f"\n\n{self.content}"
        return head

def _extract_content(result: Any) -> str:
    # Cascade through whatever the API returned: highlights → summary → text.
    highlights = getattr(result, "highlights", None) or []
    if highlights: return "\n".join(f"- {h}" for h in highlights)
    summary = getattr(result, "summary", None)
    if summary: return str(summary).strip()
    text = getattr(result, "text", None)
    if text:
        text = str(text).strip()
        return text if len(text) <= 1500 else text[:1500] + "…"
    return ""

def _hit_from_result(result: Any) -> SearchHit:
    return SearchHit(
        title=getattr(result, "title", "") or "",
        url=getattr(result, "url", "") or "",
        published_date=getattr(result, "published_date", None),
        author=getattr(result, "author", None),
        content=_extract_content(result),
    )

def _build_search_kwargs(inp: dict) -> dict:
    kwargs: dict = {"num_results": int(inp.get("num_results", 5))}
    type_ = inp.get("type")
    if type_: kwargs["type"] = type_
    for src, dst in (
        ("include_domains", "include_domains"),
        ("exclude_domains", "exclude_domains"),
        ("include_text", "include_text"),
        ("exclude_text", "exclude_text"),
    ):
        v = inp.get(src)
        if v: kwargs[dst] = v
    category = inp.get("category")
    if category: kwargs["category"] = category
    start = inp.get("start_published_date")
    if start: kwargs["start_published_date"] = start
    end = inp.get("end_published_date")
    if end: kwargs["end_published_date"] = end
    user_location = inp.get("user_location")
    if user_location: kwargs["user_location"] = user_location

    text = inp.get("text", True)
    highlights = inp.get("highlights", True)
    summary = inp.get("summary", False)
    if text: kwargs["text"] = text if isinstance(text, dict) else True
    if highlights: kwargs["highlights"] = highlights if isinstance(highlights, dict) else True
    if summary: kwargs["summary"] = summary if isinstance(summary, dict) else True
    return kwargs

def _make_search(api_key: str):
    def search(inp: dict) -> str:
        try:
            from exa_py import Exa
        except ImportError:
            return "Error: 'exa-py' not installed. Install with: uv add 'tinyloom[exa]'"
        query = (inp.get("query") or "").strip()
        if not query: return "Error: 'query' is required"
        client = Exa(api_key=api_key)
        client.headers["x-exa-integration"] = INTEGRATION_HEADER
        kwargs = _build_search_kwargs(inp)
        try:
            response = client.search_and_contents(query, **kwargs)
        except Exception as e:
            return f"Error: Exa search failed: {type(e).__name__}: {e}"
        results = getattr(response, "results", None) or []
        if not results: return f"No results for: {query}"
        hits = [_hit_from_result(r) for r in results]
        return "\n\n".join(h.render() for h in hits)
    return search

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "num_results": {"type": "integer", "description": "Max results (default 5, max 100)"},
        "type": {"type": "string", "enum": ["auto", "neural", "fast", "deep", "deep-lite", "deep-reasoning", "instant"], "description": "Search type (default auto)"},
        "include_domains": {"type": "array", "items": {"type": "string"}, "description": "Only return results from these domains"},
        "exclude_domains": {"type": "array", "items": {"type": "string"}, "description": "Exclude results from these domains"},
        "include_text": {"type": "array", "items": {"type": "string"}, "description": "Result must include this text (1 phrase, ≤5 words)"},
        "exclude_text": {"type": "array", "items": {"type": "string"}, "description": "Result must not include this text"},
        "category": {"type": "string", "description": "Filter by category (e.g. company, research paper, news, personal site, financial report, people)"},
        "start_published_date": {"type": "string", "description": "ISO 8601, e.g. 2024-01-01"},
        "end_published_date": {"type": "string", "description": "ISO 8601, e.g. 2024-12-31"},
        "user_location": {"type": "string", "description": "Two-letter ISO country code"},
        "text": {"description": "Return page text. Boolean or {maxCharacters, includeHtmlTags}"},
        "highlights": {"description": "Return highlights. Boolean or {numSentences, highlightsPerUrl, query}"},
        "summary": {"description": "Return a summary. Boolean or {query, schema}"},
    },
    "required": ["query"],
}

DESCRIPTION = (
    "Search the web with Exa AI. Returns ranked results with titles, URLs, publish dates, and content "
    "(highlights/summary/text). Supports neural and keyword search, domain and date filters, and category "
    "filters (company, research paper, news, etc.). Use this when you need fresh or external information."
)

def activate(agent: Agent):
    api_key = os.environ.get("EXA_API_KEY", "").strip()
    if not api_key:
        print("Exa plugin: EXA_API_KEY not set; skipping web_search tool.", file=sys.stderr)
        return
    agent.tools.register(Tool(
        name="web_search",
        description=DESCRIPTION,
        input_schema=INPUT_SCHEMA,
        function=_make_search(api_key),
    ))
