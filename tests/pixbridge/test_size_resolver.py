"""Tests for pixbridge.size_resolver — size preset resolution."""

import pytest

from pixbridge.size_resolver import (
    RESOLUTION_PRESETS,
    _infer_aspect_ratio,
    resolve_size_preset,
)


class TestResolveSizePreset:
    @pytest.mark.parametrize("preset,provider,expected_size,expected_aspect", [
        ("720p", "gemini", "1K", "16:9"),
        ("1080p", "gemini", "1K", "16:9"),
        ("2160p", "gemini", "2K", "16:9"),
        ("720p", "openai", "1536x1024", "16:9"),
        ("1080p", "openai", "1536x1024", "16:9"),
        ("2160p", "openai", "3840x2160", "16:9"),
        ("720p", "xai", None, "16:9"),
        ("1080p", "vertex", "1K", "16:9"),
        ("2160p", "vertex", "2K", "16:9"),
    ])
    def test_known_presets(self, preset, provider, expected_size, expected_aspect):
        size, aspect = resolve_size_preset(preset, provider)
        assert size == expected_size
        assert aspect == expected_aspect

    @pytest.mark.parametrize("size_value", ["1K", "2K"])
    def test_passthrough_non_preset(self, size_value):
        size, aspect = resolve_size_preset(size_value, "gemini")
        assert size == size_value
        assert aspect is None

    def test_unknown_provider_with_preset(self):
        size, aspect = resolve_size_preset("1080p", "unknown_provider")
        assert size == "1080p"
        assert aspect == "16:9"

    @pytest.mark.parametrize("wxh,provider,expected_size,expected_aspect", [
        ("1920x1080", "gemini", "2K", "16:9"),
        ("1024x1024", "gemini", "1K", "1:1"),
        # OpenAI sizes now pass through unchanged — no silent snap to closest.
        ("1024x1024", "openai", "1024x1024", "1:1"),
        ("3840x2160", "openai", "3840x2160", "16:9"),
        ("2560x1440", "openai", "2560x1440", "16:9"),
        ("1152x2048", "openai", "1152x2048", "9:16"),   # true 9:16
        ("2048x1152", "openai", "2048x1152", "16:9"),   # true 16:9
        ("720x1280", "openai", "720x1280", "9:16"),     # rule-based, not in recommended
        ("1088x1920", "openai", "1088x1920", "9:16"),   # rule-based, not in recommended
        ("1920x1080", "xai", None, "16:9"),
        ("1920x1080", "vertex", "2K", "16:9"),
        ("800x600", "gemini", "1K", "4:3"),
    ])
    def test_wxh_dimensions(self, wxh, provider, expected_size, expected_aspect):
        size, aspect = resolve_size_preset(wxh, provider)
        assert size == expected_size
        assert aspect == expected_aspect

    @pytest.mark.parametrize("wxh,reason_fragment", [
        ("1080x1920", "divisible by 16"),    # 1080 not /16
        ("1920x1080", "divisible by 16"),    # 1080 not /16
        ("2048x512", "aspect ratio"),        # ratio 4:1
        ("4096x4096", "max dimension"),      # exceeds 3840
    ])
    def test_invalid_openai_wxh_raises(self, wxh, reason_fragment):
        # OpenAI no longer silently snaps invalid sizes to the closest allowed
        # one — invalid input raises so the caller can fix the request.
        with pytest.raises(ValueError, match=reason_fragment):
            resolve_size_preset(wxh, "openai")


class TestInferAspectRatio:
    @pytest.mark.parametrize("w,h,expected", [
        (1920, 1080, "16:9"),
        (1080, 1920, "9:16"),
        (1024, 1024, "1:1"),
        (1024, 768, "4:3"),
        (768, 1024, "3:4"),
    ])
    def test_infer_aspect_ratio(self, w, h, expected):
        assert _infer_aspect_ratio(w, h) == expected


class TestResolutionPresets:
    def test_all_presets_have_all_providers(self):
        expected_providers = {"gemini", "openai", "xai", "vertex"}
        for preset, mapping in RESOLUTION_PRESETS.items():
            assert set(mapping.keys()) == expected_providers, f"Preset {preset} missing providers"
