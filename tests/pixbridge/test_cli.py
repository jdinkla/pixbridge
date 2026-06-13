"""Tests for pixbridge.cli — command routing, exit codes."""

import argparse
from unittest.mock import MagicMock, patch

import pytest
import yaml

from pixbridge.cli import (
    _batch_style_transfer,
    _load_config_from_args,
    check_command,
    generate_command,
    load_prompt_from_yaml,
    main,
    providers_command,
    style_transfer_command,
)
from pixbridge.models import ImagePrompt
from pixbridge.size_resolver import _infer_aspect_ratio, resolve_size_preset

# --- load_prompt_from_yaml ---


class TestLoadPromptFromYaml:
    def test_flat_structure(self, tmp_path):
        data = {
            "full_prompt": "A mountain landscape",
            "generation_notes": {
                "aspect_ratio": "16:9",
                "key_requirements": ["landscape"],
            },
        }
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text(yaml.dump(data))

        prompt = load_prompt_from_yaml(yaml_file)

        assert isinstance(prompt, ImagePrompt)
        assert prompt.full_prompt == "A mountain landscape"

    def test_nested_structure(self, tmp_path):
        data = {
            "image_prompt": {
                "full_prompt": "A cat",
                "generation_notes": {
                    "aspect_ratio": "1:1",
                    "key_requirements": ["cute"],
                },
            }
        }
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text(yaml.dump(data))

        prompt = load_prompt_from_yaml(yaml_file)

        assert prompt.full_prompt == "A cat"

    def test_with_sections(self, tmp_path):
        data = {
            "full_prompt": "A dog",
            "sections": {
                "goal": "g", "subject": "s", "composition": "c",
                "setting": "s", "lighting": "l", "style": "st",
                "fidelity": "f", "consistency": "co",
            },
            "generation_notes": {
                "aspect_ratio": "4:3",
                "key_requirements": [],
            },
        }
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text(yaml.dump(data))

        prompt = load_prompt_from_yaml(yaml_file)

        assert prompt.sections is not None


# --- main() routing ---


class TestMainRouting:
    def test_no_command_returns_0(self):
        with patch("sys.argv", ["pixbridge"]):
            code = main()
        assert code == 0

    @patch("pixbridge.cli.providers_command", return_value=0)
    def test_providers_dispatched(self, mock_cmd):
        with patch("sys.argv", ["pixbridge", "providers"]):
            code = main()
        assert code == 0
        mock_cmd.assert_called_once()

    @patch("pixbridge.cli.generate_command", return_value=0)
    def test_generate_dispatched(self, mock_cmd):
        with patch("sys.argv", ["pixbridge", "generate", "prompt.yaml"]):
            code = main()
        assert code == 0
        mock_cmd.assert_called_once()

    @patch("pixbridge.cli.style_transfer_command", return_value=0)
    def test_style_transfer_dispatched(self, mock_cmd):
        with patch("sys.argv", ["pixbridge", "style-transfer", "--list-styles"]):
            code = main()
        assert code == 0
        mock_cmd.assert_called_once()


# --- generate_command ---


