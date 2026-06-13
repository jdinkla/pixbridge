"""Multi-provider image generation tool for presentation slides."""

from .client import GeminiImageClient, ImageClient
from .models import GenerationNotes, ImagePrompt, ImagePromptSections
from .providers import (
    GenerationResult,
    ProviderCapabilities,
    get_provider,
    list_providers,
)
from .size_resolver import resolve_size_preset

__all__ = [
    "GeminiImageClient",  # Backward compatibility
    "GenerationNotes",
    "GenerationResult",
    "ImageClient",
    "ImagePrompt",
    "ImagePromptSections",
    "ProviderCapabilities",
    "get_provider",
    "list_providers",
    "resolve_size_preset",
]
