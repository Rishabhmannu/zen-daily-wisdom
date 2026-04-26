from __future__ import annotations

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def build_telegram_card_image(
    thought_of_day: str,
    theme_of_day: str,
    size: tuple[int, int] = (1080, 1080),
) -> bytes:
    width, height = size
    image = Image.new("RGB", size, "#f7efe6")
    draw = ImageDraw.Draw(image)

    # Soft organic accents for calm visual identity.
    draw.ellipse((40, 40, 340, 320), fill="#e3f2dc")
    draw.ellipse((760, 90, 1040, 370), fill="#f7d9df")
    draw.ellipse((120, 760, 420, 1040), fill="#d8eaf9")
    draw.ellipse((730, 730, 1060, 1060), fill="#f2d6c2")

    title_font = _font(62)
    theme_font = _font(42)
    thought_font = _font(40)
    footer_font = _font(30)

    title = "Zen Daily Wisdom"
    draw.text((90, 110), title, fill="#2f3b2f", font=title_font)
    draw.text((90, 210), f"Theme: {theme_of_day}", fill="#3f5a42", font=theme_font)

    wrapped = textwrap.fill(thought_of_day.strip(), width=36)
    draw.text((90, 320), wrapped, fill="#3d3d3d", font=thought_font, spacing=10)

    draw.text((90, 970), "Pause. Breathe. Continue gently.", fill="#4a5f4a", font=footer_font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
