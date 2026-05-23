from __future__ import annotations

from pathlib import Path

from PIL import ImageFont


FONT_CANDIDATES = [
    Path(r"C:\Users\zazqi\Downloads\Kanit\Kanit-Bold.ttf"),
    Path(r"C:\Windows\Fonts\Kanit-Bold.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()
