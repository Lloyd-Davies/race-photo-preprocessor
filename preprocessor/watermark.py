"""Watermark compositing utilities."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from preprocessor.pipeline import ProcessConfig


def apply_watermark(img: Image.Image, config: "ProcessConfig") -> Image.Image:
    """Draw a subtle diagonal repeating text pattern and return RGB image."""
    text = config.watermark_text
    if not text:
        return img

    w, h = img.size
    shortest = min(w, h)
    font_size = max(14, int(shortest * 0.028))

    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    for face in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"):
        try:
            font = ImageFont.truetype(face, font_size)
            break
        except (IOError, OSError):
            pass
    else:
        font = ImageFont.load_default()

    # Measure text
    _tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = _tmp.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Keep this subtle even at high opacity settings.
    base_alpha = max(0, min(255, int(config.watermark_opacity / 100 * 255)))
    alpha = max(12, min(120, int(base_alpha * 0.45)))

    spacing_x = max(int(tw * 2.1), int(shortest * 0.22))
    spacing_y = max(int(th * 2.8), int(shortest * 0.16))

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

    rotated = pattern.rotate(-32, resample=Image.Resampling.BICUBIC)

    left = (diag - w) // 2
    top = (diag - h) // 2
    overlay = rotated.crop((left, top, left + w, top + h))

    base = img.convert("RGBA")
    merged = Image.alpha_composite(base, overlay)
    return merged.convert("RGB")
