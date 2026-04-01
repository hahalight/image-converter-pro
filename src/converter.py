"""
Image Converter Engine
Handles all image conversion, resize, sequence, and animation operations.
"""
import os
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Callable
from PIL import Image, ImageSequence

try:
    import pillow_avif  # noqa: F401 - AVIF support plugin (optional)
except ImportError:
    pass  # AVIF support disabled — install pillow-avif-plugin to enable


# ── Supported formats ──────────────────────────────────────────────────────────
INPUT_FORMATS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif",
    ".gif", ".apng", ".ico", ".avif", ".psd", ".tga",
    ".ppm", ".pgm", ".pbm",
}

OUTPUT_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "GIF": ".gif",
    "APNG": ".png",   # animated PNG saved as PNG
    "ICO": ".ico",
    "AVIF": ".avif",
    "TGA": ".tga",
}

# Formats that support alpha channel
ALPHA_FORMATS = {"PNG", "WEBP", "TIFF", "APNG", "GIF", "ICO", "AVIF", "TGA"}

# Animation-capable output formats
ANIM_OUTPUT_FORMATS = {"GIF", "WEBP", "APNG"}


# ── Helper utilities ───────────────────────────────────────────────────────────

def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _ensure_alpha(img: Image.Image) -> Image.Image:
    """Convert image to RGBA if it has no alpha channel."""
    if img.mode not in ("RGBA", "LA", "PA"):
        return img.convert("RGBA")
    return img


