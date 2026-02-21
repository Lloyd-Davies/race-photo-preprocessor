"""Watermark compositing utilities."""
from __future__ import annotations

from typing import TYPE_CHECKING

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


def _load_font(font_size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    for face in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"):
        try:
            font = ImageFont.truetype(face, font_size)
            break
        except (IOError, OSError):
            pass
    else:
        font = ImageFont.load_default()
    return font


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

    # Measure text
    _tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = _tmp.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    base_alpha = max(0, min(255, int(config.watermark_opacity / 100 * 255)))
    alpha = max(12, min(120, int(base_alpha * 0.45)))

    base = img.convert("RGBA")

    if config.watermark_pattern == "single-corner":
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

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.text((x, y), text, font=font, fill=(255, 255, 255, min(200, base_alpha)))
        return Image.alpha_composite(base, overlay).convert("RGB")

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
    overlay = rotated.crop((left, top, left + w, top + h))

    merged = Image.alpha_composite(base, overlay)
    return merged.convert("RGB")
