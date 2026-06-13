"""Verify generated images via the local `claude` CLI.

Runs `claude -p --output-format json --json-schema ...` as a subprocess so the
call is billed against the user's Claude Code subscription instead of per-token
API credits. The image is downscaled before being sent to the verifier to cut
vision-token cost independent of what the generator produced.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import TypedDict

from PIL import Image

VISION_MODEL = "claude-sonnet-4-6"
MAX_EDGE_PX = 512


class PropertyResult(TypedDict):
    passed: bool
    reason: str


class VerifierUnavailable(RuntimeError):
    """The `claude` CLI is missing, unauthenticated, or otherwise not runnable."""


def verify_image(
    image_path: Path,
    properties: dict[str, str],
    *,
    timeout_s: float = 180.0,
) -> dict[str, PropertyResult]:
    """Ask Claude (via the `claude` CLI) whether an image satisfies named properties.

    Args:
        image_path: Path to the image on disk. Will be downscaled before sending.
        properties: Mapping of property id -> plain-English description.
        timeout_s: How long to wait for the subprocess before aborting.

    Returns:
        Mapping of property id -> {passed, reason}.

    Raises:
        VerifierUnavailable: `claude` CLI not found, or exited non-zero.
        ValueError: CLI responded but the envelope is malformed.
    """
    verify_target = _downscale(image_path)
    schema = _build_schema(properties)
    prompt = _build_prompt(verify_target, properties)

    env = os.environ.copy()
    # Force OAuth/subscription auth — if ANTHROPIC_API_KEY is set, claude would
    # bill per-token instead, which is exactly the path we're avoiding.
    env.pop("ANTHROPIC_API_KEY", None)

    try:
        # Prompt goes via stdin — --add-dir is variadic and would swallow a
        # positional prompt argument that follows it.
        completed = subprocess.run(
            [
                "claude",
                "-p",
                "--model",
                VISION_MODEL,
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(schema),
                "--add-dir",
                str(verify_target.parent),
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
    except FileNotFoundError as e:
        raise VerifierUnavailable("`claude` CLI not found on PATH") from e

    if completed.returncode != 0:
        raise VerifierUnavailable(
            f"claude -p exited {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )

    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f"claude -p output was not JSON: {completed.stdout!r}") from e

    if envelope.get("is_error"):
        raise VerifierUnavailable(
            f"claude -p returned error: {envelope.get('result') or envelope}"
        )

    structured = envelope.get("structured_output")
    if not isinstance(structured, dict):
        raise ValueError(
            f"claude -p envelope missing 'structured_output' object: {envelope!r}"
        )

    results: dict[str, PropertyResult] = {}
    for pid, verdict in structured.items():
        if (
            not isinstance(verdict, dict)
            or "passed" not in verdict
            or "reason" not in verdict
        ):
            raise ValueError(f"Malformed verdict for {pid!r}: {verdict!r}")
        results[pid] = PropertyResult(
            passed=bool(verdict["passed"]),
            reason=str(verdict["reason"]),
        )
    return results


def _downscale(src: Path) -> Path:
    """Resize src to at most MAX_EDGE_PX on its longest edge; returns src if already small."""
    with Image.open(src) as im:
        im.load()
        w, h = im.size
        longest = max(w, h)
        if longest <= MAX_EDGE_PX:
            return src
        scale = MAX_EDGE_PX / longest
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        resized = im.resize(new_size, Image.LANCZOS)
        fmt = (im.format or "PNG").upper()
        if fmt == "JPEG":
            resized = resized.convert("RGB")
        out = src.with_name(f"{src.stem}.verify{'.jpg' if fmt == 'JPEG' else '.png'}")
        resized.save(out, format=fmt)
    return out


def _build_schema(properties: dict[str, str]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties.keys()),
        "properties": {
            pid: {
                "type": "object",
                "additionalProperties": False,
                "required": ["passed", "reason"],
                "properties": {
                    "passed": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            }
            for pid in properties
        },
    }


def _build_prompt(image_path: Path, properties: dict[str, str]) -> str:
    checklist = "\n".join(f"- {pid}: {desc}" for pid, desc in properties.items())
    return (
        f"Read the image at {image_path} using the Read tool, then verify the "
        "properties below. For each property decide whether the image satisfies "
        "it and give a one-sentence reason. Respond only as JSON matching the "
        "provided schema.\n\nProperties:\n" + checklist
    )
