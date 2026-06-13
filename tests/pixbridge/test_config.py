"""Tests for pixbridge.config — YAML model configuration."""


import pytest
import yaml

from pixbridge.config import get_configured_model, load_model_config


class TestLoadModelConfig:
    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "providers": {
                "gemini": {"default_model": "gemini-3-pro-image-preview"},
                "openai": {"default_model": "gpt-image-2"},
            }
        }))

        config = load_model_config(config_file)

        assert "providers" in config
        assert config["providers"]["gemini"]["default_model"] == "gemini-3-pro-image-preview"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_model_config(tmp_path / "nonexistent.yaml")

    def test_missing_providers_key(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"models": {"gemini": "foo"}}))

        with pytest.raises(ValueError, match="providers"):
            load_model_config(config_file)

    def test_empty_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        with pytest.raises(ValueError, match="providers"):
            load_model_config(config_file)


class TestGetConfiguredModel:
    def test_returns_model_for_known_provider(self):
        config = {"providers": {"gemini": {"default_model": "my-model"}}}
        assert get_configured_model(config, "gemini") == "my-model"

    def test_returns_none_for_unknown_provider(self):
        config = {"providers": {"gemini": {"default_model": "my-model"}}}
        assert get_configured_model(config, "xai") is None

    def test_returns_none_when_config_is_none(self):
        assert get_configured_model(None, "gemini") is None

    def test_returns_none_when_no_default_model(self):
        config = {"providers": {"gemini": {"other_key": "value"}}}
        assert get_configured_model(config, "gemini") is None

    def test_returns_none_when_provider_entry_is_not_dict(self):
        config = {"providers": {"gemini": "not-a-dict"}}
        assert get_configured_model(config, "gemini") is None

    def test_returns_none_when_providers_is_not_dict(self):
        config = {"providers": "bad"}
        assert get_configured_model(config, "gemini") is None
