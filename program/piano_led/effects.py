"""Small, reusable colour helpers used by manual effects."""

from __future__ import annotations

import colorsys


def rainbow_color(index: int, total: int) -> tuple[int, int, int]:
    if total <= 0:
        raise ValueError("total must be positive")
    red, green, blue = colorsys.hsv_to_rgb((index % total) / total, 1.0, 1.0)
    return round(red * 255), round(green * 255), round(blue * 255)