class TestGenerateCommand:
    @patch("pixbridge.cli.ImageClient")
    def test_generates_image(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.provider.capabilities = MagicMock(
            default_model="gemini-3-pro-image-preview",
            default_quality="medium",
        )
        mock_client.generate_image.return_value = tmp_path / "out" / "image.png"
        mock_cls.return_value = mock_client

        prompt_file = tmp_path / "prompt.yaml"
        prompt_file.write_text(yaml.dump({
            "full_prompt": "A cat",
            "generation_notes": {
                "aspect_ratio": "16:9",
                "key_requirements": ["cute"],
            },
        }))

        args = argparse.Namespace(
            prompt_file=str(prompt_file),
            output=str(tmp_path / "out"),
            provider="gemini",
            model=None,
            size="1K",
            aspect_ratio="16:9",
            quality=None,
        )
        code = generate_command(args)

        assert code == 0
        mock_client.generate_image.assert_called_once()

    def test_missing_file_returns_1(self, tmp_path, capsys):
        args = argparse.Namespace(
            prompt_file=str(tmp_path / "nope.yaml"),
            output=None,
            provider="gemini",
            model=None,
            size="1K",
            aspect_ratio="16:9",
            quality=None,
        )
        code = generate_command(args)

        assert code == 1
        assert "not found" in capsys.readouterr().err

    @patch("pixbridge.cli.ImageClient")
    def test_value_error_returns_1(self, mock_cls, tmp_path, capsys):
        mock_cls.side_effect = ValueError("bad param")

        prompt_file = tmp_path / "prompt.yaml"
        prompt_file.write_text(yaml.dump({
            "full_prompt": "A cat",
            "generation_notes": {
                "aspect_ratio": "16:9",
                "key_requirements": [],
            },
        }))

        args = argparse.Namespace(
            prompt_file=str(prompt_file),
            output=None,
            provider="gemini",
            model=None,
            size="1K",
            aspect_ratio="16:9",
            quality=None,
        )
        code = generate_command(args)

        assert code == 1

    @patch("pixbridge.cli.ImageClient")
    def test_openai_quality_param(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.provider.capabilities = MagicMock(
            default_model="gpt-image-2",
            default_quality="low",
        )
        mock_client.generate_image.return_value = tmp_path / "image.png"
        mock_cls.return_value = mock_client

        prompt_file = tmp_path / "prompt.yaml"
        prompt_file.write_text(yaml.dump({
            "full_prompt": "A cat",
            "generation_notes": {
                "aspect_ratio": "1:1",
                "key_requirements": [],
            },
        }))

        args = argparse.Namespace(
            prompt_file=str(prompt_file),
            output=str(tmp_path),
            provider="openai",
            model=None,
            size="1K",
            aspect_ratio="1:1",
            quality="high",
        )
        code = generate_command(args)

        assert code == 0
        call_kwargs = mock_client.generate_image.call_args
        # quality should be passed for openai
        assert call_kwargs[1]["quality"] == "high"


# --- providers_command ---


class TestProvidersCommand:
    @patch("pixbridge.cli.get_provider")
    def test_lists_providers(self, mock_get, capsys):
        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock(
            default_model="m1",
            sizes=["1K"],
            aspect_ratios=["16:9"],
            quality_levels=None,
        )
        mock_get.return_value = mock_provider

        args = argparse.Namespace(command="providers")
        code = providers_command(args)

        assert code == 0
        out = capsys.readouterr().out
        assert "m1" in out

    @patch("pixbridge.cli.get_provider", side_effect=Exception("error"))
    def test_handles_provider_error(self, mock_get, capsys):
        args = argparse.Namespace(command="providers")
        code = providers_command(args)

        assert code == 0
        out = capsys.readouterr().out
        assert "error" in out


# --- style_transfer_command ---


class TestStyleTransferCommand:
    def test_list_styles(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        preset_dir = tmp_path / "prompts" / "style-transfer" / "anime"
        preset_dir.mkdir(parents=True)
        (preset_dir / "anime-dark.md").write_text("...")

        args = argparse.Namespace(
            list_styles=True,
            input=None,
            style=None,
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 0
        assert "anime/anime-dark" in capsys.readouterr().out

    def test_no_presets(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(
            list_styles=True,
            input=None,
            style=None,
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 0
        assert "No style presets" in capsys.readouterr().out

    def test_missing_input_returns_1(self, capsys):
        args = argparse.Namespace(
            list_styles=False,
            input=None,
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 1
        assert "input" in capsys.readouterr().err.lower()

    def test_missing_style_returns_1(self, capsys, tmp_path):
        input_img = tmp_path / "input.png"
        input_img.touch()

        args = argparse.Namespace(
            list_styles=False,
            input=str(input_img),
            style=None,
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 1
        assert "style" in capsys.readouterr().err.lower()

    def test_nonexistent_input_returns_1(self, capsys, tmp_path):
        args = argparse.Namespace(
            list_styles=False,
            input=str(tmp_path / "nope.png"),
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 1
        assert "not found" in capsys.readouterr().err.lower()

    @patch("pixbridge.cli.ImageClient")
    def test_single_file(self, mock_cls, tmp_path, capsys):
        from PIL import Image as PILImage

        mock_client = MagicMock()
        mock_client.style_transfer_image.return_value = tmp_path / "output.png"
        mock_cls.return_value = mock_client

        input_img = tmp_path / "input.png"
        PILImage.new("RGB", (10, 10)).save(input_img)

        args = argparse.Namespace(
            list_styles=False,
            input=str(input_img),
            style="anime-dark",
            output=str(tmp_path / "output.png"),
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 0
        mock_client.style_transfer_image.assert_called_once()

    @patch("pixbridge.cli.ImageClient")
    def test_error_returns_1(self, mock_cls, tmp_path, capsys):
        mock_client = MagicMock()
        mock_client.style_transfer_image.side_effect = ValueError("bad")
        mock_cls.return_value = mock_client

        input_img = tmp_path / "input.png"
        input_img.touch()

        args = argparse.Namespace(
            list_styles=False,
            input=str(input_img),
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        code = style_transfer_command(args)

        assert code == 1

    @patch("pixbridge.cli.ImageClient")
    def test_batch_requires_directory(self, mock_cls, tmp_path, capsys):
        mock_cls.return_value = MagicMock()

        input_file = tmp_path / "input.png"
        input_file.touch()

        args = argparse.Namespace(
            list_styles=False,
            input=str(input_file),
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=True,
        )
        code = style_transfer_command(args)

        assert code == 1
        assert "directory" in capsys.readouterr().err.lower()

    def test_not_a_file_returns_1(self, tmp_path, capsys):
        # input is a directory but not in batch mode
        args = argparse.Namespace(
            list_styles=False,
            input=str(tmp_path),
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
            batch=False,
        )
        # Need to patch ImageClient to avoid API key issues
        with patch("pixbridge.cli.ImageClient"):
            code = style_transfer_command(args)

        assert code == 1
        assert "not a file" in capsys.readouterr().err.lower()


# --- _batch_style_transfer ---


class TestBatchStyleTransfer:
    def test_processes_images(self, tmp_path):
        from PIL import Image as PILImage

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        PILImage.new("RGB", (10, 10)).save(input_dir / "a.png")
        PILImage.new("RGB", (10, 10)).save(input_dir / "b.jpg")
        (input_dir / "readme.txt").write_text("not an image")

        mock_client = MagicMock()
        mock_client.style_transfer_image.return_value = tmp_path / "out.png"

        args = argparse.Namespace(
            style="anime-dark",
            output=str(tmp_path / "output"),
            model=None,
            size=None,
            aspect_ratio=None,
        )
        code = _batch_style_transfer(mock_client, input_dir, args)

        assert code == 0
        assert mock_client.style_transfer_image.call_count == 2

    def test_no_images_found(self, tmp_path, capsys):
        input_dir = tmp_path / "empty"
        input_dir.mkdir()

        mock_client = MagicMock()
        args = argparse.Namespace(
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
        )
        code = _batch_style_transfer(mock_client, input_dir, args)

        assert code == 0
        assert "No images found" in capsys.readouterr().out

    def test_handles_individual_failures(self, tmp_path, capsys):
        from PIL import Image as PILImage

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        PILImage.new("RGB", (10, 10)).save(input_dir / "a.png")
        PILImage.new("RGB", (10, 10)).save(input_dir / "b.png")

        mock_client = MagicMock()
        mock_client.style_transfer_image.side_effect = [
            tmp_path / "a.png",
            Exception("API error"),
        ]

        args = argparse.Namespace(
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
        )
        code = _batch_style_transfer(mock_client, input_dir, args)

        assert code == 0
        out = capsys.readouterr().out
        assert "1/2" in out

    def test_overwrites_in_place_without_output(self, tmp_path):
        from PIL import Image as PILImage

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        PILImage.new("RGB", (10, 10)).save(input_dir / "a.png")

        mock_client = MagicMock()
        mock_client.style_transfer_image.return_value = input_dir / "a.png"

        args = argparse.Namespace(
            style="anime-dark",
            output=None,
            model=None,
            size=None,
            aspect_ratio=None,
        )
        _batch_style_transfer(mock_client, input_dir, args)

        call_kwargs = mock_client.style_transfer_image.call_args[1]
        assert call_kwargs["output_path"] is None


# --- resolve_size_preset ---


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
        ("1152x2048", "openai", "1152x2048", "9:16"),
        ("2048x1152", "openai", "2048x1152", "16:9"),
        ("1920x1080", "xai", None, "16:9"),
        ("1920x1080", "vertex", "2K", "16:9"),
        ("800x600", "gemini", "1K", "4:3"),
    ])
    def test_wxh_dimensions(self, wxh, provider, expected_size, expected_aspect):
        size, aspect = resolve_size_preset(wxh, provider)
        assert size == expected_size
        assert aspect == expected_aspect


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


# --- _load_config_from_args ---


class TestLoadConfigFromArgs:
    def test_returns_none_without_config_or_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # no model_config.yaml here
        args = argparse.Namespace(config=None)
        assert _load_config_from_args(args) is None

    def test_loads_explicit_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "providers": {"gemini": {"default_model": "my-model"}},
        }))
        args = argparse.Namespace(config=str(config_file))
        result = _load_config_from_args(args)
        assert result["providers"]["gemini"]["default_model"] == "my-model"

    def test_missing_explicit_config_exits(self, tmp_path):
        args = argparse.Namespace(config=str(tmp_path / "nope.yaml"))
        with pytest.raises(SystemExit):
            _load_config_from_args(args)

    def test_invalid_explicit_config_exits(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"bad": "data"}))
        args = argparse.Namespace(config=str(config_file))
        with pytest.raises(SystemExit):
            _load_config_from_args(args)

    def test_auto_discovers_default_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        default_cfg = tmp_path / "model_config.yaml"
        default_cfg.write_text(yaml.dump({
            "providers": {"openai": {"default_model": "auto-model"}},
        }))
        args = argparse.Namespace(config=None)
        result = _load_config_from_args(args)
        assert result["providers"]["openai"]["default_model"] == "auto-model"

    def test_explicit_config_overrides_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # default in cwd
        (tmp_path / "model_config.yaml").write_text(yaml.dump({
            "providers": {"gemini": {"default_model": "from-default"}},
        }))
        # explicit elsewhere
        explicit = tmp_path / "custom.yaml"
        explicit.write_text(yaml.dump({
            "providers": {"gemini": {"default_model": "from-explicit"}},
        }))
        args = argparse.Namespace(config=str(explicit))
        result = _load_config_from_args(args)
        assert result["providers"]["gemini"]["default_model"] == "from-explicit"


# --- config model resolution in generate_command ---


class TestGenerateConfigModel:
    def _make_prompt_file(self, tmp_path):
        prompt_file = tmp_path / "prompt.yaml"
        prompt_file.write_text(yaml.dump({
            "full_prompt": "A cat",
            "generation_notes": {
                "aspect_ratio": "16:9",
                "key_requirements": ["cute"],
            },
        }))
        return prompt_file

    @patch("pixbridge.cli.ImageClient")
    def test_config_model_used_when_no_flag(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.provider.capabilities = MagicMock(
            default_model="hardcoded-default",
            default_quality="medium",
        )
        mock_client.generate_image.return_value = tmp_path / "image.png"
        mock_cls.return_value = mock_client

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "providers": {"gemini": {"default_model": "config-model"}},
        }))

        args = argparse.Namespace(
            prompt_file=str(self._make_prompt_file(tmp_path)),
            output=str(tmp_path),
            provider="gemini",
            model=None,
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            config=str(config_file),
        )
        code = generate_command(args)

        assert code == 0
        call_kwargs = mock_client.generate_image.call_args[1]
        assert call_kwargs["model"] == "config-model"

    @patch("pixbridge.cli.ImageClient")
    def test_cli_model_overrides_config(self, mock_cls, tmp_path):
        mock_client = MagicMock()
        mock_client.provider.capabilities = MagicMock(
            default_model="hardcoded-default",
            default_quality="medium",
        )
        mock_client.generate_image.return_value = tmp_path / "image.png"
        mock_cls.return_value = mock_client

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "providers": {"gemini": {"default_model": "config-model"}},
        }))

        args = argparse.Namespace(
            prompt_file=str(self._make_prompt_file(tmp_path)),
            output=str(tmp_path),
            provider="gemini",
            model="cli-model",
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            config=str(config_file),
        )
        code = generate_command(args)

        assert code == 0
        call_kwargs = mock_client.generate_image.call_args[1]
        assert call_kwargs["model"] == "cli-model"

    @patch("pixbridge.cli.ImageClient")
    def test_provider_default_without_config(self, mock_cls, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # no model_config.yaml here
        mock_client = MagicMock()
        mock_client.provider.capabilities = MagicMock(
            default_model="hardcoded-default",
            default_quality="medium",
        )
        mock_client.generate_image.return_value = tmp_path / "image.png"
        mock_cls.return_value = mock_client

        args = argparse.Namespace(
            prompt_file=str(self._make_prompt_file(tmp_path)),
            output=str(tmp_path),
            provider="gemini",
            model=None,
            size="1K",
            aspect_ratio="16:9",
            quality=None,
            config=None,
        )
        code = generate_command(args)

        assert code == 0
        call_kwargs = mock_client.generate_image.call_args[1]
        assert call_kwargs["model"] == "hardcoded-default"


# --- config flag via main() argument parsing ---


class TestConfigArgParsing:
    @patch("pixbridge.cli.providers_command", return_value=0)
    def test_config_flag_parsed(self, mock_cmd, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "providers": {"gemini": {"default_model": "my-model"}},
        }))
        with patch("sys.argv", ["pixbridge", "--config", str(config_file), "providers"]):
            code = main()
        assert code == 0
        # Verify config was passed through
        call_args = mock_cmd.call_args[0][0]
        assert call_args.config == str(config_file)


