# 画像の表示

Coral Dev Board の HDMI 出力に画像を表示する方法をまとめます。
GStreamer / ImageMagick / OpenCV / Pillow の 4 つの方法を実機で検証し、
BMP・JPG・PNG・WebP すべての形式で表示できることを確認しました。

## 表示環境

Coral Dev Board (Mendel Linux) のディスプレイスタックは以下の構成です。

- **Weston** (Wayland コンポジタ) がデフォルトで動作
- **XWayland** が有効 → X11 アプリもそのまま動作可能
- `/dev/fb0` は存在するが、i.MX 8M は DRM/KMS ベースのため直接書き込みには Weston の停止が必要

## 方法 1: GStreamer（推奨）

Wayland ウィンドウとして表示します。Weston の停止は不要です。

### インストール

```bash
sudo apt-get install gstreamer1.0-tools
```

### コマンド

```bash
WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
  gst-launch-1.0 filesrc location=<file> ! decodebin ! videoconvert ! imagefreeze ! waylandsink
```

`decodebin` が形式を自動判別してデコードするため、BMP・JPG・PNG・WebP いずれも同じコマンドで表示できます。

!!! note "画面が再描画されない場合"
    GStreamer の停止後に画面が更新されないことがあります。
    その場合は `sudo systemctl restart weston` で復旧できます。

## 方法 2: ImageMagick

XWayland 経由で表示します。Weston の停止は不要です。
GUI 操作（ズーム・回転・色調整等）が可能で、コマンドも最短です。

### インストール

```bash
sudo apt-get install imagemagick
```

### コマンド

```bash
DISPLAY=:0 display -geometry +0+0 <file>
```

`-geometry +0+0` を指定しないとウィンドウが画面下部に配置され、画像が見切れることがあります。

## 方法 3: OpenCV (python3-opencv)

XWayland 経由で表示します。Weston の停止は不要です。
推論結果の描画（矩形・テキスト等）と表示を一つのライブラリで完結できます。

### インストール

```bash
sudo apt-get install python3-opencv
```

!!! warning "pip install は使用不可"
    `pip install opencv-python-headless` は numpy のビルドに失敗するため使用できません。
    必ず apt でインストールしてください。

### コード例

```python
import cv2
import os

os.environ["WAYLAND_DISPLAY"] = "wayland-0"
os.environ["XDG_RUNTIME_DIR"] = "/run/user/1000"

img = cv2.imread("<file>")
cv2.imshow("viewer", img)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

## 方法 4: Pillow + GStreamer

Pillow で画像を読み込み、raw bytes に変換して GStreamer の `rawvideoparse` にパイプする方法です。
Pillow はプリインストール済みのため追加インストールは不要ですが、GStreamer は必要です。

GStreamer 単体の `decodebin` で同等のことができるため、
**表示前に Python で画像処理が必要な場合**にのみ有用です。

## 比較

| 方法 | パッケージ | Weston 停止 | 特徴 |
|------|-----------|:-----------:|------|
| GStreamer | `gstreamer1.0-tools` | 不要 | CLI で完結、パイプラインで柔軟 |
| ImageMagick | `imagemagick` | 不要 | GUI 操作可能、コマンド最短 |
| OpenCV | `python3-opencv` (apt) | 不要 | Python 推論パイプラインに統合しやすい |
| Pillow + GStreamer | `gstreamer1.0-tools` | 不要 | Python 画像処理後に表示 |

## 対応フォーマット

全ツールで BMP / JPG / PNG / WebP の表示を実機検証済みです。
