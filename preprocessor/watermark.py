"""Watermark compositing utilities."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from preprocessor.pipeline import ProcessConfig

# position key → (x_fraction, y_fraction)
# x_fraction: 0=left edge, 0.5=centre, 1=right edge
# y_fraction: 0=top edge, 0.5=centre, 1=bottom edge
_POSITIONS: dict[str, tuple[float, float]] = {
    "top-left":      (0.0, 0.0),
    "top-center":    (0.5, 0.0),
    "top-right":     (1.0, 0.0),
    "center-left":   (0.0, 0.5),
    "center":        (0.5, 0.5),
    "center-right":  (1.0, 0.5),
    "bottom-left":   (0.0, 1.0),
    "bottom-center": (0.5, 1.0),
    "bottom-right":  (1.0, 1.0),
}


def apply_watermark(img: Image.Image, config: "ProcessConfig") -> Image.Image:
    """Draw a text watermark on *img* and return the composited RGB image."""
    text = config.watermark_text
    if not text:
        return img

    w, h = img.size
    margin = int(min(w, h) * 0.03)
    font_size = max(14, int(min(w, h) * 0.032))

    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    for face in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"):
        try:
            font = ImageFont.truetype(face, font_size)
            break
        except (IOError, OSError):
            pass
    else:
        font = ImageFont.load_default()

    # Measure text on a throw-away draw surface
    _tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = _tmp.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    fx, fy = _POSITIONS.get(config.watermark_position, _POSITIONS["bottom-right"])

    # Anchor: edge positions use margin, centre positions are truly centred
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

    alpha = max(0, min(255, int(config.watermark_opacity / 100 * 255)))
    shadow_off = max(1, font_size // 20)

    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Drop shadow
    draw.text(
        (x + shadow_off, y + shadow_off),
        text,
        font=font,
        fill=(0, 0, 0, min(alpha, 200)),
    )
    # Main text
    draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))

    merged = Image.alpha_composite(base, overlay)
    return merged.convert("RGB")
