"""Size preset resolution for image generation providers."""

import re

RESOLUTION_PRESETS = {
    "720p":  {"gemini": ("1K", "16:9"), "openai": ("1536x1024", "16:9"), "xai": (None, "16:9"), "vertex": ("1K", "16:9")},
    "1080p": {"gemini": ("1K", "16:9"), "openai": ("1536x1024", "16:9"), "xai": (None, "16:9"), "vertex": ("1K", "16:9")},
    "2160p": {"gemini": ("2K", "16:9"), "openai": ("3840x2160", "16:9"), "xai": (None, "16:9"), "vertex": ("2K", "16:9")},
}


_STANDARD_ASPECTS = {
    "16:9": 16 / 9,
    "4:3": 4 / 3,
    "1:1": 1.0,
    "3:4": 3 / 4,
    "9:16": 9 / 16,
}

_WXH_RE = re.compile(r"^(\d+)x(\d+)$")


def _infer_aspect_ratio(w: int, h: int) -> str:
    """Return the closest standard aspect ratio for the given dimensions."""
    ratio = w / h
    return min(_STANDARD_ASPECTS, key=lambda k: abs(_STANDARD_ASPECTS[k] - ratio))


def _resolve_wxh(w: int, h: int, provider: str) -> tuple[str | None, str]:
    """Map WxH dimensions to provider-specific (size, aspect_ratio).

    Delegates the size mapping to the provider's capability surface
    (:meth:`ProviderCapabilities.native_size`) rather than branching on the
    provider name: bucketed providers (Gemini/Vertex) map onto a named size,
    dimensional providers (OpenAI) validate and pass ``WxH`` through, and
    ratio-only providers (xAI) return ``None``. Unknown providers fall back to
    no size.

    For OpenAI the WxH is validated against gpt-image-2's actual rules (both
    dims divisible by 16, ratio in [1:3, 3:1], max dim 3840); invalid sizes
    raise ``ValueError`` rather than being silently snapped to the nearest
    supported size — silent rewrites masked a bug where 9:16 requests were
    downgraded to 3:4.
    """
    aspect = _infer_aspect_ratio(w, h)

    # Local import keeps size_resolver importable without the provider SDKs and
    # mirrors the credential-free registry pattern.
    from .providers import get_capabilities

    caps = get_capabilities(provider)
    if caps is None:
        # Unknown provider — no size, just aspect
        return (None, aspect)
    return (caps.native_size(w, h), aspect)


def resolve_size_preset(size: str, provider: str) -> tuple[str | None, str | None]:
    """Resolve a size preset to (provider_size, aspect_ratio) or return (size, None) if not a preset."""
    if size in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[size].get(provider, (size, "16:9"))
    m = _WXH_RE.match(size)
    if m:
        return _resolve_wxh(int(m.group(1)), int(m.group(2)), provider)
    return (size, None)
