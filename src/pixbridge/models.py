"""Pydantic models for Task 7 image prompt format."""

from pydantic import BaseModel


class GenerationNotes(BaseModel):
    """Generation configuration notes."""

    aspect_ratio: str  # "16:9", "4:3", "1:1"
    negative_prompts: list[str] | None = None
    key_requirements: list[str]


class ImagePromptSections(BaseModel):
    """Individual sections of the Nano-Banana Pro prompt."""

    goal: str
    subject: str
    composition: str
    spatial_relationships: str | None = None
    setting: str
    lighting: str
    text_elements: str | None = None
    style: str
    fidelity: str
    consistency: str


class ImagePrompt(BaseModel):
    """Complete image prompt structure from Task 7."""

    full_prompt: str
    sections: ImagePromptSections | None = None
    generation_notes: GenerationNotes