# --- check_command ---


class TestCheckCommand:
    @staticmethod
    def _args(path, threshold=0.01):
        return argparse.Namespace(path=str(path), threshold=threshold)

    @staticmethod
    def _png(path, mode="RGB", color="red", size=(10, 10)):
        from PIL import Image as PILImage

        PILImage.new(mode, size, color).save(path)
        return path

    def test_missing_path_returns_1(self, tmp_path):
        code = check_command(self._args(tmp_path / "nope.png"))
        assert code == 1

    def test_single_ok_file_returns_0(self, tmp_path):
        path = self._png(tmp_path / "ok.png")
        assert check_command(self._args(path)) == 0

    def test_single_failing_file_returns_1(self, tmp_path):
        # Fully transparent → flagged → exit 1.
        path = self._png(tmp_path / "bad.png", mode="RGBA", color=(0, 0, 0, 0))
        assert check_command(self._args(path)) == 1

    def test_directory_all_ok_returns_0(self, tmp_path):
        self._png(tmp_path / "a.png")
        self._png(tmp_path / "b.png", color="blue")
        assert check_command(self._args(tmp_path)) == 0

    def test_directory_with_failure_returns_1(self, tmp_path):
        self._png(tmp_path / "a.png")
        self._png(tmp_path / "bad.png", mode="RGBA", color=(0, 0, 0, 0))
        assert check_command(self._args(tmp_path)) == 1

    def test_empty_directory_returns_0(self, tmp_path):
        assert check_command(self._args(tmp_path)) == 0

    def test_directory_summary_printed(self, tmp_path, capsys):
        self._png(tmp_path / "a.png")
        self._png(tmp_path / "bad.png", mode="RGBA", color=(0, 0, 0, 0))
        check_command(self._args(tmp_path))
        out = capsys.readouterr().out
        assert "2 images checked, 1 failed" in out
