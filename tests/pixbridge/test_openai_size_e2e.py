"""End-to-end size regression tests for OpenAI.

These run ImageClient / the CLI, the size resolver and the real OpenAIProvider
together, mocking only the OpenAI SDK client. Mocking each layer in isolation
previously hid that an explicit size was replaced by the aspect-ratio size.
"""

import base64
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from pixbridge.cli import main
from pixbridge.client import ImageClient
from pixbridge.providers.openai import ASPECT_RATIO_TO_SIZE, validate_openai_size
from pixbridge.size_resolver import RESOLUTION_PRESETS

MODEL = "gpt-image-2"

# (size passed by the caller, size the SDK must receive)
EXPLICIT_SIZES = [
    ("3840x2160", "3840x2160"),
    ("2160p", "3840x2160"),
    ("1080p", "2048x1152"),
    ("720p", "1280x720"),
    ("1152x2048", "1152x2048"),  # portrait
    ("1024x1536", "1024x1536"),  # portrait, 2:3
]


@pytest.fixture
def sdk(tiny_png_bytes, monkeypatch, tmp_path):
    """Mocked OpenAI SDK client; everything above it is real."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                b64_json=base64.b64encode(tiny_png_bytes).decode("ascii"),
                url=None,
                revised_prompt=None,
            )
        ]
    )
    client = MagicMock()
    client.images.generate.return_value = response
    client.images.edit.return_value = response
    with patch("pixbridge.providers.openai.OpenAI", return_value=client):
        yield client


def _sent_size(mock_call) -> str:
    mock_call.assert_called_once()
    return mock_call.call_args.kwargs["size"]


class TestImageClientSize:
    @pytest.mark.parametrize(("size", "expected"), EXPLICIT_SIZES)
    def test_explicit_size_reaches_sdk(self, sdk, sample_prompt, tmp_path, size, expected):
        ImageClient(provider="openai").generate_image(
            sample_prompt, tmp_path, model=MODEL, size=size
        )
        assert _sent_size(sdk.images.generate) == expected

    @pytest.mark.parametrize(("size", "expected"), EXPLICIT_SIZES)
    def test_explicit_size_wins_over_aspect_ratio(
        self, sdk, sample_prompt, tmp_path, size, expected
    ):
        ImageClient(provider="openai").generate_image(
            sample_prompt, tmp_path, model=MODEL, size=size, aspect_ratio="1:1"
        )
        assert _sent_size(sdk.images.generate) == expected

    def test_aspect_ratio_maps_to_size_when_no_size(self, sdk, sample_prompt, tmp_path):
        ImageClient(provider="openai").generate_image(
            sample_prompt, tmp_path, model=MODEL, aspect_ratio="9:16"
        )
        assert _sent_size(sdk.images.generate) == "1152x2048"

    @pytest.mark.parametrize(("size", "expected"), EXPLICIT_SIZES)
    def test_explicit_size_reaches_sdk_with_references(
        self, sdk, sample_prompt, tmp_path, tiny_png_bytes, size, expected
    ):
        ref = tmp_path / "ref.png"
        ref.write_bytes(tiny_png_bytes)
        ImageClient(provider="openai").generate_image_with_references(
            sample_prompt, [ref], tmp_path, model=MODEL, size=size, aspect_ratio="1:1"
        )
        assert _sent_size(sdk.images.edit) == expected

    def test_invalid_explicit_size_raises_instead_of_being_replaced(
        self, sdk, sample_prompt, tmp_path
    ):
        # 1080 is not divisible by 16.
        with pytest.raises(ValueError, match="divisible by 16"):
            ImageClient(provider="openai").generate_image(
                sample_prompt, tmp_path, model=MODEL, size="1920x1080", aspect_ratio="16:9"
            )
        sdk.images.generate.assert_not_called()


class TestCliGenerateSize:
    @pytest.fixture
    def prompt_file(self, tmp_path):
        path = tmp_path / "prompt.yaml"
        path.write_text(
            yaml.dump(
                {
                    "full_prompt": "A mountain landscape",
                    # The YAML always carries an aspect ratio; it must not
                    # override an explicit --size.
                    "generation_notes": {"aspect_ratio": "4:3", "key_requirements": []},
                }
            )
        )
        return path

    def _run(self, prompt_file, tmp_path, *extra: str) -> int:
        argv = [
            "pixbridge", "generate", str(prompt_file),
            "--provider", "openai", "--model", MODEL,
            "--output", str(tmp_path / "out"), *extra,
        ]  # fmt: skip
        with patch("sys.argv", argv):
            return main()

    @pytest.mark.parametrize(("size", "expected"), EXPLICIT_SIZES)
    def test_size_flag_reaches_sdk(self, sdk, prompt_file, tmp_path, size, expected):
        assert self._run(prompt_file, tmp_path, "--size", size) == 0
        assert _sent_size(sdk.images.generate) == expected

    @pytest.mark.parametrize(("size", "expected"), EXPLICIT_SIZES)
    def test_size_flag_wins_over_aspect_ratio_flag(
        self, sdk, prompt_file, tmp_path, size, expected
    ):
        code = self._run(prompt_file, tmp_path, "--size", size, "--aspect-ratio", "1:1")
        assert code == 0
        assert _sent_size(sdk.images.generate) == expected

    def test_yaml_aspect_ratio_used_when_no_size(self, sdk, prompt_file, tmp_path):
        assert self._run(prompt_file, tmp_path) == 0
        assert _sent_size(sdk.images.generate) == "1536x1152"


class TestMappingsAreTrueRatios:
    @pytest.mark.parametrize("preset", sorted(RESOLUTION_PRESETS))
    def test_openai_presets_are_valid_true_16_9(self, preset):
        size, aspect = RESOLUTION_PRESETS[preset]["openai"]
        assert aspect == "16:9"
        validate_openai_size(size)
        w, h = (int(d) for d in size.split("x"))
        assert Fraction(w, h) == Fraction(16, 9)

    @pytest.mark.parametrize(("ratio", "size"), sorted(ASPECT_RATIO_TO_SIZE.items()))
    def test_aspect_ratio_sizes_match_their_ratio(self, ratio, size):
        validate_openai_size(size)
        w, h = (int(d) for d in size.split("x"))
        rw, rh = (int(d) for d in ratio.split(":"))
        assert Fraction(w, h) == Fraction(rw, rh)

    def test_3_2_and_2_3_keep_legacy_sizes(self):
        assert ASPECT_RATIO_TO_SIZE["3:2"] == "1536x1024"
        assert ASPECT_RATIO_TO_SIZE["2:3"] == "1024x1536"
