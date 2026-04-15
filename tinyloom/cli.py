from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from tinyloom import __version__
from tinyloom.core.config import load_config
from tinyloom.core.tools import ToolRegistry, get_builtin_tools
from tinyloom.core.hooks import HookRunner
from tinyloom.core.agent import Agent
from tinyloom.plugins import load_plugins, load_plugins_from_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tinyloom", description="tinyloom - tiny coding agent")
    parser.add_argument("prompt", nargs="?", help="Prompt (triggers headless mode)")
    parser.add_argument("-m", "--model", help="Override model")
    parser.add_argument("-p", "--provider", help="Override provider")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--stdin", action="store_true", help="Read prompt from stdin")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--json", action="store_true", help="Force JSON output")
    parser.add_argument("--no-plugins", action="store_true", help="Disable all plugins")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version=f"tinyloom {__version__}")
    return parser


def detect_mode(args: argparse.Namespace) -> str:
    if args.prompt or args.stdin:
        return "headless"
    return "interactive"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130


async def _run(args: argparse.Namespace) -> int:
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    config = load_config(args.config)
    if args.model:
        config.model.model = args.model
    if args.provider:
        config.model.provider = args.provider
    if args.system:
        config.system_prompt = args.system

    registry = ToolRegistry()
    for t in get_builtin_tools():
        registry.register(t)

    hooks = HookRunner()
    hooks.register_from_config(config.hooks)

    from tinyloom.providers import create_provider
    provider = create_provider(config.model)

    agent = Agent(config=config, provider=provider, tools=registry, hooks=hooks)

    if not args.no_plugins:
        load_plugins(agent)
        load_plugins_from_config(agent, config.plugins)

    mode = detect_mode(args)
    if mode == "headless":
        prompt = args.prompt
        if args.stdin:
            prompt = sys.stdin.read().strip()
        if not prompt:
            print("Error: no prompt provided", file=sys.stderr)
            return 1
        await _run_headless(agent, prompt)
    else:
        from tinyloom.tui import run_tui
        await run_tui(agent)
    return 0


async def _run_headless(agent: Agent, prompt: str):
    async for evt in agent.run(prompt):
        print(json.dumps(evt.to_dict()), flush=True)
