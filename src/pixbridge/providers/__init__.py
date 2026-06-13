"""Image generation providers registry."""

from typing import Literal

from .base import (
    BaseImageProvider,
    GenerationResult,
    ImageProvider,
    ProviderCapabilities,
)
from .gemini import GEMINI_CAPABILITIES, GeminiProvider
from .openai import OPENAI_CAPABILITIES, OpenAIProvider
from .xai import XAI_CAPABILITIES, XAIProvider

ProviderName = Literal["gemini", "openai", "xai", "vertex"]

# Provider registry. Eagerly-loaded providers are listed here; opt-in
# providers (requiring extra setup, e.g. GCP credentials) register lazily.
_PROVIDERS: dict[str, type[BaseImageProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "xai": XAIProvider,
}

# Names of providers that can be loaded on demand via _ensure_provider.
_LAZY_PROVIDERS: tuple[str, ...] = ("vertex",)


def _ensure_provider(name: str) -> None:
    """Import and register a provider if not already loaded."""
    if name in _PROVIDERS:
        return
    if name == "vertex":
        from .vertex import VertexProvider
        _PROVIDERS["vertex"] = VertexProvider
    else:
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available providers: {list_providers()}"
        )


def get_provider(name: str, api_key: str | None = None) -> BaseImageProvider:
    """Get a provider instance by name.

    Args:
        name: Provider name (gemini, openai, xai, vertex).
        api_key: Optional API key to pass to the provider.

    Returns:
        Provider instance.

    Raises:
        ValueError: If provider name is not recognized.
    """
    _ensure_provider(name)
    provider_class = _PROVIDERS[name]
    return provider_class(api_key=api_key)


def list_providers() -> list[str]:
    """List all provider names, including opt-in ones that aren't loaded yet.

    Returns:
        Sorted list of provider names known to the registry.
    """
    return sorted(set(_PROVIDERS) | set(_LAZY_PROVIDERS))


def get_capabilities(name: str) -> ProviderCapabilities | None:
    """Return a provider's capability surface by name.

    Unlike :func:`get_provider`, this never instantiates the provider and
    requires no credentials — it returns the shared, declarative
    :class:`ProviderCapabilities` object. This lets credential-free callers
    (e.g. ``size_resolver``) reason about a provider's size rules without
    branching on the provider name themselves.

    Vertex shares Gemini's capabilities. Unknown names return ``None`` so
    callers can fall back gracefully.
    """
    if name in ("gemini", "vertex"):
        return GEMINI_CAPABILITIES
    if name == "openai":
        return OPENAI_CAPABILITIES
    if name == "xai":
        return XAI_CAPABILITIES
    return None


__all__ = [
    "BaseImageProvider",
    "GeminiProvider",
    "GenerationResult",
    "ImageProvider",
    "OpenAIProvider",
    "ProviderCapabilities",
    "ProviderName",
    "XAIProvider",
    "get_capabilities",
    "get_provider",
    "list_providers",
]
