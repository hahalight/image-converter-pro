"""
Image Converter Pro - 유닛 테스트
실행: pytest tests/test_converter.py -v
또는: python tests/test_converter.py
"""
import sys, os
from pathlib import Path

# src 디렉터리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import pytest
except ImportError:
    pytest = None
from PIL import Image
import converter as conv

TMP = Path(__file__).parent / "_tmp"
TMP.mkdir(exist_ok=True)


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def make_rgba(path, color=(200, 100, 50, 180), size=(100, 80)):
    img = Image.new("RGBA", size, color)
    img.save(str(path), format="PNG")
    return str(path)

def make_rgb(path, color=(80, 160, 240), size=(100, 80)):
    img = Image.new("RGB", size, color)
    img.save(str(path), format="JPEG", quality=90)
    return str(path)

def make_gif(path, colors=None, size=(64, 64)):
    if colors is None:
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    frames = [Image.new("RGB", size, c) for c in colors]
    frames[0].save(str(path), format="GIF", save_all=True,
                   append_images=frames[1:], loop=0,
                   duration=[100] * len(frames))
    return str(path)


# ── 유틸 함수 ──────────────────────────────────────────────────────────────────

class TestComputeSize:
    def test_no_target(self):
        assert conv._compute_size((100, 80), None, None, True) == (100, 80)

    def test_width_only_ratio(self):
        assert conv._compute_size((200, 100), 100, None, True) == (100, 50)

    def test_height_only_ratio(self):
        assert conv._compute_size((200, 100), None, 25, True) == (50, 25)

    def test_both_fit_ratio(self):
        assert conv._compute_size((200, 100), 50, 50, True) == (50, 25)

    def test_no_ratio(self):
        assert conv._compute_size((200, 100), 60, 40, False) == (60, 40)


class TestFlattenAlpha:
    def test_rgba_to_rgb(self):
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
        out = conv._flatten_alpha(img, (255, 255, 255))
        assert out.mode == "RGB"

    def test_fully_transparent_becomes_bg(self):
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
        out = conv._flatten_alpha(img, (0, 0, 255))
        assert out.getpixel((0, 0)) == (0, 0, 255)


# ── convert_single ─────────────────────────────────────────────────────────────

