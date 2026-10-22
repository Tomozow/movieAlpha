from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from moviealpha.color import composite_preview, parse_color, to_hex
from moviealpha.keying import (
    default_output_path,
    encode_alpha_video,
    extract_frame,
    media_duration,
    resolve_key_color,
)


def format_timecode(seconds: float) -> str:
    seconds = max(0.0, seconds)
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return f"{minutes}:{rest:05.2f}"


class ColorKeyWindow:
    def __init__(
        self,
        input_path: Path | None,
        color_text: str,
        threshold: float,
        softness: float,
        method: str,
        fmt: str,
    ) -> None:
        self.input_path = input_path
        self.method = method
        self.fmt = fmt
        self.frame_image: Image.Image | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.display_scale = 1.0
        self.key_rgb = (0, 0, 0)
        self.duration = 0.0
        self._loading_frame = False

        self.root = tk.Tk()
        self.root.title("movieAlpha")
        self.root.geometry("980x720")

        self.color_var = tk.StringVar(value=color_text)
        self.threshold_var = tk.DoubleVar(value=threshold)
        self.softness_var = tk.DoubleVar(value=softness)
        self.time_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="「動画を開く」からファイルを選んでください")

        self._build()
        if self.input_path is not None:
            self._open_video()
        else:
            self._show_empty()

    def _build(self) -> None:
        controls = ttk.Frame(self.root, padding=8)
        controls.pack(fill=tk.X)

        ttk.Button(controls, text="動画を開く", command=self._open_file).pack(side=tk.LEFT)
        ttk.Label(controls, text="色").pack(side=tk.LEFT, padx=(12, 4))
        ttk.Entry(controls, textvariable=self.color_var, width=12).pack(side=tk.LEFT)
        ttk.Button(controls, text="自動", command=self._auto_color).pack(side=tk.LEFT, padx=4)
        ttk.Label(controls, text="しきい値").pack(side=tk.LEFT, padx=(12, 4))
        self.threshold_scale = ttk.Scale(
            controls,
            from_=0.0,
            to=0.5,
            variable=self.threshold_var,
            command=lambda _v: self._update_status_text(),
            length=140,
        )
        self.threshold_scale.pack(side=tk.LEFT)
        ttk.Label(controls, text="半透明幅").pack(side=tk.LEFT, padx=(12, 4))
        self.softness_scale = ttk.Scale(
            controls,
            from_=0.0,
            to=0.5,
            variable=self.softness_var,
            command=lambda _v: self._update_status_text(),
            length=140,
        )
        self.softness_scale.pack(side=tk.LEFT)
        ttk.Button(controls, text="書き出す", command=self._export).pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self.root, background="#222222", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.canvas.bind("<Button-1>", self._pick_color)
        self.canvas.bind("<Configure>", lambda _e: self._on_canvas_configure())

        seek_row = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        seek_row.pack(fill=tk.X)
        ttk.Label(seek_row, text="位置").pack(side=tk.LEFT)
        self.seek_scale = ttk.Scale(
            seek_row,
            from_=0.0,
            to=1.0,
            variable=self.time_var,
            command=self._on_seek,
            state=tk.DISABLED,
        )
        self.seek_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.time_label = ttk.Label(seek_row, text="0:00.00 / 0:00.00", width=18)
        self.time_label.pack(side=tk.RIGHT)

        ttk.Label(self.root, textvariable=self.status_var, padding=8).pack(fill=tk.X)
        self._bind_scale_commit(self.threshold_scale, self._refresh_preview)
        self._bind_scale_commit(self.softness_scale, self._refresh_preview)
        self._bind_scale_commit(self.seek_scale, self._commit_seek)

    def _open_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="動画を選択",
            filetypes=[("動画", "*.mp4 *.mov *.webm *.mkv *.avi"), ("すべて", "*.*")],
        )
        if not chosen:
            return
        self.input_path = Path(chosen)
        self._open_video()

    def _show_empty(self) -> None:
        self.duration = 0.0
        self._loading_frame = True
        try:
            self.time_var.set(0.0)
            self.seek_scale.configure(to=1.0, state=tk.DISABLED)
        finally:
            self._loading_frame = False
        self.time_label.configure(text="0:00.00 / 0:00.00")
        self.canvas.delete("all")
        self.preview_photo = None
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_text(
            width // 2,
            height // 2,
            fill="#cccccc",
            font=("Yu Gothic UI", 16),
            text="「動画を開く」から MP4 を選んでください",
        )

    def _on_canvas_configure(self) -> None:
        if self.frame_image is None:
            self._show_empty()
            return
        self._refresh_preview()

    def _max_seek(self) -> float:
        return max(0.0, self.duration - 0.04) if self.duration > 0.04 else max(0.0, self.duration)

    def _bind_scale_commit(self, scale: ttk.Scale, on_commit) -> None:
        def _on_press(_event):
            bind_id = {"id": None}

            def _on_release(_event2):
                ident = bind_id["id"]
                if ident is not None:
                    self.root.unbind("<ButtonRelease-1>", ident)
                    bind_id["id"] = None
                on_commit()

            bind_id["id"] = self.root.bind("<ButtonRelease-1>", _on_release, add="+")

        scale.bind("<ButtonPress-1>", _on_press)
        scale.bind("<KeyRelease>", lambda _e: on_commit())

    def _update_time_label(self) -> None:
        self.time_label.configure(
            text=f"{format_timecode(self.time_var.get())} / {format_timecode(self.duration)}"
        )

    def _on_seek(self, _value: str) -> None:
        self._update_time_label()
        self._update_status_text()

    def _commit_seek(self) -> None:
        if self.input_path is None or self._loading_frame:
            return
        self._extract_current_frame(reset_color=False)

    def _update_status_text(self) -> None:
        if self.input_path is None or self.frame_image is None:
            return
        self.status_var.set(
            f"{self.input_path.name}  {format_timecode(self.time_var.get())}  "
            f"color={to_hex(self.key_rgb)}  "
            f"threshold={self.threshold_var.get():.3f}  softness={self.softness_var.get():.3f}"
        )

    def _open_video(self) -> None:
        if self.input_path is None:
            self._show_empty()
            return
        try:
            self.duration = media_duration(self.input_path)
        except Exception as exc:
            messagebox.showerror("エラー", str(exc))
            return
        self._loading_frame = True
        try:
            self.time_var.set(0.0)
            self.seek_scale.configure(to=max(self._max_seek(), 0.001), state=tk.NORMAL)
            self._update_time_label()
        finally:
            self._loading_frame = False
        self._extract_current_frame(reset_color=True)

    def _extract_current_frame(self, reset_color: bool) -> None:
        if self.input_path is None:
            self._show_empty()
            return
        time_sec = min(max(0.0, float(self.time_var.get())), self._max_seek())
        self._loading_frame = True
        try:
            with tempfile.TemporaryDirectory(prefix="moviealpha-gui-") as temp_dir:
                self.frame_image = extract_frame(
                    self.input_path,
                    Path(temp_dir) / "frame.png",
                    time_sec,
                )
            if reset_color:
                try:
                    self.key_rgb = resolve_key_color(self.color_var.get(), self.frame_image)
                except ValueError:
                    self.key_rgb = resolve_key_color("auto", self.frame_image)
                self.color_var.set(to_hex(self.key_rgb))
            self._refresh_preview()
        except Exception as exc:
            messagebox.showerror("エラー", str(exc))
        finally:
            self._loading_frame = False

    def _auto_color(self) -> None:
        if self.frame_image is None:
            return
        self.key_rgb = resolve_key_color("auto", self.frame_image)
        self.color_var.set(to_hex(self.key_rgb))
        self._refresh_preview()

    def _pick_color(self, event: tk.Event) -> None:
        if self.frame_image is None or self.display_scale <= 0:
            return
        x = int(event.x / self.display_scale)
        y = int(event.y / self.display_scale)
        width, height = self.frame_image.size
        if not (0 <= x < width and 0 <= y < height):
            return
        pixel = self.frame_image.getpixel((x, y))
        self.key_rgb = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
        self.color_var.set(to_hex(self.key_rgb))
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self.frame_image is None:
            return
        try:
            self.key_rgb = parse_color(self.color_var.get())
        except ValueError:
            return
        canvas_w = max(self.canvas.winfo_width(), 320)
        canvas_h = max(self.canvas.winfo_height(), 240)
        scale = min(canvas_w / self.frame_image.width, canvas_h / self.frame_image.height, 1.0)
        work_w = max(1, int(self.frame_image.width * scale))
        work_h = max(1, int(self.frame_image.height * scale))
        work = self.frame_image.resize((work_w, work_h), Image.Resampling.BILINEAR)
        preview = composite_preview(
            work,
            self.key_rgb,
            float(self.threshold_var.get()),
            float(self.softness_var.get()),
        )
        self.display_scale = scale
        shown = preview
        self.preview_photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_photo)
        self._update_status_text()

    def _export(self) -> None:
        if self.input_path is None or self.frame_image is None:
            messagebox.showinfo("動画がありません", "先に「動画を開く」でファイルを選んでください。")
            return
        try:
            color_rgb = parse_color(self.color_var.get())
            suggested = default_output_path(self.input_path, self.fmt)
            dest = filedialog.asksaveasfilename(
                title="透過動画を保存",
                defaultextension=f".{self.fmt}",
                initialfile=suggested.name,
                filetypes=[("WebM", "*.webm"), ("MOV", "*.mov")],
            )
            if not dest:
                return
            output_path = Path(dest)
            fmt = output_path.suffix.lstrip(".").lower() or self.fmt
            encode_alpha_video(
                self.input_path,
                output_path,
                color_rgb,
                float(self.threshold_var.get()),
                float(self.softness_var.get()),
                self.method,
                fmt,
            )
            messagebox.showinfo("完了", f"書き出しました:\n{output_path}")
        except Exception as exc:
            messagebox.showerror("エラー", str(exc))

    def run(self) -> None:
        self.root.mainloop()


def run_gui(
    input_path: Path | None,
    color_text: str,
    threshold: float,
    softness: float,
    method: str,
    fmt: str,
) -> None:
    ColorKeyWindow(input_path, color_text, threshold, softness, method, fmt).run()
