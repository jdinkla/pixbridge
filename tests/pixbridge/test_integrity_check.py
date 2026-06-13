"""Tests for pixbridge.integrity_check — corruption, transparency, fill-band logic."""

from pathlib import Path

from PIL import Image

from pixbridge.integrity_check import (
    CheckResult,
    check_directory,
    check_image,
)


def _save(img: Image.Image, path: Path, **kwargs) -> Path:
    img.save(path, **kwargs)
    return path


# --- check_image: corruption ---


class TestCorruption:
    def test_valid_png_passes(self, tmp_path):
        path = _save(Image.new("RGB", (10, 10), "red"), tmp_path / "ok.png")
        result = check_image(path)
        assert result.ok
        assert result.issues == []

    def test_garbage_file_is_corrupt(self, tmp_path):
        path = tmp_path / "broken.png"
        path.write_bytes(b"not an image at all")
        result = check_image(path)
        assert not result.ok
        assert result.issues[0].startswith("corrupt:")

    def test_truncated_data_is_corrupt(self, tmp_path):
        good = _save(Image.new("RGB", (64, 64), "blue"), tmp_path / "src.png")
        data = good.read_bytes()
        path = tmp_path / "trunc.png"
        # Keep just enough to be recognized as PNG but fail full decode.
        path.write_bytes(data[: len(data) // 2])
        result = check_image(path)
        assert not result.ok
        assert result.issues[0].startswith("corrupt:")


# --- check_image: PNG IEND chunk ---


class TestIENDChunk:
    def test_intact_png_has_iend(self, tmp_path):
        path = _save(Image.new("RGB", (10, 10), "green"), tmp_path / "ok.png")
        assert "missing IEND chunk" not in check_image(path).issues

    def test_trailing_bytes_hide_iend(self, tmp_path):
        # Bytes appended after IEND: Pillow still decodes, but the last 12 bytes
        # no longer contain the IEND marker.
        path = _save(Image.new("RGB", (10, 10), "green"), tmp_path / "trail.png")
        path.write_bytes(path.read_bytes() + b"\x00" * 32)
        result = check_image(path)
        assert "missing IEND chunk" in result.issues

    def test_iend_check_skipped_for_non_png(self, tmp_path):
        path = _save(Image.new("RGB", (10, 10), "green"), tmp_path / "ok.jpg")
        # JPEG path never inspects IEND regardless of content.
        assert "missing IEND chunk" not in check_image(path).issues


# --- check_image: transparency ---


class TestTransparency:
    def test_fully_transparent_flagged(self, tmp_path):
        path = _save(Image.new("RGBA", (10, 10), (255, 0, 0, 0)), tmp_path / "t.png")
        result = check_image(path)
        assert any(i.startswith("transparent") for i in result.issues)
        assert "transparent 100.0%" in result.issues

    def test_fully_opaque_not_flagged(self, tmp_path):
        path = _save(Image.new("RGBA", (10, 10), (255, 0, 0, 255)), tmp_path / "o.png")
        result = check_image(path)
        assert not any(i.startswith("transparent") for i in result.issues)

    def test_below_threshold_not_flagged(self, tmp_path):
        # 1 of 100 pixels transparent = 1% ; threshold default is 1% (strict >).
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))
        path = _save(img, tmp_path / "edge.png")
        result = check_image(path, transparency_threshold=0.01)
        assert not any(i.startswith("transparent") for i in result.issues)

    def test_custom_threshold_can_flag(self, tmp_path):
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))  # 1% transparent
        path = _save(img, tmp_path / "edge.png")
        result = check_image(path, transparency_threshold=0.005)
        assert any(i.startswith("transparent") for i in result.issues)

    def test_rgb_image_skips_transparency(self, tmp_path):
        path = _save(Image.new("RGB", (10, 10), "red"), tmp_path / "rgb.png")
        assert not any(i.startswith("transparent") for i in check_image(path).issues)


# --- check_image: fill-band detection ---


class TestFillBand:
    def test_uniform_bottom_band_flagged(self, tmp_path):
        # Solid-color tall image: bottom band has zero variance.
        path = _save(Image.new("RGB", (20, 100), (120, 120, 120)), tmp_path / "u.png")
        result = check_image(path)
        assert "uniform bottom band" in result.issues

    def test_noisy_bottom_band_not_flagged(self, tmp_path):
        # Tall image with a high-variance bottom band.
        img = Image.new("RGB", (20, 100), (120, 120, 120))
        for y in range(50, 100):
            for x in range(20):
                v = 0 if (x + y) % 2 == 0 else 255
                img.putpixel((x, y), (v, v, v))
        path = _save(img, tmp_path / "n.png")
        result = check_image(path)
        assert "uniform bottom band" not in result.issues

    def test_short_image_skips_band_check(self, tmp_path):
        # height <= band_height (default 50) → band logic never runs.
        path = _save(Image.new("RGB", (20, 30), (10, 10, 10)), tmp_path / "s.png")
        result = check_image(path)
        assert "uniform bottom band" not in result.issues
        assert result.ok

    def test_band_threshold_configurable(self, tmp_path):
        img = Image.new("RGB", (20, 100), (120, 120, 120))
        # Mild variation in the bottom band.
        for x in range(20):
            img.putpixel((x, 99), (123, 123, 123))
        path = _save(img, tmp_path / "m.png")
        # A very low std threshold treats the mild variation as non-uniform.
        result = check_image(path, band_std_threshold=0.001)
        assert "uniform bottom band" not in result.issues


# --- CheckResult.summary ---


class TestSummary:
    def test_ok_summary(self):
        r = CheckResult(path=Path("/tmp/a.png"), ok=True, issues=[])
        assert r.summary() == "  OK  /tmp/a.png"

    def test_fail_summary_joins_issues(self):
        r = CheckResult(
            path=Path("/tmp/b.png"),
            ok=False,
            issues=["transparent 50.0%", "uniform bottom band"],
        )
        s = r.summary()
        assert "FAIL /tmp/b.png" in s
        assert "transparent 50.0%, uniform bottom band" in s


# --- check_directory ---


class TestCheckDirectory:
    def test_returns_one_result_per_image(self, tmp_path):
        _save(Image.new("RGB", (10, 10), "red"), tmp_path / "a.png")
        _save(Image.new("RGB", (10, 10), "blue"), tmp_path / "b.jpg")
        results = check_directory(tmp_path)
        assert len(results) == 2
        assert all(isinstance(r, CheckResult) for r in results)

    def test_ignores_non_image_files(self, tmp_path):
        _save(Image.new("RGB", (10, 10), "red"), tmp_path / "a.png")
        (tmp_path / "notes.txt").write_text("hello")
        (tmp_path / "data.json").write_text("{}")
        results = check_directory(tmp_path)
        assert len(results) == 1
        assert results[0].path.name == "a.png"

    def test_results_sorted_by_path(self, tmp_path):
        for name in ("c.png", "a.png", "b.png"):
            _save(Image.new("RGB", (10, 10), "red"), tmp_path / name)
        results = check_directory(tmp_path)
        assert [r.path.name for r in results] == ["a.png", "b.png", "c.png"]

    def test_empty_directory(self, tmp_path):
        assert check_directory(tmp_path) == []

    def test_threshold_forwarded(self, tmp_path):
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))  # 1% transparent
        _save(img, tmp_path / "a.png")
        flagged = check_directory(tmp_path, transparency_threshold=0.005)
        assert any(i.startswith("transparent") for i in flagged[0].issues)
