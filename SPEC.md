# movieAlpha 仕様

MP4 など不透明動画から、指定した色を透明（アルファ）に置き換える。OBS のメディアソース用オーバーレイを想定した単機能ツール。

## 参考にした実装

| リポジトリ | Stars | 取り入れた点 |
|---|---:|---|
| [obsproject/obs-studio](https://github.com/obsproject/obs-studio) Color Key | 70k+ | `similarity`（しきい値）と `smoothness`（半透明幅）。`alpha = saturate((dist - threshold) / softness)` |
| [FFmpeg colorkey](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_colorkey.c) | — | 同じ式を `similarity` / `blend` としてエンコードに使う |
| [kkroening/ffmpeg-python](https://github.com/kkroening/ffmpeg-python) | 11k+ | FFmpeg フィルタグラフを Python で組み立てる |

実写グリーンバック向けの高度な despill / AI キーイング（CorridorKey 等）は対象外。

## 入出力

- 入力: FFmpeg が読める動画（MP4 / MOV / WebM など）
- 出力: アルファ付きコンテナのみ
  - `webm`（既定）: VP9 + `yuva420p`。OBS で透過再生しやすい
  - `mov`: Animation (`qtrle`) または PNG。編集向け
- MP4 / H.264 はアルファを持てないため出力しない

## キーイング

既定フィルタは FFmpeg `colorkey`（RGB）。単色背景・画面収録・グラフィックに向く。実写クロマキーには `chromakey`（YUV）を選べる。

パラメータ:

- `color`: 透明にする色。`#RRGGBB` / `0xRRGGBB` / 名前 / `auto`（四隅の最多色）
- `threshold`（別名 `similarity`）: 0〜1。キー色からの距離がこれ以下なら完全透明
- `softness`（別名 `smoothness` / `blend`）: 0〜1。しきい値の外側この幅までは半透明。0 なら二値

アルファ計算（[OBS Color Key](https://github.com/obsproject/obs-studio/blob/master/plugins/obs-filters/data/color_key_filter.effect) と [FFmpeg colorkey](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_colorkey.c)）:

1. RGB ユークリッド距離 `d` を 0〜1 に正規化する
2. `d <= threshold` なら alpha = 0（完全透明）
3. `threshold < d < threshold + softness` なら alpha は 0〜1 を線形補間（半透明）
4. `d >= threshold + softness` または `softness = 0` の外側なら alpha = 1（不透明）

## CLI

```text
moviealpha INPUT --color #000000 --threshold 0.08 --softness 0.12 -o OUTPUT.webm
moviealpha INPUT --gui
moviealpha INPUT --preview PREVIEW.png
```

音声は既定で残す（WebM は Opus）。`--no-audio` で落とす。

## GUI

1. フレームをクリックしてキー色を取る
2. しきい値と半透明幅をプレビューで調整する
3. アルファ付き WebM または MOV を書き出す

プレビューは同一距離式の CPU 実装。本番エンコードは FFmpeg。

## 非目標

- 人物切り抜き、AI マッティング
- 複数キー色、マスクペイント
- H.264 MP4 へのアルファ埋め込み