def _flatten_alpha(img: Image.Image, bg_color: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Composite RGBA image onto a solid background (for formats without alpha)."""
    if img.mode in ("RGBA", "LA", "PA"):
        background = Image.new("RGB", img.size, bg_color)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB") if img.mode != "RGB" else img


def _compute_size(
    original: Tuple[int, int],
    target_w: Optional[int],
    target_h: Optional[int],
    keep_ratio: bool,
) -> Tuple[int, int]:
    ow, oh = original
    if not target_w and not target_h:
        return ow, oh
    if keep_ratio:
        if target_w and target_h:
            ratio = min(target_w / ow, target_h / oh)
            return int(ow * ratio), int(oh * ratio)
        if target_w:
            return target_w, int(oh * target_w / ow)
        return int(ow * target_h / oh), target_h
    return target_w or ow, target_h or oh


def _resize_frame(
    frame: Image.Image,
    new_size: Tuple[int, int],
    resample=Image.LANCZOS,
) -> Image.Image:
    if frame.size == new_size:
        return frame
    return frame.resize(new_size, resample)


def _natural_sort_key(path: Path):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", path.stem)]


# ── Frame extraction ───────────────────────────────────────────────────────────

def extract_frames(img: Image.Image) -> List[Tuple[Image.Image, int]]:
    """
    Return list of (frame_RGBA, duration_ms) for all frames in an animated image.
    For static images returns a single frame with duration 0.
    Uses seek-based iteration for reliable multi-frame detection.
    """
    n = getattr(img, "n_frames", 1)
    frames = []
    for i in range(n):
        try:
            img.seek(i)
        except EOFError:
            break
        duration = img.info.get("duration", 100)
        frames.append((img.copy().convert("RGBA"), int(duration)))
    if not frames:
        frames = [(img.convert("RGBA"), 0)]
    return frames


# ── Single image conversion ────────────────────────────────────────────────────

def convert_single(
    src_path: str,
    dst_path: str,
    fmt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_ratio: bool = True,
    quality: int = 90,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    frame_index: int = 0,
    keep_alpha: bool = True,
) -> None:
    """
    Convert a single image (or one frame from an animated image).
    keep_alpha: True=알파채널 유지(형식 지원 시), False=배경색으로 합성
    """
    fmt = fmt.upper()
    img = Image.open(src_path)

    # Extract the desired frame
    frames = extract_frames(img)
    frame_idx = _clamp(frame_index, 0, len(frames) - 1)
    frame, _ = frames[frame_idx]

    # Resize
    new_size = _compute_size(frame.size, width, height, keep_ratio)
    frame = _resize_frame(frame, new_size)

    # Alpha handling
    if keep_alpha and fmt in ALPHA_FORMATS:
        out_img = frame  # keep RGBA
    else:
        out_img = _flatten_alpha(frame, bg_color)

    # ICO special: needs RGB or RGBA
    save_kwargs: Dict[str, Any] = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif fmt == "WEBP":
        save_kwargs["quality"] = quality
        save_kwargs["method"] = 6
    elif fmt == "AVIF":
        save_kwargs["quality"] = quality
    elif fmt == "TIFF":
        save_kwargs["compression"] = "tiff_lzw"
    elif fmt == "ICO":
        # ICO supports limited sizes; clamp to max 256
        ico_size = tuple(_clamp(d, 1, 256) for d in out_img.size)
        out_img = out_img.resize(ico_size, Image.LANCZOS)
        if out_img.mode not in ("RGBA", "RGB"):
            out_img = out_img.convert("RGBA")

    pil_fmt = "PNG" if fmt == "APNG" else fmt
    out_img.save(dst_path, format=pil_fmt, **save_kwargs)


# ── Animated image conversion ──────────────────────────────────────────────────

def convert_animated(
    src_path: str,
    dst_path: str,
    fmt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_ratio: bool = True,
    quality: int = 90,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    loop: int = 0,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    keep_alpha: bool = True,
) -> None:
    """
    Convert an animated image to another animated format.

    fmt must be one of ANIM_OUTPUT_FORMATS: GIF, WEBP, APNG.
    """
    fmt = fmt.upper()
    if fmt not in ANIM_OUTPUT_FORMATS:
        raise ValueError(f"'{fmt}' does not support animation. Use: {ANIM_OUTPUT_FORMATS}")

    img = Image.open(src_path)
    frames_raw = extract_frames(img)
    total = len(frames_raw)

    processed: List[Image.Image] = []
    durations: List[int] = []

    for i, (frame, dur) in enumerate(frames_raw):
        new_size = _compute_size(frame.size, width, height, keep_ratio)
        frame = _resize_frame(frame, new_size)
        processed.append(frame)
        durations.append(dur if dur > 0 else 100)
        if progress_cb:
            progress_cb(i + 1, total)

    if not processed:
        raise ValueError("No frames found in source image.")

    first = processed[0]
    rest = processed[1:]

    if fmt == "GIF":
        # GIF: palette mode; keep_alpha=True preserves transparency index
        gif_frames = []
        for f in processed:
            if keep_alpha and f.mode == "RGBA":
                gif_frames.append(f.convert("P", palette=Image.ADAPTIVE, colors=255))
            else:
                gif_frames.append(_flatten_alpha(f, bg_color).convert("P", palette=Image.ADAPTIVE, colors=256))
        gif_frames[0].save(
            dst_path,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            loop=loop,
            duration=list(durations),
            optimize=True,
        )

    elif fmt == "WEBP":
        first_out = first if keep_alpha else _flatten_alpha(first, bg_color)
        rest_out  = [f if keep_alpha else _flatten_alpha(f, bg_color) for f in rest]
        first_out.save(
            dst_path,
            format="WEBP",
            save_all=True,
            append_images=rest_out,
            loop=loop,
            duration=list(durations),
            quality=quality,
            method=6,
        )

    elif fmt == "APNG":
        # APNG natively supports full RGBA transparency
        first.save(
            dst_path,
            format="PNG",
            save_all=True,
            append_images=rest,
            loop=loop,
            duration=list(durations),
        )


# ── Sequence conversion ────────────────────────────────────────────────────────

def convert_sequence(
    src_paths: List[str],
    dst_dir: str,
    dst_fmt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_ratio: bool = True,
    quality: int = 90,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> List[str]:
    """
    Batch-convert a list of source images.

    Returns list of output paths.
    """
    dst_fmt = dst_fmt.upper()
    ext = OUTPUT_FORMATS.get(dst_fmt, f".{dst_fmt.lower()}")
    os.makedirs(dst_dir, exist_ok=True)
    outputs = []

    for i, src in enumerate(src_paths):
        stem = Path(src).stem
        dst = os.path.join(dst_dir, stem + ext)
        convert_single(src, dst, dst_fmt, width, height, keep_ratio, quality, bg_color)
        outputs.append(dst)
        if progress_cb:
            progress_cb(i + 1, len(src_paths))

    return outputs


def frames_to_animation(
    src_paths: List[str],
    dst_path: str,
    fmt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_ratio: bool = True,
    quality: int = 90,
    duration_ms: int = 100,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    loop: int = 0,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    keep_alpha: bool = True,
) -> None:
    """
    Assemble a list of still images into an animated file (GIF / WEBP / APNG).
    """
    fmt = fmt.upper()
    if fmt not in ANIM_OUTPUT_FORMATS:
        raise ValueError(f"'{fmt}' does not support animation. Use: {ANIM_OUTPUT_FORMATS}")

    total = len(src_paths)
    processed: List[Image.Image] = []

    for i, src in enumerate(src_paths):
        img = Image.open(src).convert("RGBA")
        new_size = _compute_size(img.size, width, height, keep_ratio)
        img = _resize_frame(img, new_size)
        processed.append(img)
        if progress_cb:
            progress_cb(i + 1, total)

    if not processed:
        raise ValueError("No source images provided.")

    first = processed[0]
    rest = processed[1:]
    durations = [duration_ms] * len(processed)

    if fmt == "GIF":
        gif_frames = []
        for f in processed:
            if keep_alpha and f.mode == "RGBA":
                gif_frames.append(f.convert("P", palette=Image.ADAPTIVE, colors=255))
            else:
                gif_frames.append(_flatten_alpha(f, bg_color).convert("P", palette=Image.ADAPTIVE, colors=256))
        gif_frames[0].save(
            dst_path,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            loop=loop,
            duration=list(durations),
            optimize=True,
        )
    elif fmt == "WEBP":
        first_out = first if keep_alpha else _flatten_alpha(first, bg_color)
        rest_out  = [f if keep_alpha else _flatten_alpha(f, bg_color) for f in rest]
        first_out.save(
            dst_path,
            format="WEBP",
            save_all=True,
            append_images=rest_out,
            loop=loop,
            duration=list(durations),
            quality=quality,
            method=6,
        )
    elif fmt == "APNG":
        first.save(
            dst_path,
            format="PNG",
            save_all=True,
            append_images=rest,
            loop=loop,
            duration=list(durations),
        )


def animation_to_frames(
    src_path: str,
    dst_dir: str,
    dst_fmt: str = "PNG",
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_ratio: bool = True,
    quality: int = 90,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    progress_cb: Optional[Callable[[int, int], None]] = None,
    keep_alpha: bool = True,
) -> List[str]:
    """
    Extract all frames from an animated image and save as individual files.
    """
    dst_fmt = dst_fmt.upper()
    ext = OUTPUT_FORMATS.get(dst_fmt, f".{dst_fmt.lower()}")
    os.makedirs(dst_dir, exist_ok=True)

    img = Image.open(src_path)
    frames_raw = extract_frames(img)
    total = len(frames_raw)
    stem = Path(src_path).stem
    outputs = []

    for i, (frame, _) in enumerate(frames_raw):
        new_size = _compute_size(frame.size, width, height, keep_ratio)
        frame = _resize_frame(frame, new_size)

        if keep_alpha and dst_fmt in ALPHA_FORMATS:
            out = frame
        else:
            out = _flatten_alpha(frame, bg_color)

        dst = os.path.join(dst_dir, f"{stem}_frame{i:04d}{ext}")
        pil_fmt = "PNG" if dst_fmt == "APNG" else dst_fmt
        save_kw: Dict[str, Any] = {}
        if dst_fmt == "JPEG":
            save_kw["quality"] = quality
        elif dst_fmt == "WEBP":
            save_kw["quality"] = quality
        out.save(dst, format=pil_fmt, **save_kw)
        outputs.append(dst)
        if progress_cb:
            progress_cb(i + 1, total)

    return outputs


def get_image_info(src_path: str) -> Dict[str, Any]:
    """Return metadata dict for a given image file."""
    img = Image.open(src_path)
    n = getattr(img, "n_frames", 1)
    is_animated = getattr(img, "is_animated", n > 1)
    return {
        "path": src_path,
        "format": img.format or Path(src_path).suffix.upper().lstrip("."),
        "mode": img.mode,
        "size": img.size,
        "frames": n,
        "animated": is_animated,
        "has_alpha": img.mode in ("RGBA", "LA", "PA"),
        "info": img.info,
    }