class TestConvertSingle:
    def test_png_to_jpeg(self):
        src = make_rgba(TMP / "s_src.png")
        dst = str(TMP / "s_out.jpg")
        conv.convert_single(src, dst, "JPEG", quality=85)
        assert Image.open(dst).mode == "RGB"

    def test_png_to_png_keep_alpha_true(self):
        src = make_rgba(TMP / "s_alpha.png", color=(255, 0, 0, 128))
        dst = str(TMP / "s_alpha_out.png")
        conv.convert_single(src, dst, "PNG", keep_alpha=True)
        px = Image.open(dst).getpixel((50, 40))
        assert px[3] == 128

    def test_png_to_png_keep_alpha_false(self):
        src = make_rgba(TMP / "s_flat.png", color=(255, 0, 0, 128))
        dst = str(TMP / "s_flat_out.png")
        conv.convert_single(src, dst, "PNG", keep_alpha=False, bg_color=(0, 0, 255))
        img = Image.open(dst)
        assert img.mode == "RGB"

    def test_png_to_webp_keep_alpha(self):
        src = make_rgba(TMP / "s_webp.png")
        dst = str(TMP / "s_webp_out.webp")
        conv.convert_single(src, dst, "WEBP", keep_alpha=True)
        assert Image.open(dst).mode == "RGBA"

    def test_png_to_webp_no_alpha(self):
        src = make_rgba(TMP / "s_webp2.png")
        dst = str(TMP / "s_webp2_out.webp")
        conv.convert_single(src, dst, "WEBP", keep_alpha=False)
        assert Image.open(dst).mode == "RGB"

    def test_resize_ratio(self):
        src = make_rgba(TMP / "s_resize.png", size=(200, 100))
        dst = str(TMP / "s_resize_out.png")
        conv.convert_single(src, dst, "PNG", width=50, keep_ratio=True)
        assert Image.open(dst).size == (50, 25)

    def test_resize_no_ratio(self):
        src = make_rgba(TMP / "s_nratio.png", size=(200, 100))
        dst = str(TMP / "s_nratio_out.png")
        conv.convert_single(src, dst, "PNG", width=60, height=40, keep_ratio=False)
        assert Image.open(dst).size == (60, 40)

    def test_bmp_output(self):
        src = make_rgba(TMP / "s_bmp.png")
        dst = str(TMP / "s_out.bmp")
        conv.convert_single(src, dst, "BMP")
        assert Path(dst).exists()

    def test_tiff_output(self):
        src = make_rgba(TMP / "s_tiff.png")
        dst = str(TMP / "s_out.tiff")
        conv.convert_single(src, dst, "TIFF")
        assert Path(dst).exists()

    def test_ico_output(self):
        src = make_rgba(TMP / "s_ico.png")
        dst = str(TMP / "s_out.ico")
        conv.convert_single(src, dst, "ICO")
        assert Path(dst).exists()

    def test_gif_frame_extraction(self):
        src = make_gif(TMP / "s_anim.gif")
        dst = str(TMP / "s_frame0.png")
        conv.convert_single(src, dst, "PNG", frame_index=0)
        assert Path(dst).exists()

    def test_gif_second_frame(self):
        src = make_gif(TMP / "s_anim2.gif")
        dst = str(TMP / "s_frame1.png")
        conv.convert_single(src, dst, "PNG", frame_index=1)
        assert Path(dst).exists()


# ── get_image_info ─────────────────────────────────────────────────────────────

