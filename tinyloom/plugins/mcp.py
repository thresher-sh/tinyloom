from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tinyloom.core.tools import Tool

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


def _load_mcp_json() -> dict:
    candidates = [Path(".mcp.json"), Path.home() / ".config" / "tinyloom" / ".mcp.json"]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text())
    return {}


async def _connect_and_register(agent: Agent, name: str, config: dict):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        print(
            "MCP plugin: 'mcp' package not installed. Install with: uv add 'tinyloom[mcp]'",
            file=sys.stderr,
        )
        return

    server_params = StdioServerParameters(
        command=config["command"],
        args=config.get("args", []),
        env=config.get("env"),
    )

    try:
        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = await ClientSession(read_stream, write_stream).__aenter__()
        await session.initialize()
        mcp_tools = await session.list_tools()

        for mt in mcp_tools.tools:
            tool_name = mt.name
            tool_session = session

            async def call_mcp(inp: dict, _name=tool_name, _session=tool_session) -> str:
                result = await _session.call_tool(_name, arguments=inp)
                return "\n".join(
                    block.text for block in result.content if hasattr(block, "text")
                )

            agent.tools.register(Tool(
                name=f"mcp_{tool_name}",
                description=mt.description or f"MCP tool: {tool_name}",
                input_schema=mt.inputSchema or {"type": "object", "properties": {}},
                function=call_mcp,
            ))
    except Exception as e:
        print(f"MCP server '{name}' failed: {e}", file=sys.stderr)


def activate(agent: Agent):
    import asyncio

    mcp_config = _load_mcp_json()
    servers = mcp_config.get("mcpServers", {})

    for server_name, server_config in servers.items():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_connect_and_register(agent, server_name, server_config))
            else:
                asyncio.run(_connect_and_register(agent, server_name, server_config))
        except Exception as e:
            print(f"MCP server '{server_name}' failed: {e}", file=sys.stderr)
