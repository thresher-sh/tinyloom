from __future__ import annotations
import os, yaml
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

@dataclass
class ModelConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int = 8192
    context_window: int = 200_000
    temperature: float = 0.0
    sync_http: bool = False

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

    def get_system_prompt(self, tool_names: list[str]) -> str:
        if not tool_names:
            return self.system_prompt
        return f"{self.system_prompt}\n\nAvailable tools: {', '.join(sorted(tool_names))}"

def _apply(target, data: dict):
    for k, v in data.items():
        if hasattr(target, k):
            setattr(target, k, v)

def load_config(path: str | Path | None = None) -> Config:
    load_dotenv(Path(".env"), override=False)
    raw = _load_yaml(path)
    cfg = Config()

    if "model" in raw: _apply(cfg.model, raw["model"])
    if "compaction" in raw: _apply(cfg.compaction, raw["compaction"])

    for k in ("system_prompt", "max_turns", "plugins", "hooks", "hook_scripts"):
        if k in raw:
            setattr(cfg, k, raw[k])

    _apply_env_vars(cfg)
    return cfg

def _load_yaml(path: str | Path | None) -> dict:
    candidates = [Path("tinyloom.yaml"), Path.home() / ".config" / "tinyloom" / "tinyloom.yaml"]
    if path:
        candidates.insert(0, Path(path))
    for p in candidates:
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    return {}

def _apply_env_vars(cfg: Config) -> None:
    if cfg.model.api_key: return
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        if key := os.environ.get(var):
            cfg.model.api_key = key
            return
