from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from moviealpha import __version__
from moviealpha.color import to_hex
from moviealpha.keying import (
    KEY_METHODS,
    OUTPUT_FORMATS,
    default_output_path,
    encode_alpha_video,
    encode_preview_png,
    extract_frame,
    resolve_key_color,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moviealpha",
        description="指定色をアルファチャンネルに置き換えて透過動画を書き出します。",
    )
    parser.add_argument("input", nargs="?", type=Path, help="入力動画（MP4 など）。--gui では省略可")
    parser.add_argument("-o", "--output", type=Path, help="出力パス。省略時は INPUT_alpha.webm")
    parser.add_argument("--color", default="auto", help="キー色。#RRGGBB / 0xRRGGBB / auto")
    parser.add_argument(
        "--threshold",
        "--similarity",
        dest="threshold",
        type=float,
        default=0.08,
        help="完全に透明にする色距離のしきい値 0〜1（別名: --similarity）",
    )
    parser.add_argument(
        "--softness",
        "--smoothness",
        "--blend",
        dest="softness",
        type=float,
        default=0.12,
        help="しきい値の外側を半透明にする幅 0〜1（別名: --smoothness / --blend）",
    )
    parser.add_argument("--method", choices=KEY_METHODS, default="colorkey")
    parser.add_argument("--format", choices=OUTPUT_FORMATS, default="webm")
    parser.add_argument("--preview", type=Path, help="透過プレビュー PNG だけ書き出す")
    parser.add_argument("--time", type=float, default=0.0, help="プレビュー／自動色の秒位置")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--gui", action="store_true", help="クリックで色を指定する画面を開く")
    parser.add_argument("--version", action="version", version=f"moviealpha {__version__}")
    return parser


def _validate_ranges(threshold: float, softness: float) -> None:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold は 0.0〜1.0 です。")
    if not 0.0 <= softness <= 1.0:
        raise ValueError("softness は 0.0〜1.0 です。")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path: Path | None = args.input

    try:
        _validate_ranges(args.threshold, args.softness)
        if args.gui:
            from moviealpha.gui import run_gui

            if input_path is not None and not input_path.is_file():
                parser.error(f"入力ファイルがありません: {input_path}")
            run_gui(
                input_path=input_path,
                color_text=args.color,
                threshold=args.threshold,
                softness=args.softness,
                method=args.method,
                fmt=args.format,
            )
            return 0

        if input_path is None:
            parser.error("入力ファイルを指定するか、--gui で画面を開いてください。")
        if not input_path.is_file():
            parser.error(f"入力ファイルがありません: {input_path}")

        with tempfile.TemporaryDirectory(prefix="moviealpha-") as temp_dir:
            frame = extract_frame(input_path, Path(temp_dir) / "frame.png", args.time)
            color_rgb = resolve_key_color(args.color, frame)

        print(f"key color: {to_hex(color_rgb)}")
        print(f"threshold: {args.threshold:.3f}  softness: {args.softness:.3f}")
        if args.preview is not None:
            encode_preview_png(
                input_path,
                args.preview,
                color_rgb,
                args.threshold,
                args.softness,
                args.method,
                args.time,
            )
            print(f"wrote {args.preview}")
            return 0

        output_path = args.output or default_output_path(input_path, args.format)
        encode_alpha_video(
            input_path,
            output_path,
            color_rgb,
            args.threshold,
            args.softness,
            args.method,
            args.format,
            keep_audio=not args.no_audio,
        )
        print(f"wrote {output_path}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
