from __future__ import annotations

import argparse


from tinyloom.cli import build_parser, detect_mode


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_build_parser_no_args():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.prompt is None
    assert args.model is None
    assert args.provider is None
    assert args.stdin is False
    assert args.no_plugins is False
    assert args.system is None


def test_build_parser_prompt_arg():
    parser = build_parser()
    args = parser.parse_args(["hello world"])
    assert args.prompt == "hello world"


def test_build_parser_model_flag():
    parser = build_parser()
    args = parser.parse_args(["-m", "claude-3-opus-latest"])
    assert args.model == "claude-3-opus-latest"


def test_build_parser_model_flag_long():
    parser = build_parser()
    args = parser.parse_args(["--model", "gpt-4o"])
    assert args.model == "gpt-4o"


def test_build_parser_provider_flag():
    parser = build_parser()
    args = parser.parse_args(["-p", "openai"])
    assert args.provider == "openai"


def test_build_parser_provider_flag_long():
    parser = build_parser()
    args = parser.parse_args(["--provider", "anthropic"])
    assert args.provider == "anthropic"


def test_build_parser_stdin_flag():
    parser = build_parser()
    args = parser.parse_args(["--stdin"])
    assert args.stdin is True


def test_build_parser_no_plugins_flag():
    parser = build_parser()
    args = parser.parse_args(["--no-plugins"])
    assert args.no_plugins is True


def test_build_parser_system_flag():
    parser = build_parser()
    args = parser.parse_args(["--system", "You are a pirate"])
    assert args.system == "You are a pirate"


def test_build_parser_config_flag():
    parser = build_parser()
    args = parser.parse_args(["--config", "/path/to/config.yaml"])
    assert args.config == "/path/to/config.yaml"


def test_build_parser_json_flag():
    parser = build_parser()
    args = parser.parse_args(["--json"])
    assert args.json is True


# ---------------------------------------------------------------------------
# detect_mode tests
# ---------------------------------------------------------------------------

def _ns(**kwargs) -> argparse.Namespace:
    defaults = {"prompt": None, "stdin": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_detect_mode_headless_with_prompt():
    args = _ns(prompt="do something")
    assert detect_mode(args) == "headless"


def test_detect_mode_headless_with_stdin():
    args = _ns(stdin=True)
    assert detect_mode(args) == "headless"


def test_detect_mode_headless_with_prompt_and_stdin():
    args = _ns(prompt="hi", stdin=True)
    assert detect_mode(args) == "headless"


def test_detect_mode_interactive_no_prompt():
    args = _ns()
    assert detect_mode(args) == "interactive"
