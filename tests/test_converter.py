"""
Tests for converter.py
Run: pytest tests/test_converter.py -v
"""
import os
import sys
import pytest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import converter as conv

# ── Fixtures ───────────────────────────────────────────────────────────────────

TEMP = Path(__file__).parent / "_tmp"
TEMP.mkdir(exist_ok=True)


def _make_rgba(path: Path, size=(100, 80)) -> Path:
    """Create a small RGBA test PNG."""
    img = Image.new("RGBA", size, (200, 100, 50, 180))
    img.save(path, format="PNG")
    return path


def _make_rgb(path: Path, size=(100, 80)) -> Path:
    """Create a small RGB test JPEG."""
    img = Image.new("RGB", size, (80, 160, 240))
    img.save(path, format="JPEG", quality=90)
    return path


def _make_gif(path: Path, frames=4, size=(64, 64)) -> Path:
    """Create a small animated GIF."""
    imgs = []
    for i in range(frames):
        frame = Image.new("P", size, i * 60)
        imgs.append(frame)
    imgs[0].save(
        path, format="GIF", save_all=True,
        append_images=imgs[1:], loop=0, duration=100
    )
    return path


# ── Helper tests ───────────────────────────────────────────────────────────────

class TestComputeSize:
    def test_no_target(self):
        assert conv._compute_size((100, 80), None, None, True) == (100, 80)

    def test_width_only_ratio(self):
        w, h = conv._compute_size((200, 100), 100, None, True)
        assert w == 100 and h == 50

    def test_height_only_ratio(self):
        w, h = conv._compute_size((200, 100), None, 25, True)
        assert w == 50 and h == 25

    def test_both_fit_ratio(self):
        w, h = conv._compute_size((200, 100), 50, 50, True)
        # min ratio = 0.25 → (50, 25)
        assert w == 50 and h == 25

    def test_no_ratio(self):
        w, h = conv._compute_size((200, 100), 60, 40, False)
        assert w == 60 and h == 40


class TestFlattenAlpha:
    def test_rgba_to_rgb(self):
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
        out = conv._flatten_alpha(img, (255, 255, 255))
        assert out.mode == "RGB"

    def test_rgb_passthrough(self):
        img = Image.new("RGB", (4, 4), (10, 20, 30))
        out = conv._flatten_alpha(img)
        assert out.mode == "RGB"


# ── Single conversion ──────────────────────────────────────────────────────────

class TestConvertSingle:
    def test_png_to_jpeg(self):
        src = _make_rgba(TEMP / "src_rgba.png")
        dst = TEMP / "out.jpg"
        conv.convert_single(str(src), str(dst), "JPEG", quality=85)
        assert dst.exists()
        img = Image.open(dst)
        assert img.mode == "RGB"

    def test_png_to_png_keeps_alpha(self):
        src = _make_rgba(TEMP / "src_alpha.png")
        dst = TEMP / "out_alpha.png"
        conv.convert_single(str(src), str(dst), "PNG")
        assert dst.exists()
        img = Image.open(dst)
        assert img.mode == "RGBA"

    def test_resize_ratio(self):
        src = _make_rgba(TEMP / "src_resize.png", size=(200, 100))
        dst = TEMP / "out_resize.png"
        conv.convert_single(str(src), str(dst), "PNG", width=50, keep_ratio=True)
        img = Image.open(dst)
        assert img.size == (50, 25)

    def test_resize_no_ratio(self):
        src = _make_rgba(TEMP / "src_nratio.png", size=(200, 100))
        dst = TEMP / "out_nratio.png"
        conv.convert_single(str(src), str(dst), "PNG", width=60, height=40, keep_ratio=False)
        img = Image.open(dst)
        assert img.size == (60, 40)

    def test_jpeg_to_webp(self):
        src = _make_rgb(TEMP / "src.jpg")
        dst = TEMP / "out.webp"
        conv.convert_single(str(src), str(dst), "WEBP", quality=80)
        assert dst.exists()

    def test_gif_first_frame(self):
        src = _make_gif(TEMP / "src_anim.gif", frames=4)
        dst = TEMP / "out_frame0.png"
        conv.convert_single(str(src), str(dst), "PNG", frame_index=0)
        assert dst.exists()

    def test_gif_second_frame(self):
        src = _make_gif(TEMP / "src_anim2.gif", frames=4)
        dst = TEMP / "out_frame1.png"
        conv.convert_single(str(src), str(dst), "PNG", frame_index=1)
        assert dst.exists()


