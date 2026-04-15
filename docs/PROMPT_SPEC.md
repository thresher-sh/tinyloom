ok we are going to make this in python. I need you to deep research ultrathink ultraplan this...
I want implementation plan for this that I can take to claude code.

- Extremely small agent, small codebase.
- Python stack.
- Works with any openai, anthropic api supported LLM inference endpoint
- Has only a few built in tools: read, write, edit, grep, bash, exec...
- exec launches a copy of itself with some config/prompt. for launching subagents essentially...
- Supports .mcp.json for tool extension.
- Supports hooks in agent lifecycle for example (pretool, posttool, start, stop)
- Supports extensions or plugins so others can add features we don't think about or care about.
- Supports compaction when context window approaches some % of total context window for a model.
- Config via tinyloom.yaml
- small TUI for interactive mode
- headless cli call mode, with json stream output showing all messages and tool calls and responses and final response etc.

One example I like is this: https://ampcode.com/notes/how-to-build-an-agent