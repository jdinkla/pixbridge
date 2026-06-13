"""Tests for pixbridge.consistency_check — prompt building, generation, CLI."""

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

from pixbridge.consistency_check import (
    ConsistencyResult,
    build_consistency_prompt,
    normalize_style_label,
    run_consistency_check,
)
from pixbridge.models import ImagePrompt

# --- normalize_style_label ---


class TestNormalizeStyleLabel:
    def test_preset_name_unchanged(self):
        assert normalize_style_label("anime-dark") == "anime-dark"

    def test_md_file_path(self):
        assert normalize_style_label("prompts/style-transfer/anime/anime-dark.md") == "anime-dark"

    def test_relative_path(self):
        assert normalize_style_label("./styles/victorian-mystery-anime.md") == "victorian-mystery-anime"

    def test_bare_md_extension(self):
        assert normalize_style_label("custom-style.md") == "custom-style"

    def test_path_without_md(self):
        assert normalize_style_label("some/dir/style-name") == "style-name"


# --- build_consistency_prompt ---


class TestBuildConsistencyPrompt:
    def test_returns_image_prompt(self):
        prompt = build_consistency_prompt("a room", "dark moody style")
        assert isinstance(prompt, ImagePrompt)

    def test_combines_scene_and_style(self):
        prompt = build_consistency_prompt("a forest", "watercolor look")
        assert "a forest" in prompt.full_prompt
        assert "watercolor look" in prompt.full_prompt

    def test_aspect_ratio_is_16_9(self):
        prompt = build_consistency_prompt("scene", "style")
        assert prompt.generation_notes.aspect_ratio == "16:9"

    def test_key_requirements_present(self):
        prompt = build_consistency_prompt("scene", "style")
        reqs = prompt.generation_notes.key_requirements
        assert len(reqs) > 0
        assert any("consistent" in r for r in reqs)


# --- run_consistency_check ---


class TestRunConsistencyCheck:
    def _make_mock_provider(self, tiny_png_bytes, name="gemini"):
        provider = MagicMock()
        provider.name = name
        provider.capabilities = MagicMock()

        from pixbridge.providers.base import GenerationResult

        provider.generate.return_value = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider=name,
            model="test-model",
        )
        return provider

    def test_generates_n_images(self, tmp_path, tiny_png_bytes):
        provider = self._make_mock_provider(tiny_png_bytes)
        result = run_consistency_check(
            provider=provider,
            style="test-style",
            style_text="dark moody",
            output_dir=tmp_path / "out",
            count=3,
        )

        assert isinstance(result, ConsistencyResult)
        assert len(result.images) == 3
        assert result.failures == []
        assert result.count == 3
        assert result.style == "test-style"
        assert result.provider == "gemini"
        assert result.duration_s > 0
        assert provider.generate.call_count == 3

    def test_sequential_filenames(self, tmp_path, tiny_png_bytes):
        provider = self._make_mock_provider(tiny_png_bytes)
        result = run_consistency_check(
            provider=provider,
            style="anime-dark",
            style_text="style text",
            output_dir=tmp_path / "out",
            count=3,
        )

        filenames = sorted(p.name for p in result.images)
        assert filenames == [
            "anime-dark_gemini_01.png",
            "anime-dark_gemini_02.png",
            "anime-dark_gemini_03.png",
        ]

    def test_handles_partial_failures(self, tmp_path, tiny_png_bytes):
        provider = self._make_mock_provider(tiny_png_bytes)

        from pixbridge.providers.base import GenerationResult

        ok_result = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider="gemini",
            model="test-model",
        )
        provider.generate.side_effect = [
            ok_result,
            Exception("API error"),
            ok_result,
        ]

        result = run_consistency_check(
            provider=provider,
            style="test",
            style_text="style",
            output_dir=tmp_path / "out",
            count=3,
        )

        assert len(result.images) == 2
        assert len(result.failures) == 1
        assert "API error" in result.failures[0]

    def test_total_failure(self, tmp_path):
        provider = MagicMock()
        provider.name = "gemini"
        provider.capabilities = MagicMock()
        provider.generate.side_effect = Exception("always fails")

        result = run_consistency_check(
            provider=provider,
            style="test",
            style_text="style",
            output_dir=tmp_path / "out",
            count=2,
        )

        assert len(result.images) == 0
        assert len(result.failures) == 2

    def test_creates_output_dir(self, tmp_path, tiny_png_bytes):
        provider = self._make_mock_provider(tiny_png_bytes)
        out = tmp_path / "nested" / "deep" / "out"
        assert not out.exists()

        run_consistency_check(
            provider=provider,
            style="test",
            style_text="style",
            output_dir=out,
            count=1,
        )

        assert out.exists()

    def test_custom_scene(self, tmp_path, tiny_png_bytes):
        provider = self._make_mock_provider(tiny_png_bytes)
        custom = "a spaceship in orbit"

        run_consistency_check(
            provider=provider,
            style="test",
            style_text="style",
            output_dir=tmp_path / "out",
            count=1,
            scene=custom,
        )

        call_args = provider.generate.call_args
        prompt = call_args[1]["prompt"]
        assert custom in prompt.full_prompt

    def test_passes_generation_params(self, tmp_path, tiny_png_bytes):
        provider = self._make_mock_provider(tiny_png_bytes)

        run_consistency_check(
            provider=provider,
            style="test",
            style_text="style",
            output_dir=tmp_path / "out",
            count=1,
            model="custom-model",
            quality="high",
            aspect_ratio="4:3",
        )

        call_kwargs = provider.generate.call_args[1]
        assert call_kwargs["model"] == "custom-model"
        assert call_kwargs["quality"] == "high"
        assert call_kwargs["aspect_ratio"] == "4:3"