class TestGetImageInfo:
    def test_static_png(self):
        src = make_rgba(TMP / "info_static.png")
        info = conv.get_image_info(src)
        assert info["format"] == "PNG"
        assert info["has_alpha"] is True
        assert info["animated"] is False
        assert info["frames"] == 1

    def test_animated_gif(self):
        src = make_gif(TMP / "info_anim.gif", colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        info = conv.get_image_info(src)
        assert info["animated"] is True
        assert info["frames"] == 3


# ── convert_animated ───────────────────────────────────────────────────────────

class TestConvertAnimated:
    def test_gif_to_webp_keep_alpha(self):
        src = make_gif(TMP / "ca_src.gif")
        dst = str(TMP / "ca_out.webp")
        conv.convert_animated(src, dst, "WEBP", keep_alpha=True)
        assert conv.get_image_info(dst)["frames"] == 4

    def test_gif_to_apng(self):
        src = make_gif(TMP / "ca_src2.gif")
        dst = str(TMP / "ca_out.png")
        conv.convert_animated(src, dst, "APNG", keep_alpha=True)
        assert conv.get_image_info(dst)["frames"] == 4

    def test_gif_to_gif(self):
        src = make_gif(TMP / "ca_src3.gif")
        dst = str(TMP / "ca_out2.gif")
        conv.convert_animated(src, dst, "GIF")
        assert conv.get_image_info(dst)["frames"] == 4

    def test_invalid_format_raises(self):
        src = make_gif(TMP / "ca_bad.gif")
        try:
            conv.convert_animated(src, str(TMP / "ca_bad.bmp"), "BMP")
            raise AssertionError("ValueError 미발생")
        except ValueError:
            pass  # 정상

    def test_progress_cb(self):
        src = make_gif(TMP / "ca_prog.gif")
        calls = []
        conv.convert_animated(src, str(TMP / "ca_prog.webp"), "WEBP",
                               progress_cb=lambda c, t: calls.append((c, t)))
        assert len(calls) == 4
        assert calls[-1] == (4, 4)


# ── frames_to_animation ────────────────────────────────────────────────────────

class TestFramesToAnimation:
    def _frames(self, n=3):
        paths = []
        colors = [(255, 0, 0, 255), (0, 200, 0, 255), (0, 0, 255, 255)]
        for i in range(n):
            p = TMP / f"fta_frame_{i}.png"
            make_rgba(p, color=colors[i % len(colors)])
            paths.append(str(p))
        return paths

    def test_to_gif(self):
        dst = str(TMP / "fta.gif")
        conv.frames_to_animation(self._frames(), dst, "GIF", duration_ms=120)
        assert conv.get_image_info(dst)["animated"] is True

    def test_to_webp_keep_alpha(self):
        dst = str(TMP / "fta_alpha.webp")
        conv.frames_to_animation(self._frames(), dst, "WEBP", keep_alpha=True)
        assert conv.get_image_info(dst)["frames"] == 3

    def test_to_webp_no_alpha(self):
        dst = str(TMP / "fta_flat.webp")
        conv.frames_to_animation(self._frames(), dst, "WEBP", keep_alpha=False)
        assert Path(dst).exists()

    def test_to_apng(self):
        dst = str(TMP / "fta.png")
        conv.frames_to_animation(self._frames(), dst, "APNG")
        assert conv.get_image_info(dst)["frames"] == 3

    def test_progress_cb(self):
        calls = []
        dst = str(TMP / "fta_prog.gif")
        conv.frames_to_animation(self._frames(3), dst, "GIF",
                                  progress_cb=lambda c, t: calls.append((c, t)))
        assert calls[-1] == (3, 3)


# ── animation_to_frames ────────────────────────────────────────────────────────

class TestAnimationToFrames:
    def test_extract_png_keep_alpha(self):
        src = make_gif(TMP / "atf_src.gif",
                       colors=[(255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255)])
        out = conv.animation_to_frames(src, str(TMP / "atf_alpha"), "PNG",
                                        keep_alpha=True)
        assert len(out) == 5
        assert all(Path(p).exists() for p in out)

    def test_extract_jpeg_no_alpha(self):
        src = make_gif(TMP / "atf_src2.gif", colors=[(0, 255, 0)] * 3)
        out = conv.animation_to_frames(src, str(TMP / "atf_jpg"), "JPEG",
                                        keep_alpha=False)
        assert all(Path(p).suffix == ".jpg" for p in out)
        assert Image.open(out[0]).mode == "RGB"


# ── convert_sequence ───────────────────────────────────────────────────────────

class TestConvertSequence:
    def test_batch_png_to_jpeg(self):
        srcs = [make_rgba(TMP / f"seq_{i}.png", color=(i*60, 100, 200, 255))
                for i in range(3)]
        outs = conv.convert_sequence(srcs, str(TMP / "seq_out"), "JPEG", quality=80)
        assert len(outs) == 3
        assert all(Path(p).exists() and Path(p).suffix == ".jpg" for p in outs)


# ── 정리 ──────────────────────────────────────────────────────────────────────

def teardown_module(_):
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)


# ── 직접 실행 지원 (pytest 없이도 동작) ─────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    passed = failed = 0
    test_classes = [
        TestComputeSize, TestFlattenAlpha, TestConvertSingle,
        TestGetImageInfo, TestConvertAnimated, TestFramesToAnimation,
        TestAnimationToFrames, TestConvertSequence,
    ]
    for cls in test_classes:
        obj = cls()
        methods = [m for m in dir(obj) if m.startswith("test_")]
        for m in methods:
            try:
                getattr(obj, m)()
                print(f"  PASS  {cls.__name__}.{m}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {cls.__name__}.{m}: {e}")
                traceback.print_exc()
                failed += 1
    import shutil; shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{'='*50}")
    print(f"  PASS: {passed}   FAIL: {failed}   TOTAL: {passed+failed}")
    print(f"{'='*50}")
    sys.exit(0 if failed == 0 else 1)
