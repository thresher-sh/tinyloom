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
    api_key_env: str | None = None  # custom env var name for API key
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


def _apply_env_vars(cfg: Config) -> None:
    if cfg.model.provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
    else:
        key = os.environ.get("OPENAI_API_KEY")
    if key:
        cfg.model.api_key = key
