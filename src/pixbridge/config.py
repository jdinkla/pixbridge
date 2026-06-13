"""YAML-based model configuration for image generation providers."""

from pathlib import Path

import yaml


def load_model_config(config_path: Path) -> dict:
    """Read a model_config.yaml file and return its contents.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file is missing the 'providers' key.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "providers" not in data:
        raise ValueError(f"Config file must contain a 'providers' key: {config_path}")

    return data


def get_configured_model(config: dict | None, provider: str) -> str | None:
    """Extract the default_model for a provider from a loaded config.

    Args:
        config: Parsed config dictionary (from load_model_config), or None.
        provider: Provider name (e.g. "gemini", "openai").

    Returns:
        The configured default_model string, or None if not found.
    """
    if config is None:
        return None

    providers = config.get("providers")
    if not isinstance(providers, dict):
        return None

    provider_config = providers.get(provider)
    if not isinstance(provider_config, dict):
        return None

    return provider_config.get("default_model")
