"""Live end-to-end tests: each provider generates an image, `claude` verifies it.

These tests are opt-in via the `live` marker. They are skipped by default
(see `addopts` in pyproject.toml) and can be run with `just test-live` or
`pytest -m live`. Tests skip automatically when required API keys are missing.

pixbridge has no default model, so each provider's model comes from the
environment as well: ``PIXBRIDGE_LIVE_<PROVIDER>_MODEL`` (e.g.
``PIXBRIDGE_LIVE_OPENAI_MODEL=gpt-image-2``). `just test-live` sets these from
the values at the top of the justfile; under a bare `pytest -m live` a provider
whose model variable is unset is skipped, same as a missing API key.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from pixbridge.client import ImageClient
from pixbridge.models import GenerationNotes, ImagePrompt

from .vision_verifier import VerifierUnavailable, verify_image

# Persistent output dir so generated images stay around for inspection after the
# run. Each provider gets its own subdir, wiped at the start of every run so the
# only files left are from the most recent invocation.
LIVE_OUTPUT_ROOT = Path("/tmp/pixbridge-live")

SHARED_PROMPT = ImagePrompt(
    full_prompt=(
        "A single red apple sitting alone in the exact center of a plain white "
        "table, photographed from slightly above, soft even lighting, no text "
        "or watermark, landscape orientation."
    ),
    generation_notes=GenerationNotes(
        aspect_ratio="16:9",
        key_requirements=[
            "single red apple as the only subject",
            "plain white table / background",
            "no text or watermark",
            "landscape orientation",
        ],
    ),
)



def _live_model(provider_name: str) -> str:
    """Return the model to test ``provider_name`` with, or skip the test."""
    env_var = f"PIXBRIDGE_LIVE_{provider_name.upper()}_MODEL"
    model = os.environ.get(env_var)
    if not model:
        pytest.skip(f"{env_var} not set (pixbridge has no default model)")
    return model


def _generate_or_fail(client: ImageClient, prompt: ImagePrompt, **kwargs: Any) -> Path:
    """Generate an image, turning a provider/SDK error into a one-line failure.

    A live failure is almost always the provider saying no (billing, quota, an
    unknown model, an outage). The SDK's own message says which; the traceback
    through the SDK internals adds nothing, so it is suppressed.
    """
    try:
        return client.generate_image(prompt, **kwargs)
    except Exception as e:
        # SDK errors carry a short human-readable `message`; str(e) appends the
        # raw response body, which is noise here.
        detail = getattr(e, "message", None) or str(e)
        status = getattr(e, "code", None) or getattr(e, "status_code", None)
        error = f"{type(e).__name__}" + (f" {status}" if status else "") + f": {detail}"
    # Fail outside the `except` block so pytest does not also print the chained
    # original exception.
    pytest.fail(
        f"{client.provider_name} (model={kwargs.get('model')}) API call failed: {error}",
        pytrace=False,
    )


PROPERTIES: dict[str, str] = {
    "subject_is_apple": "The main subject is a single apple (not multiple, not another fruit).",
    "apple_is_red": "The apple is predominantly red.",
    "background_is_plain_white_surface": (
        "The apple rests on a plain, light/white surface with no busy background."
    ),
    "no_text_or_watermark": "There is no visible text, caption, logo, or watermark.",
    "landscape_orientation": "The image is wider than it is tall (landscape orientation).",
}


@pytest.mark.live
@pytest.mark.parametrize(
    ("provider_name", "env_key"),
    [
        ("gemini", "GOOGLE_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("xai", "XAI_API_KEY"),
    ],
)
def test_provider_generates_verifiable_image(
    provider_name: str,
    env_key: str,
) -> None:
    if not os.environ.get(env_key) and not (
        provider_name == "gemini" and os.environ.get("GEMINI_API_KEY")
    ):
        pytest.skip(f"{env_key} not set")
    model = _live_model(provider_name)

    output_dir = LIVE_OUTPUT_ROOT / provider_name
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    client = ImageClient(provider=provider_name)
    # generate_image() does not currently read prompt.generation_notes.aspect_ratio,
    # so pass it explicitly — otherwise OpenAI falls back to its 1:1 default.
    image_path = _generate_or_fail(
        client, SHARED_PROMPT, output_dir=output_dir, model=model, aspect_ratio="16:9"
    )

    assert image_path.exists(), f"{provider_name} did not produce an image file"
    assert image_path.stat().st_size > 0, f"{provider_name} produced an empty file"

    try:
        results = verify_image(image_path, PROPERTIES)
    except VerifierUnavailable as e:
        pytest.skip(f"vision verifier unavailable: {e}")

    missing = PROPERTIES.keys() - results.keys()
    assert not missing, f"claude did not return verdicts for: {sorted(missing)}"

    failures = {pid: r for pid, r in results.items() if not r["passed"]}
    assert not failures, (
        f"{provider_name} image failed vision verification:\n"
        + "\n".join(f"  - {pid}: {r['reason']}" for pid, r in failures.items())
    )


@pytest.mark.live
def test_openai_true_9_16_size() -> None:
    """OpenAI generates a true-9:16 image when --size 1152x2048 is passed.

    Regression guard for the 9:16 → 3:4 silent-rewrite bug fixed in TASK-42.1.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    model = _live_model("openai")

    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    output_dir = LIVE_OUTPUT_ROOT / "openai-9x16"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    vertical_prompt = ImagePrompt(
        full_prompt=(
            "A tall lighthouse on a rocky coast at dawn, full vertical "
            "composition from waves at the base to the lamp at the top, "
            "vertical orientation."
        ),
        generation_notes=GenerationNotes(
            aspect_ratio="9:16",
            key_requirements=["vertical orientation", "single lighthouse"],
        ),
    )

    client = ImageClient(provider="openai")
    image_path = _generate_or_fail(
        client,
        vertical_prompt,
        output_dir=output_dir,
        model=model,
        size="1152x2048",
        aspect_ratio="9:16",
    )

    assert image_path.exists(), "OpenAI did not produce an image file"
    with Image.open(image_path) as img:
        assert img.size == (1152, 2048), (
            f"Expected 1152x2048, got {img.size}. The OpenAI size pass-through "
            "or rule-based validation may be wired incorrectly."
        )
