"""Image integrity checks: transparency, truncation, and structural corruption."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class CheckResult:
    """Result of an integrity check on a single image."""

    path: Path
    ok: bool
    issues: list[str]

    def summary(self) -> str:
        if self.ok:
            return f"  OK  {self.path}"
        tag = ", ".join(self.issues)
        return f"  FAIL {self.path}  [{tag}]"


def check_image(
    path: Path,
    *,
    transparency_threshold: float = 0.01,
    band_height: int = 50,
    band_std_threshold: float = 5.0,
) -> CheckResult:
    """Run integrity checks on a single image file.

    Checks performed:
    1. File can be opened and fully decoded by Pillow.
    2. PNG files have a valid IEND chunk.
    3. Transparency: flags images where more than *transparency_threshold*
       fraction of pixels are non-opaque (RGBA mode only).
    4. Fill-band detection: flags images where the bottom *band_height* rows
       have a pixel standard deviation below *band_std_threshold* (indicates
       truncated generation filling with a uniform color).
    """
    issues: list[str] = []

    # 1. Can Pillow open and decode the image?
    try:
        img = Image.open(path)
        img.load()  # force full decompression
    except Exception as exc:
        return CheckResult(path=path, ok=False, issues=[f"corrupt: {exc}"])

    # 2. PNG IEND check
    if path.suffix.lower() == ".png":
        with open(path, "rb") as f:
            f.seek(-12, 2)
            if b"IEND" not in f.read():
                issues.append("missing IEND chunk")

    # 3. Transparency check
    if img.mode == "RGBA":
        alpha = img.getchannel("A")
        # get_flattened_data() exists at runtime (Pillow 11+) but is missing from
        # the bundled type stubs; it replaces the deprecated getdata().
        data = alpha.get_flattened_data()  # type: ignore[attr-defined]
        total = len(data)
        non_opaque = sum(1 for p in data if p < 255)
        ratio = non_opaque / total
        if ratio > transparency_threshold:
            pct = ratio * 100
            issues.append(f"transparent {pct:.1f}%")

    # 4. Fill-band detection (bottom rows uniform color)
    width, height = img.size
    if height > band_height:
        bottom = img.crop((0, height - band_height, width, height)).convert("RGB")
        pixels = bottom.get_flattened_data()  # type: ignore[attr-defined]
        if pixels:
            # Compute per-channel std dev
            r_vals = [p[0] for p in pixels]
            g_vals = [p[1] for p in pixels]
            b_vals = [p[2] for p in pixels]
            for _ch_name, vals in [("R", r_vals), ("G", g_vals), ("B", b_vals)]:
                mean = sum(vals) / len(vals)
                variance = sum((v - mean) ** 2 for v in vals) / len(vals)
                std = variance**0.5
                if std > band_std_threshold:
                    break
            else:
                # All channels below threshold
                issues.append("uniform bottom band")

    return CheckResult(path=path, ok=len(issues) == 0, issues=issues)


def check_directory(
    directory: Path,
    *,
    transparency_threshold: float = 0.01,
) -> list[CheckResult]:
    """Check all images in a directory.

    Returns a list of CheckResult, one per image file found.
    """
    images = sorted(
        p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    )
    return [
        check_image(p, transparency_threshold=transparency_threshold) for p in images
    ]
