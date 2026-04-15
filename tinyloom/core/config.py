from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int = 8192
    context_window: int = 200_000
    temperature: float = 0.0


@dataclass
class CompactionConfig:
    enabled: bool = True
    threshold: float = 0.8
    strategy: str = "summarize"
    model: str | None = None       # None = use main model
    provider: str | None = None    # None = use main provider


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    system_prompt: str = "You are a skilled coding assistant. Be concise."
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
    plugins: list[str] = field(default_factory=list)
    hooks: dict[str, list[str]] = field(default_factory=dict)
    hook_scripts: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    max_turns: int = 200


def load_config(path: str | Path | None = None) -> Config:
    _load_dotenv()
    raw = _load_yaml(path)
    cfg = Config()

    if "model" in raw:
        for k, v in raw["model"].items():
            if hasattr(cfg.model, k):
                setattr(cfg.model, k, v)

    if "compaction" in raw:
        for k, v in raw["compaction"].items():
            if hasattr(cfg.compaction, k):
                setattr(cfg.compaction, k, v)

    for k in ("system_prompt", "max_turns", "plugins", "hooks", "hook_scripts"):
        if k in raw:
            setattr(cfg, k, raw[k])

    _apply_env_vars(cfg)
    return cfg


def _load_yaml(path: str | Path | None) -> dict:
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path("tinyloom.yaml"))
    candidates.append(Path.home() / ".config" / "tinyloom" / "tinyloom.yaml")

    for p in candidates:
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    return {}


def _load_dotenv() -> None:
    """Load .env file into os.environ. Won't override existing vars."""
    for p in (Path(".env"), Path.home() / ".config" / "tinyloom" / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key not in os.environ:
                    os.environ[key] = value
            return  # only load the first .env found


def _apply_env_vars(cfg: Config) -> None:
    # Don't override if api_key was already set (e.g. from YAML)
    if cfg.model.api_key:
        return

    # Check provider-specific first, then the other, so it works with custom base_url setups
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        key = os.environ.get(var)
        if key:
            cfg.model.api_key = key
            return
