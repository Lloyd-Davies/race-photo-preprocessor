"""Watermark compositing utilities."""
from __future__ import annotations

import threading
from typing import Callable, TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from preprocessor.pipeline import ProcessConfig


_POSITIONS: dict[str, tuple[float, float]] = {
    "top-left": (0.0, 0.0),
    "top-center": (0.5, 0.0),
    "top-right": (1.0, 0.0),
    "center-left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "center-right": (1.0, 0.5),
    "bottom-left": (0.0, 1.0),
    "bottom-center": (0.5, 1.0),
    "bottom-right": (1.0, 1.0),
}

_CACHE_LOCK = threading.RLock()
_FONT_CACHE: dict[int, ImageFont.ImageFont | ImageFont.FreeTypeFont] = {}
_OVERLAY_CACHE: dict[tuple[object, ...], Image.Image] = {}
_OVERLAY_CACHE_LIMIT = 64


def clear_watermark_cache() -> None:
    """Clear cached fonts and overlays. Intended for tests and benchmark setup."""
    with _CACHE_LOCK:
        _FONT_CACHE.clear()
        _OVERLAY_CACHE.clear()


def watermark_cache_info() -> dict[str, int]:
    """Return cache sizes for diagnostics and tests."""
    with _CACHE_LOCK:
        return {"fonts": len(_FONT_CACHE), "overlays": len(_OVERLAY_CACHE)}


def _load_font_uncached(font_size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for face in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"):
        try:
            return ImageFont.truetype(face, font_size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def _load_font(font_size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    with _CACHE_LOCK:
        font = _FONT_CACHE.get(font_size)
        if font is not None:
            return font

    font = _load_font_uncached(font_size)
    with _CACHE_LOCK:
        return _FONT_CACHE.setdefault(font_size, font)


def _cached_overlay(
    key: tuple[object, ...],
    build: Callable[[], Image.Image],
) -> Image.Image:
    with _CACHE_LOCK:
        overlay = _OVERLAY_CACHE.get(key)
        if overlay is not None:
            return overlay

    overlay = build()
    with _CACHE_LOCK:
        if len(_OVERLAY_CACHE) >= _OVERLAY_CACHE_LIMIT:
            _OVERLAY_CACHE.pop(next(iter(_OVERLAY_CACHE)))
        return _OVERLAY_CACHE.setdefault(key, overlay)


def _measure_text(text: str, font: ImageFont.ImageFont | ImageFont.FreeTypeFont) -> tuple[int, int]:
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = tmp.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _single_corner_overlay(
    size: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    text_size: tuple[int, int],
    config: "ProcessConfig",
    base_alpha: int,
) -> Image.Image:
    w, h = size
    tw, th = text_size
    shortest = min(w, h)
    margin = int(shortest * 0.03)
    fx, fy = _POSITIONS.get(config.watermark_position, _POSITIONS["bottom-right"])

    if fx == 0.0:
        x = margin
    elif fx == 1.0:
        x = w - margin - tw
    else:
        x = (w - tw) // 2

    if fy == 0.0:
        y = margin
    elif fy == 1.0:
        y = h - margin - th
    else:
        y = (h - th) // 2

    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.text((x, y), text, font=font, fill=(255, 255, 255, min(200, base_alpha)))
    return overlay


def _diagonal_overlay(
    size: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    text_size: tuple[int, int],
    config: "ProcessConfig",
    alpha: int,
) -> Image.Image:
    w, h = size
    tw, th = text_size
    shortest = min(w, h)
    spacing_x = max(int(tw * 1.4), int(shortest * max(5, min(70, config.watermark_spacing_x_pct)) / 100))
    spacing_y = max(int(th * 1.6), int(shortest * max(5, min(70, config.watermark_spacing_y_pct)) / 100))

    # Draw on a large square so post-rotation fully covers the image.
    diag = int((w * w + h * h) ** 0.5) + max(spacing_x, spacing_y) * 2
    pattern = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pattern)

    y = -spacing_y
    row = 0
    while y < diag + spacing_y:
        x_offset = (spacing_x // 2) if (row % 2) else 0
        x = -spacing_x + x_offset
        while x < diag + spacing_x:
            draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))
            x += spacing_x
        y += spacing_y
        row += 1

    angle = max(-80, min(80, int(config.watermark_angle)))
    rotated = pattern.rotate(angle, resample=Image.Resampling.BICUBIC)

    left = (diag - w) // 2
    top = (diag - h) // 2
    return rotated.crop((left, top, left + w, top + h))


def _overlay_key(
    size: tuple[int, int],
    text: str,
    font_size: int,
    config: "ProcessConfig",
    alpha: int,
    base_alpha: int,
) -> tuple[object, ...]:
    return (
        size,
        text,
        font_size,
        config.watermark_pattern,
        config.watermark_position,
        int(config.watermark_angle),
        int(config.watermark_spacing_x_pct),
        int(config.watermark_spacing_y_pct),
        int(config.watermark_font_scale_pct),
        alpha,
        base_alpha,
    )


def apply_watermark(img: Image.Image, config: "ProcessConfig") -> Image.Image:
    """Apply watermark pattern and return composited RGB image."""
    text = config.watermark_text
    if not text:
        return img

    w, h = img.size
    shortest = min(w, h)
    scale = max(50, min(250, int(config.watermark_font_scale_pct))) / 100.0
    font_size = max(14, int(shortest * 0.028 * scale))
    font = _load_font(font_size)
    text_size = _measure_text(text, font)

    base_alpha = max(0, min(255, int(config.watermark_opacity / 100 * 255)))
    alpha = max(12, min(120, int(base_alpha * 0.45)))
    size = (w, h)
    key = _overlay_key(size, text, font_size, config, alpha, base_alpha)

    if config.watermark_pattern == "single-corner":
        overlay = _cached_overlay(
            key,
            lambda: _single_corner_overlay(size, text, font, text_size, config, base_alpha),
        )
    else:
        overlay = _cached_overlay(
            key,
            lambda: _diagonal_overlay(size, text, font, text_size, config, alpha),
        )

    base = img.convert("RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")
