from __future__ import annotations

import re

from PIL import Image

HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")
OX_RE = re.compile(r"^0x([0-9A-Fa-f]{6})$", re.IGNORECASE)

NAMED_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "lime": (0, 255, 0),
    "blue": (0, 0, 255),
    "magenta": (255, 0, 255),
    "cyan": (0, 255, 255),
    "yellow": (255, 255, 0),
}


def parse_color(value: str) -> tuple[int, int, int]:
    text = value.strip()
    named = NAMED_COLORS.get(text.lower())
    if named is not None:
        return named
    match = HEX_RE.match(text) or OX_RE.match(text)
    if match is None:
        raise ValueError(f"色の指定が不正です: {value}")
    raw = match.group(1)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def to_ffmpeg_color(rgb: tuple[int, int, int]) -> str:
    return "0x{:02X}{:02X}{:02X}".format(*rgb)


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def sample_corner_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    inset_x = max(1, width // 50)
    inset_y = max(1, height // 50)
    points = (
        (inset_x, inset_y),
        (width - 1 - inset_x, inset_y),
        (inset_x, height - 1 - inset_y),
        (width - 1 - inset_x, height - 1 - inset_y),
    )
    counts: dict[tuple[int, int, int], int] = {}
    for point in points:
        color = rgb.getpixel(point)
        counts[color] = counts.get(color, 0) + 1
    return max(counts, key=counts.get)


def color_distance(sample_rgb: tuple[int, int, int], key_rgb: tuple[int, int, int]) -> float:
    """RGB ユークリッド距離を 0〜1 に正規化する（FFmpeg colorkey と同じ）。"""
    dr = sample_rgb[0] - key_rgb[0]
    dg = sample_rgb[1] - key_rgb[1]
    db = sample_rgb[2] - key_rgb[2]
    return ((dr * dr + dg * dg + db * db) / (255.0 * 255.0 * 3.0)) ** 0.5


def alpha_from_distance(delta: float, threshold: float, softness: float) -> int:
    """しきい値以内は透明、しきい値〜しきい値+softness は半透明。

    OBS Color Key の
    `saturate(max(dist - similarity, 0) / smoothness)` と
    FFmpeg colorkey の `(diff - similarity) / blend` と同じ。
    """
    if softness <= 0:
        return 0 if delta <= threshold else 255
    return int(max(0.0, min(1.0, (delta - threshold) / softness)) * 255)


def apply_colorkey(
    image: Image.Image,
    key_rgb: tuple[int, int, int],
    threshold: float,
    softness: float,
) -> Image.Image:
    src = image.convert("RGB")
    pixels = list(src.getdata())
    out: list[tuple[int, int, int, int]] = []
    for red, green, blue in pixels:
        delta = color_distance((red, green, blue), key_rgb)
        alpha = alpha_from_distance(delta, threshold, softness)
        out.append((red, green, blue, alpha))
    keyed = Image.new("RGBA", src.size)
    keyed.putdata(out)
    return keyed


def checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    width, height = size
    board = Image.new("RGB", size, (190, 190, 190))
    pixels = board.load()
    dark = (140, 140, 140)
    for y in range(height):
        for x in range(width):
            if ((x // cell) + (y // cell)) % 2 == 0:
                pixels[x, y] = dark
    return board


def composite_preview(
    image: Image.Image,
    key_rgb: tuple[int, int, int],
    threshold: float,
    softness: float,
) -> Image.Image:
    keyed = apply_colorkey(image, key_rgb, threshold, softness)
    return Image.alpha_composite(checkerboard(keyed.size).convert("RGBA"), keyed)
