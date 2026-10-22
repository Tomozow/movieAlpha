from __future__ import annotations

import shutil
from pathlib import Path

import ffmpeg
from PIL import Image

from moviealpha.color import parse_color, sample_corner_color, to_ffmpeg_color

OUTPUT_FORMATS = ("webm", "mov")
KEY_METHODS = ("colorkey", "chromakey")


class FFmpegNotFoundError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise FFmpegNotFoundError(
        "ffmpeg が見つかりません。FFmpeg をインストールし、PATH を通してください。"
    )


def probe_media(input_path: Path) -> dict:
    return ffmpeg.probe(str(input_path))


def has_audio(probe: dict) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))


def media_duration(input_path: Path) -> float:
    probe = probe_media(input_path)
    raw = probe.get("format", {}).get("duration")
    if raw not in (None, "N/A", ""):
        return max(0.0, float(raw))
    for stream in probe.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        raw = stream.get("duration")
        if raw not in (None, "N/A", ""):
            return max(0.0, float(raw))
    return 0.0


def extract_frame(input_path: Path, dest_png: Path, time_sec: float = 0.0) -> Image.Image:
    find_ffmpeg()
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    (
        ffmpeg.input(str(input_path), ss=max(0.0, time_sec))
        .output(str(dest_png), vframes=1, update=1)
        .overwrite_output()
        .run(quiet=True)
    )
    return Image.open(dest_png).convert("RGB")


def resolve_key_color(color_text: str, frame: Image.Image | None) -> tuple[int, int, int]:
    if color_text.strip().lower() == "auto":
        if frame is None:
            raise ValueError("auto にはプレビューフレームが必要です。")
        return sample_corner_color(frame)
    return parse_color(color_text)


def default_output_path(input_path: Path, fmt: str) -> Path:
    return input_path.with_name(f"{input_path.stem}_alpha.{fmt}")


def _video_output_kwargs(fmt: str) -> dict:
    if fmt == "webm":
        return {
            "vcodec": "libvpx-vp9",
            "pix_fmt": "yuva420p",
            "crf": 32,
            "deadline": "good",
            "cpu-used": 4,
            "b:v": 0,
            "auto-alt-ref": 0,
        }
    if fmt == "mov":
        return {
            "vcodec": "qtrle",
            "pix_fmt": "argb",
        }
    raise ValueError(f"未対応の出力形式です: {fmt}")


def build_key_filter(
    input_path: Path,
    color_rgb: tuple[int, int, int],
    threshold: float,
    softness: float,
    method: str,
    start_sec: float = 0.0,
):
    if method not in KEY_METHODS:
        raise ValueError(f"未対応の method です: {method}")
    source = ffmpeg.input(str(input_path), ss=start_sec) if start_sec > 0 else ffmpeg.input(str(input_path))
    video = source.video.filter("format", "rgba")
    color = to_ffmpeg_color(color_rgb)
    ffmpeg_softness = max(softness, 0.00001) if softness > 0 else 0.0
    if method == "colorkey":
        video = video.filter(
            "colorkey",
            color=color,
            similarity=max(threshold, 0.00001),
            blend=ffmpeg_softness,
        )
    else:
        video = video.filter(
            "chromakey",
            color=color,
            similarity=max(threshold, 0.00001),
            blend=ffmpeg_softness,
        )
    return video


def encode_alpha_video(
    input_path: Path,
    output_path: Path,
    color_rgb: tuple[int, int, int],
    threshold: float,
    softness: float,
    method: str = "colorkey",
    fmt: str = "webm",
    keep_audio: bool = True,
) -> Path:
    find_ffmpeg()
    if fmt not in OUTPUT_FORMATS:
        raise ValueError(f"未対応の出力形式です: {fmt}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video = build_key_filter(input_path, color_rgb, threshold, softness, method)
    kwargs = _video_output_kwargs(fmt)
    probe = probe_media(input_path)
    streams = [video]
    extra = dict(kwargs)
    if keep_audio and has_audio(probe):
        streams.append(ffmpeg.input(str(input_path)).audio)
        if fmt == "webm":
            extra["acodec"] = "libopus"
        elif fmt == "mov":
            extra["acodec"] = "aac"
    (
        ffmpeg.output(*streams, str(output_path), **extra)
        .overwrite_output()
        .run()
    )
    return output_path


def encode_preview_png(
    input_path: Path,
    output_png: Path,
    color_rgb: tuple[int, int, int],
    threshold: float,
    softness: float,
    method: str = "colorkey",
    time_sec: float = 0.0,
) -> Path:
    find_ffmpeg()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    video = build_key_filter(
        input_path, color_rgb, threshold, softness, method, start_sec=max(0.0, time_sec)
    )
    (
        ffmpeg.output(video, str(output_png), vframes=1, update=1, pix_fmt="rgba")
        .overwrite_output()
        .run(quiet=True)
    )
    return output_png
