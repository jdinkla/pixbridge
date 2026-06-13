"""Tests for the uniform provider capability surface (TASK-42.2).

Covers ProviderCapabilities' size methods (validate_size, recommended_sizes,
aspect_to_size, max_dim, native_size) and the credential-free get_capabilities
registry that lets shared code reason about providers without instantiating them.
"""

import pytest

from pixbridge.providers import get_capabilities
from pixbridge.providers.gemini import GEMINI_CAPABILITIES
from pixbridge.providers.openai import OPENAI_CAPABILITIES
from pixbridge.providers.xai import XAI_CAPABILITIES


class TestGetCapabilities:
    @pytest.mark.parametrize("name,expected", [
        ("openai", OPENAI_CAPABILITIES),
        ("gemini", GEMINI_CAPABILITIES),
        ("xai", XAI_CAPABILITIES),
        ("vertex", GEMINI_CAPABILITIES),  # vertex shares gemini's surface
    ])
    def test_known_providers(self, name, expected):
        assert get_capabilities(name) is expected

    def test_unknown_provider_returns_none(self):
        assert get_capabilities("nope") is None

    def test_requires_no_credentials(self, monkeypatch):
        # Even with no env vars set, capability lookup must not raise — it
        # never instantiates a provider. Vertex is the credential-sensitive one.
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        assert get_capabilities("vertex") is GEMINI_CAPABILITIES


class TestValidateSize:
    @pytest.mark.parametrize("size", ["1152x2048", "2048x1152", "1024x1024"])
    def test_openai_rule_based_accepts_conformant(self, size):
        OPENAI_CAPABILITIES.validate_size(size)  # no raise

    @pytest.mark.parametrize("size,fragment", [
        ("1080x1920", "divisible by 16"),
        ("2048x512", "aspect ratio"),
        ("4096x4096", "max dimension"),
    ])
    def test_openai_rejects_invalid(self, size, fragment):
        with pytest.raises(ValueError, match=fragment):
            OPENAI_CAPABILITIES.validate_size(size)

    @pytest.mark.parametrize("size", ["1K", "2K"])
    def test_gemini_fixed_list_accepts(self, size):
        GEMINI_CAPABILITIES.validate_size(size)  # no raise

    def test_gemini_fixed_list_rejects(self):
        with pytest.raises(ValueError, match="Invalid size"):
            GEMINI_CAPABILITIES.validate_size("3K")

    def test_xai_accepts_anything(self):
        # Empty `sizes`, no validator → size is unconstrained.
        XAI_CAPABILITIES.validate_size("whatever")  # no raise


class TestRecommendedSizes:
    def test_openai_returns_recommended_list(self):
        sizes = OPENAI_CAPABILITIES.recommended_sizes()
        assert "1152x2048" in sizes and "2048x1152" in sizes

    def test_returns_copy(self):
        sizes = OPENAI_CAPABILITIES.recommended_sizes()
        sizes.append("mutation")
        assert "mutation" not in OPENAI_CAPABILITIES.recommended_sizes()

    def test_xai_empty(self):
        assert XAI_CAPABILITIES.recommended_sizes() == []


class TestAspectToSize:
    @pytest.mark.parametrize("ratio,expected", [
        ("16:9", "2048x1152"),
        ("9:16", "1152x2048"),
        ("2:3", "1024x1536"),
        ("1:1", "1024x1024"),
    ])
    def test_openai_maps(self, ratio, expected):
        assert OPENAI_CAPABILITIES.aspect_to_size(ratio) == expected

    def test_openai_unknown_ratio_is_none(self):
        assert OPENAI_CAPABILITIES.aspect_to_size("21:9") is None

    def test_gemini_has_no_map(self):
        # Gemini passes the ratio to the API directly — no WxH translation.
        assert GEMINI_CAPABILITIES.aspect_to_size("16:9") is None

    def test_xai_has_no_map(self):
        assert XAI_CAPABILITIES.aspect_to_size("16:9") is None


class TestMaxDim:
    def test_openai(self):
        assert OPENAI_CAPABILITIES.max_dim() == 3840

    def test_gemini_none(self):
        assert GEMINI_CAPABILITIES.max_dim() is None

    def test_xai_none(self):
        assert XAI_CAPABILITIES.max_dim() is None


class TestNativeSize:
    @pytest.mark.parametrize("w,h", [(1152, 2048), (2048, 1152), (1024, 1024)])
    def test_openai_passes_wxh_through(self, w, h):
        assert OPENAI_CAPABILITIES.native_size(w, h) == f"{w}x{h}"

    def test_openai_validates(self):
        with pytest.raises(ValueError, match="divisible by 16"):
            OPENAI_CAPABILITIES.native_size(1080, 1920)

    @pytest.mark.parametrize("w,h,expected", [
        (1920, 1080, "2K"),
        (1024, 1024, "1K"),
        (800, 600, "1K"),
        (3840, 2160, "2K"),
    ])
    def test_gemini_buckets(self, w, h, expected):
        assert GEMINI_CAPABILITIES.native_size(w, h) == expected

    def test_xai_returns_none(self):
        assert XAI_CAPABILITIES.native_size(1920, 1080) is None
