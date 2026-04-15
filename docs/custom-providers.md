# Custom Providers

tinyloom works with any Anthropic-compatible or OpenAI-compatible API endpoint. Set `base_url` to point at your provider.

## Provider detection

tinyloom picks the provider SDK based on these rules:

1. `config.model.provider` wins if set (`"anthropic"` or `"openai"`)
2. If the model name contains `"claude"` -- uses Anthropic SDK
3. Everything else -- uses OpenAI SDK

Most third-party APIs are OpenAI-compatible, so `provider: openai` covers the majority of cases.

## Anthropic-compatible APIs

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-20250514
  base_url: https://my-anthropic-proxy.com/v1
```

Set `ANTHROPIC_API_KEY` in your environment.

## OpenAI-compatible APIs

```yaml
model:
  provider: openai
  model: gpt-4o
  base_url: https://my-openai-proxy.com/v1
```

Set `OPENAI_API_KEY` in your environment.

## Examples

### vLLM

```yaml
model:
  provider: openai
  model: meta-llama/Llama-3-70b-chat-hf
  base_url: http://localhost:8000/v1
  context_window: 8192
```

### Ollama

```yaml
model:
  provider: openai
  model: llama3
  base_url: http://localhost:11434/v1
  context_window: 8192
```

### Together AI

```yaml
model:
  provider: openai
  model: meta-llama/Llama-3-70b-chat-hf
  base_url: https://api.together.xyz/v1
  context_window: 8192
```

Set `OPENAI_API_KEY` to your Together API key.

### Groq

```yaml
model:
  provider: openai
  model: llama-3.1-70b-versatile
  base_url: https://api.groq.com/openai/v1
  context_window: 131072
```

Set `OPENAI_API_KEY` to your Groq API key.

### LM Studio

```yaml
model:
  provider: openai
  model: local-model
  base_url: http://localhost:1234/v1
  context_window: 4096
```

### Azure OpenAI

```yaml
model:
  provider: openai
  model: gpt-4o
  base_url: https://YOUR-RESOURCE.openai.azure.com/openai/deployments/YOUR-DEPLOYMENT/
  context_window: 128000
```

Set `OPENAI_API_KEY` to your Azure API key.

## context_window matters

Set `context_window` to match your model's actual limit. tinyloom uses this value to decide when to trigger compaction. If it is too high, the LLM call may fail with a context overflow. If it is too low, compaction fires unnecessarily.

```yaml
model:
  context_window: 8192  # match your model's actual limit

compaction:
  enabled: true
  threshold: 0.8  # compact at 80% of context_window
```

## Using a cheaper model for compaction

You can use a different (cheaper/faster) model for compaction summaries:

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-20250514
  context_window: 200000

compaction:
  enabled: true
  strategy: summarize
  model: claude-haiku-4-5-20251001
  provider: anthropic
```