# --- consistency_check_command (CLI) ---


class TestConsistencyCheckCommand:
    @patch("pixbridge.cli.get_provider")
    @patch("pixbridge.cli.ImageClient._resolve_style", return_value="dark moody")
    @patch("pixbridge.cli.run_consistency_check")
    def test_success(self, mock_run, mock_resolve, mock_get_provider, tmp_path):
        from pixbridge.cli import consistency_check_command

        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock(
            default_quality=None,
        )
        mock_get_provider.return_value = mock_provider

        mock_run.return_value = ConsistencyResult(
            style="anime-dark",
            provider="gemini",
            count=3,
            images=[tmp_path / "img_01.png", tmp_path / "img_02.png"],
            failures=[],
            duration_s=5.0,
        )

        args = argparse.Namespace(
            style="anime-dark",
            provider="gemini",
            count=3,
            output=str(tmp_path / "out"),
            model="gemini-3-pro-image-preview",
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            scene=None,
            styles_dir=None,
        )
        code = consistency_check_command(args)

        assert code == 0
        mock_run.assert_called_once()

    @patch("pixbridge.cli.get_provider")
    @patch("pixbridge.cli.ImageClient._resolve_style", return_value="style text")
    @patch("pixbridge.cli.run_consistency_check")
    def test_total_failure_returns_1(self, mock_run, mock_resolve, mock_get_provider):
        from pixbridge.cli import consistency_check_command

        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock(
            default_quality=None,
        )
        mock_get_provider.return_value = mock_provider

        mock_run.return_value = ConsistencyResult(
            style="test",
            provider="gemini",
            count=3,
            images=[],
            failures=["fail1", "fail2", "fail3"],
            duration_s=1.0,
        )

        args = argparse.Namespace(
            style="test",
            provider="gemini",
            count=3,
            output=None,
            model="gemini-3-pro-image-preview",
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            scene=None,
            styles_dir=None,
        )
        code = consistency_check_command(args)

        assert code == 1

    @patch("pixbridge.cli.ImageClient._resolve_style", side_effect=ValueError("bad style"))
    def test_bad_style_returns_1(self, mock_resolve, capsys):
        from pixbridge.cli import consistency_check_command

        args = argparse.Namespace(
            style="nonexistent",
            provider="gemini",
            count=3,
            output=None,
            model=None,
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            scene=None,
            styles_dir=None,
        )
        code = consistency_check_command(args)

        assert code == 1

    @patch("pixbridge.cli.consistency_check_command", return_value=0)
    def test_dispatch_from_main(self, mock_cmd):
        from pixbridge.cli import main

        with patch("sys.argv", ["pixbridge", "consistency-check", "anime-dark"]):
            code = main()
        assert code == 0
        mock_cmd.assert_called_once()

    @patch("pixbridge.cli.get_provider")
    @patch("pixbridge.cli.ImageClient._resolve_style", return_value="style")
    @patch("pixbridge.cli.run_consistency_check")
    def test_openai_quality_param(self, mock_run, mock_resolve, mock_get_provider, tmp_path):
        from pixbridge.cli import consistency_check_command

        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock(
            default_quality="low",
        )
        mock_get_provider.return_value = mock_provider

        mock_run.return_value = ConsistencyResult(
            style="test",
            provider="openai",
            count=2,
            images=[tmp_path / "img.png"],
            failures=[],
            duration_s=1.0,
        )

        args = argparse.Namespace(
            style="test",
            provider="openai",
            count=2,
            output=str(tmp_path),
            model="gpt-image-2",
            size="1K",
            aspect_ratio="16:9",
            quality="low",
            scene=None,
            styles_dir=None,
        )
        code = consistency_check_command(args)

        assert code == 0
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["quality"] == "low"

    @patch("pixbridge.cli.get_provider")
    @patch("pixbridge.cli.ImageClient._resolve_style", return_value="style")
    @patch("pixbridge.cli.run_consistency_check")
    def test_default_output_dir(self, mock_run, mock_resolve, mock_get_provider, tmp_path):
        from pixbridge.cli import consistency_check_command

        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock(
            default_quality=None,
        )
        mock_get_provider.return_value = mock_provider

        mock_run.return_value = ConsistencyResult(
            style="anime-dark",
            provider="gemini",
            count=1,
            images=[Path("generated/consistency-check/anime-dark_gemini/img.png")],
            failures=[],
            duration_s=1.0,
        )

        args = argparse.Namespace(
            style="anime-dark",
            provider="gemini",
            count=1,
            output=None,
            model="gemini-3-pro-image-preview",
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            scene=None,
            styles_dir=None,
        )
        code = consistency_check_command(args)

        assert code == 0
        call_kwargs = mock_run.call_args[1]
        assert "consistency-check" in str(call_kwargs["output_dir"])
        assert "anime-dark_gemini" in str(call_kwargs["output_dir"])

    @patch("pixbridge.cli.get_provider")
    @patch("pixbridge.cli.ImageClient._resolve_style", return_value="style text")
    @patch("pixbridge.cli.run_consistency_check")
    def test_file_path_style_normalized(self, mock_run, mock_resolve, mock_get_provider, tmp_path):
        """File paths like 'prompts/style-transfer/anime-dark.md' should produce
        clean filenames using just the stem 'anime-dark'."""
        from pixbridge.cli import consistency_check_command

        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock(
            default_quality=None,
        )
        mock_get_provider.return_value = mock_provider

        mock_run.return_value = ConsistencyResult(
            style="victorian-mystery-anime",
            provider="gemini",
            count=1,
            images=[tmp_path / "img.png"],
            failures=[],
            duration_s=1.0,
        )

        args = argparse.Namespace(
            style="prompts/style-transfer/victorian-mystery-anime.md",
            provider="gemini",
            count=1,
            output=None,
            model="gemini-3-pro-image-preview",
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            scene=None,
            styles_dir=None,
        )
        code = consistency_check_command(args)

        assert code == 0
        call_kwargs = mock_run.call_args[1]
        # style label should be the stem, not the full path
        assert call_kwargs["style"] == "victorian-mystery-anime"
        # output dir should not contain slashes from the path
        output_dir_str = str(call_kwargs["output_dir"])
        assert "victorian-mystery-anime_gemini" in output_dir_str
        assert "prompts/style-transfer" not in output_dir_str
