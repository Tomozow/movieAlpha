from pathlib import Path

import ffmpeg
import pytest
from PIL import Image

from moviealpha.color import parse_color
from moviealpha.keying import encode_preview_png, find_ffmpeg, media_duration


def test_ffmpeg_available():
    assert Path(find_ffmpeg()).name.lower().startswith("ffmpeg")


def test_colorkey_preview_png(tmp_path: Path):
    src = tmp_path / "src.mp4"
    preview = tmp_path / "preview.png"
    (
        ffmpeg.input(
            "color=c=0x00FF00:s=64x32:d=0.2,format=yuv420p",
            f="lavfi",
        )
        .output(str(src), vcodec="libx264", pix_fmt="yuv420p", t=0.2)
        .overwrite_output()
        .run(quiet=True)
    )
    encode_preview_png(
        src,
        preview,
        parse_color("#00FF00"),
        threshold=0.1,
        softness=0.0,
        method="colorkey",
    )
    image = Image.open(preview).convert("RGBA")
    assert image.getpixel((2, 2))[3] == 0
    assert 0.15 <= media_duration(src) <= 0.25
