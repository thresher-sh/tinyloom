"""Tests for tinyloom.core.config."""

from __future__ import annotations


from tinyloom.core.config import (
    CompactionConfig,
    Config,
    ModelConfig,
    load_config,
)


class TestDefaults:
    def test_config_defaults(self):
        cfg = Config()
        assert cfg.system_prompt == "You are a skilled coding assistant. Be concise."
        assert cfg.max_turns == 200
        assert cfg.plugins == []
        assert cfg.hooks == {}

    def test_model_config_defaults(self):
        mc = ModelConfig()
        assert mc.provider == "anthropic"
        assert mc.model == "claude-sonnet-4-20250514"
        assert mc.base_url is None
        assert mc.api_key is None
        assert mc.max_tokens == 8192
        assert mc.context_window == 200_000
        assert mc.temperature == 0.0

    def test_compaction_config_defaults(self):
        cc = CompactionConfig()
        assert cc.enabled is True
        assert cc.threshold == 0.8
        assert cc.strategy == "summarize"


class TestLoadConfig:
    def test_load_config_no_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = load_config()
        assert cfg.model.provider == "anthropic"
        assert cfg.max_turns == 200
        assert cfg.model.api_key is None

    def test_load_config_from_yaml_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        yaml_content = """
model:
  provider: openai
  model: gpt-4o
  max_tokens: 4096
max_turns: 50
"""
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.model.provider == "openai"
        assert cfg.model.model == "gpt-4o"
        assert cfg.model.max_tokens == 4096
        assert cfg.max_turns == 50

    def test_load_config_from_explicit_path(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        yaml_content = """
model:
  provider: anthropic
  model: claude-opus-4-20250514
"""
        p = tmp_path / "custom.yaml"
        p.write_text(yaml_content)
        cfg = load_config(path=p)
        assert cfg.model.model == "claude-opus-4-20250514"

    def test_env_var_anthropic_api_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = load_config()
        assert cfg.model.api_key == "sk-ant-test"

    def test_env_var_openai_api_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        yaml_content = "model:\n  provider: openai\n"
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.model.api_key == "sk-openai-test"

    def test_partial_yaml_keeps_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        yaml_content = "max_turns: 100\n"
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.max_turns == 100
        assert cfg.model.provider == "anthropic"
        assert cfg.model.max_tokens == 8192
        assert cfg.compaction.enabled is True

    def test_system_prompt_from_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        yaml_content = 'system_prompt: "You are a helpful bot."\n'
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.system_prompt == "You are a helpful bot."

    def test_compaction_from_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        yaml_content = "compaction:\n  enabled: false\n  threshold: 0.5\n"
        (tmp_path / "tinyloom.yaml").write_text(yaml_content)
        cfg = load_config()
        assert cfg.compaction.enabled is False
        assert cfg.compaction.threshold == 0.5
