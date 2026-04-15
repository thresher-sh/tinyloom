# MCP Plugin

The MCP (Model Context Protocol) plugin connects to MCP servers and registers their tools with the agent.

## Setup

1. Enable the plugin and install the MCP dependency:

```bash
uv add 'tinyloom[mcp]'
```

2. Add to your `tinyloom.yaml`:

```yaml
plugins:
  - tinyloom.plugins.mcp
```

3. Create a `.mcp.json` config file.

## Config

The `.mcp.json` file is loaded from (first match wins):

1. `./.mcp.json` (project root)
2. `~/.config/tinyloom/.mcp.json` (global)

Format:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "command-to-run",
      "args": ["arg1", "arg2"],
      "env": {
        "KEY": "value"
      }
    }
  }
}
```

## Tool naming

MCP tools are registered with an `mcp_` prefix. If the MCP server exposes a tool called `read_file`, it becomes `mcp_read_file` in tinyloom.

## Example: filesystem server

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/path/to/allowed/directory"
      ]
    }
  }
}
```

## Example: multiple servers

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_..."
      }
    }
  }
}
```

## How it works

When the plugin activates:

1. It reads `.mcp.json`
2. For each server, it launches the process using `StdioServerParameters`
3. It calls `list_tools()` on each server
4. Each discovered tool is wrapped and registered in the agent's `ToolRegistry`
5. Tool calls are forwarded to the MCP server, results are returned as text

## Error handling

- If the `mcp` package is not installed, the plugin logs a message to stderr and skips
- If a server fails to connect, it logs the error and continues with other servers
- Individual tool call failures are returned as error strings to the LLM
