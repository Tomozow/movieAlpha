from moviealpha.cli import build_parser
from moviealpha.color import alpha_from_distance, apply_colorkey, color_distance, parse_color, to_ffmpeg_color, to_hex
from moviealpha.gui import format_timecode
from moviealpha.keying import default_output_path
from PIL import Image


def test_parse_color_hex_variants():
    assert parse_color("#00ff00") == (0, 255, 0)
    assert parse_color("00FF00") == (0, 255, 0)
    assert parse_color("0x000000") == (0, 0, 0)
    assert parse_color("black") == (0, 0, 0)


def test_ffmpeg_color_roundtrip():
    rgb = parse_color("#112233")
    assert to_hex(rgb) == "#112233"
    assert to_ffmpeg_color(rgb) == "0x112233"


def test_default_output_path():
    path = default_output_path(__import__("pathlib").Path("scene.mp4"), "webm")
    assert path.name == "scene_alpha.webm"


def test_colorkey_makes_exact_match_transparent():
    image = Image.new("RGB", (2, 1), (0, 0, 0))
    image.putpixel((1, 0), (255, 0, 0))
    keyed = apply_colorkey(image, (0, 0, 0), threshold=0.05, softness=0.0)
    assert keyed.getpixel((0, 0))[3] == 0
    assert keyed.getpixel((1, 0))[3] == 255


def test_threshold_band_is_semitransparent():
    delta = color_distance((40, 40, 40), (0, 0, 0))
    alpha = alpha_from_distance(delta, threshold=0.08, softness=0.12)
    expected = int(max(0.0, min(1.0, (delta - 0.08) / 0.12)) * 255)
    assert alpha == expected
    assert 0 < alpha < 255


def test_format_timecode():
    assert format_timecode(0) == "0:00.00"
    assert format_timecode(2.03) == "0:02.03"
    assert format_timecode(75.5) == "1:15.50"


def test_parser_gui_without_input():
    args = build_parser().parse_args(["--gui"])
    assert args.gui is True
    assert args.input is None


def test_hard_threshold_has_no_mid_alpha():
    assert alpha_from_distance(0.07, threshold=0.08, softness=0.0) == 0
    assert alpha_from_distance(0.09, threshold=0.08, softness=0.0) == 255