# ── get_image_info ─────────────────────────────────────────────────────────────

class TestGetImageInfo:
    def test_static_png(self):
        src = _make_rgba(TEMP / "info_src.png")
        info = conv.get_image_info(str(src))
        assert info["format"] == "PNG"
        assert info["has_alpha"] is True
        assert info["animated"] is False
        assert info["frames"] == 1

    def test_animated_gif(self):
        src = _make_gif(TEMP / "info_anim.gif", frames=3)
        info = conv.get_image_info(str(src))
        assert info["animated"] is True
        assert info["frames"] == 3


# ── Animated conversion ────────────────────────────────────────────────────────

class TestConvertAnimated:
    def test_gif_to_webp(self):
        src = _make_gif(TEMP / "anim_src.gif", frames=3)
        dst = TEMP / "anim_out.webp"
        conv.convert_animated(str(src), str(dst), "WEBP")
        assert dst.exists()

    def test_gif_to_apng(self):
        src = _make_gif(TEMP / "anim_src2.gif", frames=3)
        dst = TEMP / "anim_out.png"
        conv.convert_animated(str(src), str(dst), "APNG")
        assert dst.exists()

    def test_invalid_format_raises(self):
        src = _make_gif(TEMP / "anim_src3.gif", frames=2)
        dst = TEMP / "anim_bad.bmp"
        with pytest.raises(ValueError):
            conv.convert_animated(str(src), str(dst), "BMP")

    def test_progress_cb(self):
        src = _make_gif(TEMP / "anim_prog.gif", frames=4)
        dst = TEMP / "anim_prog_out.webp"
        calls = []
        conv.convert_animated(str(src), str(dst), "WEBP",
                               progress_cb=lambda cur, tot: calls.append((cur, tot)))
        assert len(calls) == 4
        assert calls[-1] == (4, 4)


# ── Sequence conversion ────────────────────────────────────────────────────────

class TestConvertSequence:
    def test_batch_png_to_jpeg(self):
        srcs = [str(_make_rgba(TEMP / f"seq_{i}.png")) for i in range(3)]
        out_dir = str(TEMP / "seq_out")
        outputs = conv.convert_sequence(srcs, out_dir, "JPEG", quality=80)
        assert len(outputs) == 3
        for p in outputs:
            assert Path(p).exists()
            assert Path(p).suffix == ".jpg"


# ── frames_to_animation ────────────────────────────────────────────────────────

class TestFramesToAnimation:
    def _make_frames(self, n=3) -> list:
        paths = []
        for i in range(n):
            p = TEMP / f"frame_{i}.png"
            _make_rgba(p, size=(64, 64))
            paths.append(str(p))
        return paths

    def test_frames_to_gif(self):
        frames = self._make_frames(3)
        dst = str(TEMP / "assembled.gif")
        conv.frames_to_animation(frames, dst, "GIF", duration_ms=120)
        assert Path(dst).exists()

    def test_frames_to_webp(self):
        frames = self._make_frames(3)
        dst = str(TEMP / "assembled.webp")
        conv.frames_to_animation(frames, dst, "WEBP")
        assert Path(dst).exists()

    def test_frames_to_apng(self):
        frames = self._make_frames(3)
        dst = str(TEMP / "assembled.png")
        conv.frames_to_animation(frames, dst, "APNG")
        assert Path(dst).exists()


# ── animation_to_frames ────────────────────────────────────────────────────────

class TestAnimationToFrames:
    def test_extract_all_frames(self):
        src = _make_gif(TEMP / "extract_src.gif", frames=5)
        out_dir = str(TEMP / "extracted_frames")
        outputs = conv.animation_to_frames(str(src), out_dir, "PNG")
        assert len(outputs) == 5
        for p in outputs:
            assert Path(p).exists()

    def test_extract_as_jpeg(self):
        src = _make_gif(TEMP / "extract_src2.gif", frames=3)
        out_dir = str(TEMP / "extracted_jpeg")
        outputs = conv.animation_to_frames(str(src), out_dir, "JPEG")
        for p in outputs:
            assert Path(p).suffix == ".jpg"


# ── Cleanup ────────────────────────────────────────────────────────────────────

def teardown_module(_):
    """Remove temp files after all tests."""
    import shutil
    shutil.rmtree(TEMP, ignore_errors=True)
