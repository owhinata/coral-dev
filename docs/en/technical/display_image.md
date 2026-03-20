# Displaying Images

This page describes how to display images on the Coral Dev Board's HDMI output.
Four methods — GStreamer, ImageMagick, OpenCV, and Pillow — were tested on the actual board,
and all formats (BMP, JPG, PNG, WebP) were confirmed to work with each method.

## Display Environment

The display stack on Coral Dev Board (Mendel Linux) is configured as follows:

- **Weston** (Wayland compositor) runs by default
- **XWayland** is enabled — X11 applications work out of the box
- `/dev/fb0` exists but the i.MX 8M uses DRM/KMS, so direct framebuffer access requires stopping Weston

## Method 1: GStreamer (Recommended)

Displays the image as a Wayland window. No need to stop Weston.

### Installation

```bash
sudo apt-get install gstreamer1.0-tools
```

### Command

```bash
WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
  gst-launch-1.0 filesrc location=<file> ! decodebin ! videoconvert ! imagefreeze ! waylandsink
```

`decodebin` automatically detects the format and decodes it, so the same command works for BMP, JPG, PNG, and WebP.

!!! note "Screen not refreshing after exit"
    The screen may not update after GStreamer exits.
    Run `sudo systemctl restart weston` to recover.

## Method 2: ImageMagick

Displays via XWayland. No need to stop Weston.
Provides GUI controls (zoom, rotate, color adjustment, etc.) with the shortest command.

### Installation

```bash
sudo apt-get install imagemagick
```

### Command

```bash
DISPLAY=:0 display <file>
```

## Method 3: OpenCV (python3-opencv)

Displays via XWayland. No need to stop Weston.
Useful for combining inference result rendering (rectangles, text, etc.) and display in a single library.

### Installation

```bash
sudo apt-get install python3-opencv
```

!!! warning "pip install not supported"
    `pip install opencv-python-headless` fails due to numpy build errors.
    Always install via apt.

### Code Example

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

## Method 4: Pillow + GStreamer

Load the image with Pillow, convert to raw bytes, and pipe into GStreamer's `rawvideoparse`.
Pillow is pre-installed so no additional installation is required, but GStreamer is needed.

Since GStreamer's `decodebin` can do the same thing on its own,
this method is **only useful when you need Python-based image processing before display**.

## Comparison

| Method | Package | Stop Weston | Notes |
|--------|---------|:-----------:|-------|
| GStreamer | `gstreamer1.0-tools` | No | CLI-only, flexible pipelines |
| ImageMagick | `imagemagick` | No | GUI controls, shortest command |
| OpenCV | `python3-opencv` (apt) | No | Easy to integrate into Python inference pipelines |
| Pillow + GStreamer | `gstreamer1.0-tools` | No | Display after Python image processing |

## Supported Formats

All tools were verified on the actual board with BMP / JPG / PNG / WebP.
