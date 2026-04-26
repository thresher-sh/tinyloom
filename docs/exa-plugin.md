# Exa Search Plugin

The Exa plugin registers a `web_search` tool backed by [Exa](https://exa.ai)'s web search API. It gives the agent access to live web results with optional highlights, summaries, and full page text.

## Setup

1. Install the optional dependency:

```bash
uv add 'tinyloom[exa]'
```

2. Set your API key (get one at [dashboard.exa.ai](https://dashboard.exa.ai)):

```bash
export EXA_API_KEY=...
```

Or add it to a `.env` file at the project root.

3. Enable the plugin in `tinyloom.yaml`:

```yaml
plugins:
  - tinyloom.plugins.exa_search
```

If `EXA_API_KEY` is not set when the plugin activates, it logs a warning and skips registering the tool. Tinyloom keeps running.

## What the agent sees

The plugin registers a single tool named `web_search`. The agent provides a `query` and optional filters; the tool returns a markdown-formatted list of hits with title, URL, publish date, author, and content (highlights, summary, or text — whichever was requested).

## Parameters

| Parameter | Type | Notes |
|---|---|---|
| `query` | string (required) | Search query |
| `num_results` | integer | Default 5, max 100 |
| `type` | string | `auto` (default), `neural`, `fast`, `deep`, `deep-lite`, `deep-reasoning`, `instant` |
| `include_domains` / `exclude_domains` | array of strings | Domain allow/deny lists |
| `include_text` / `exclude_text` | array of strings | Phrase must/must not appear in result |
| `category` | string | e.g. `company`, `research paper`, `news`, `personal site`, `financial report`, `people` |
| `start_published_date` / `end_published_date` | ISO 8601 | Date range filter |
| `user_location` | string | Two-letter ISO country code |
| `text` | bool or object | Return page text (default `true`) |
| `highlights` | bool or object | Return relevance-ranked snippets (default `true`) |
| `summary` | bool or object | Return an LLM-generated summary (default `false`) |

`text`, `highlights`, and `summary` can be combined in a single request — Exa supports all three simultaneously.

## Content fallback

For each result, the plugin renders the first non-empty content field in this order: `highlights` → `summary` → `text` (truncated to 1500 chars). This keeps output compact when the agent only needs a snippet.

## Example

```yaml
plugins:
  - tinyloom.plugins.exa_search
```

```
> find recent papers on test-time compute scaling

[agent calls web_search with query="test-time compute scaling", category="research paper", start_published_date="2024-01-01"]
```
