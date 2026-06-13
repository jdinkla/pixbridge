"""Tests for pixbridge.models — Pydantic model validation."""

import pytest
from pydantic import ValidationError

from pixbridge.models import GenerationNotes, ImagePrompt, ImagePromptSections


class TestGenerationNotes:
    def test_required_fields(self):
        notes = GenerationNotes(
            aspect_ratio="16:9",
            key_requirements=["photorealistic"],
        )
        assert notes.aspect_ratio == "16:9"
        assert notes.key_requirements == ["photorealistic"]

    def test_negative_prompts_optional(self):
        notes = GenerationNotes(
            aspect_ratio="1:1",
            key_requirements=["test"],
        )
        assert notes.negative_prompts is None

    def test_negative_prompts_set(self):
        notes = GenerationNotes(
            aspect_ratio="4:3",
            negative_prompts=["cartoon", "blurry"],
            key_requirements=["sharp"],
        )
        assert notes.negative_prompts == ["cartoon", "blurry"]

    def test_missing_aspect_ratio_raises(self):
        with pytest.raises(ValidationError):
            GenerationNotes(key_requirements=["test"])

    def test_missing_key_requirements_raises(self):
        with pytest.raises(ValidationError):
            GenerationNotes(aspect_ratio="16:9")

    def test_empty_key_requirements(self):
        notes = GenerationNotes(aspect_ratio="16:9", key_requirements=[])
        assert notes.key_requirements == []


class TestImagePromptSections:
    def test_all_required_fields(self):
        sections = ImagePromptSections(
            goal="goal",
            subject="subject",
            composition="composition",
            setting="setting",
            lighting="lighting",
            style="style",
            fidelity="fidelity",
            consistency="consistency",
        )
        assert sections.goal == "goal"
        assert sections.text_elements is None

    def test_text_elements_optional(self):
        sections = ImagePromptSections(
            goal="g", subject="s", composition="c",
            setting="s", lighting="l", style="st",
            fidelity="f", consistency="co",
        )
        assert sections.text_elements is None

    def test_text_elements_set(self):
        sections = ImagePromptSections(
            goal="g", subject="s", composition="c",
            setting="s", lighting="l",
            text_elements="Title: Hello",
            style="st", fidelity="f", consistency="co",
        )
        assert sections.text_elements == "Title: Hello"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            ImagePromptSections(
                goal="g", subject="s",
                # missing composition, setting, lighting, style, fidelity, consistency
            )


class TestImagePrompt:
    def test_minimal(self):
        prompt = ImagePrompt(
            full_prompt="A cat",
            generation_notes=GenerationNotes(
                aspect_ratio="1:1",
                key_requirements=["cute"],
            ),
        )
        assert prompt.full_prompt == "A cat"
        assert prompt.sections is None

    def test_with_sections(self, sample_prompt_with_sections):
        assert sample_prompt_with_sections.sections is not None
        assert sample_prompt_with_sections.sections.goal.startswith("Create")

    def test_missing_full_prompt_raises(self):
        with pytest.raises(ValidationError):
            ImagePrompt(
                generation_notes=GenerationNotes(
                    aspect_ratio="1:1",
                    key_requirements=[],
                ),
            )

    def test_missing_generation_notes_raises(self):
        with pytest.raises(ValidationError):
            ImagePrompt(full_prompt="A cat")

    def test_model_validate_dict(self):
        data = {
            "full_prompt": "A dog",
            "generation_notes": {
                "aspect_ratio": "4:3",
                "key_requirements": ["dog"],
            },
        }
        prompt = ImagePrompt.model_validate(data)
        assert prompt.full_prompt == "A dog"

    def test_model_validate_with_sections(self):
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
        prompt = ImagePrompt.model_validate(data)
        assert prompt.sections is not None
