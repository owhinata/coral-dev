"""Real-time face detection + ESPCN super-resolution on Coral Dev Board.

Detects faces via Edge TPU, sharpens each face region with CPU-based ESPCN
super-resolution (3x), and overlays the result on a live camera feed.

Usage:
    python3 face_sharp.py \
        --model ssd_mobilenet_v2_face_quant_postprocess_edgetpu.tflite \
        --sr_model espcn_x3.tflite \
        --threshold 0.5
"""

import argparse
import datetime
import os
import sys
import termios
import threading
import time
import tty

import gi
import numpy as np
from PIL import Image, ImageDraw

from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.edgetpu import make_interpreter
from tflite_runtime.interpreter import Interpreter

gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import GLib, Gst

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30


def super_resolve(crop_image, sr_interpreter, alpha=1.5):
    """Sharpen a face crop via ESPCN Y-channel detail transfer.

    Extracts high-frequency Y detail (ESPCN - bicubic), resizes to
    original crop size, and adds it to the original Y channel.
    The original image is preserved; only learned detail is added.
    """
    input_details = sr_interpreter.get_input_details()[0]
    output_details = sr_interpreter.get_output_details()[0]
    input_h, input_w = input_details['shape'][1], input_details['shape'][2]
    out_h, out_w = output_details['shape'][1], output_details['shape'][2]

    original_size = crop_image.size  # (w, h)

    # Convert to YCbCr
    ycbcr = crop_image.convert('YCbCr')
    ycbcr_np = np.array(ycbcr, dtype=np.float32)

    # Downscale Y to model input size (50x50)
    small_ycbcr = ycbcr.resize((input_w, input_h), Image.BICUBIC)
    y_small = np.array(small_ycbcr)[:, :, 0:1].astype(np.float32) / 255.0

    # ESPCN on Y channel (50x50 -> 150x150)
    input_data = np.expand_dims(y_small, axis=0)
    sr_interpreter.set_tensor(input_details['index'], input_data)
    sr_interpreter.invoke()
    y_sr = sr_interpreter.get_tensor(output_details['index'])[0, :, :, 0]
    y_sr = np.clip(y_sr, 0, 1)

    # Bicubic baseline upscale Y (50x50 -> 150x150)
    y_bicubic = np.array(
        Image.fromarray(np.array(small_ycbcr)[:, :, 0]).resize(
            (out_w, out_h), Image.BICUBIC),
        dtype=np.float32) / 255.0

    # Detail = ESPCN - bicubic (learned high-freq Y components)
    detail_150 = y_sr - y_bicubic

    # Resize detail to original crop size
    detail_image = Image.fromarray(
        np.clip((detail_150 + 0.5) * 255, 0, 255).astype(np.uint8))
    detail_resized = np.array(
        detail_image.resize(original_size, Image.LANCZOS),
        dtype=np.float32) / 255.0 - 0.5

    # Add amplified detail to original Y channel only
    ycbcr_np[:, :, 0] = np.clip(
        ycbcr_np[:, :, 0] + detail_resized * alpha * 255.0, 0, 255)

    return Image.fromarray(ycbcr_np.astype(np.uint8), 'YCbCr').convert('RGB')


def process_frame(frame, det_interpreter, sr_interpreter, threshold,
                   save_dir=None):
    """Detect faces and apply super-resolution to each face region."""
    image = Image.fromarray(frame)
    w, h = image.size

    # Run face detection on Edge TPU
    _, scale = common.set_resized_input(
        det_interpreter, image.size,
        lambda size: image.resize(size, Image.BILINEAR))
    det_interpreter.invoke()
    objs = detect.get_objects(det_interpreter, threshold, scale)

    # Apply super-resolution to each detected face
    for i, obj in enumerate(objs):
        bbox = obj.bbox
        x0 = max(0, bbox.xmin)
        y0 = max(0, bbox.ymin)
        x1 = min(w, bbox.xmax)
        y1 = min(h, bbox.ymax)

        if x1 - x0 < 4 or y1 - y0 < 4:
            continue

        crop = image.crop((x0, y0, x1, y1))
        sharpened = super_resolve(crop, sr_interpreter)

        if save_dir is not None:
            crop.save(os.path.join(save_dir, f'face{i}_before.png'))
            sharpened.save(os.path.join(save_dir, f'face{i}_after.png'))

        image.paste(sharpened, (x0, y0))

    if save_dir is not None and objs:
        image.save(os.path.join(save_dir, 'frame.png'))
        Image.fromarray(frame).save(os.path.join(save_dir, 'frame_original.png'))
        print(f'Saved {len(objs)} face(s) to {save_dir}', flush=True)

    # Draw bounding boxes
    draw = ImageDraw.Draw(image)
    for obj in objs:
        bbox = obj.bbox
        x0 = max(0, bbox.xmin)
        y0 = max(0, bbox.ymin)
        x1 = min(w, bbox.xmax)
        y1 = min(h, bbox.ymax)
        draw.rectangle([x0, y0, x1, y1], outline=(0, 255, 0), width=2)
        draw.text((x0 + 2, y0 + 2), f'{obj.score:.2f}', fill=(0, 255, 0))

    return image


def main():
    parser = argparse.ArgumentParser(
        description='Face detection + super-resolution on Coral Dev Board',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--model',
        default='ssd_mobilenet_v2_face_quant_postprocess_edgetpu.tflite',
        help='Face detection model path (Edge TPU)')
    parser.add_argument(
        '--sr_model',
        default='espcn_x3.tflite',
        help='Super-resolution model path (CPU TFLite)')
    parser.add_argument(
        '--threshold', type=float, default=0.5,
        help='Detection confidence threshold')
    args = parser.parse_args()

    # Resolve model paths relative to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(args.model):
        args.model = os.path.join(script_dir, args.model)
    if not os.path.isabs(args.sr_model):
        args.sr_model = os.path.join(script_dir, args.sr_model)

    # Initialize face detection interpreter (Edge TPU)
    print(f'Loading face detection model: {args.model}')
    det_interpreter = make_interpreter(args.model)
    det_interpreter.allocate_tensors()

    # Warmup Edge TPU
    input_size = common.input_size(det_interpreter)
    dummy = Image.new('RGB', (input_size[0], input_size[1]))
    common.set_resized_input(
        det_interpreter, dummy.size,
        lambda size: dummy.resize(size, Image.LANCZOS))
    det_interpreter.invoke()
    print('  Edge TPU warmup done')

    # Initialize super-resolution interpreter (CPU)
    print(f'Loading super-resolution model: {args.sr_model}')
    sr_interpreter = Interpreter(model_path=args.sr_model, num_threads=3)
    sr_interpreter.allocate_tensors()

    # Warmup CPU model
    sr_input = sr_interpreter.get_input_details()[0]
    sr_dummy = np.random.rand(*sr_input['shape']).astype(np.float32)
    sr_interpreter.set_tensor(sr_input['index'], sr_dummy)
    sr_interpreter.invoke()
    print('  CPU super-resolution warmup done')

    # GStreamer init
    Gst.init(None)

    # Source pipeline: camera -> appsink
    src_pipeline_str = (
        'v4l2src device=/dev/video0 '
        '! video/x-raw,format=YUY2,width={w},height={h},framerate={fps}/1 '
        '! videoconvert '
        '! video/x-raw,format=RGB,width={w},height={h} '
        '! appsink name=sink emit-signals=true max-buffers=1 drop=true'
    ).format(w=CAMERA_WIDTH, h=CAMERA_HEIGHT, fps=CAMERA_FPS)

    # Display pipeline: appsrc -> screen
    display_pipeline_str = (
        'appsrc name=src is-live=true format=time '
        '! video/x-raw,format=RGB,width={w},height={h},framerate={fps}/1 '
        '! videoconvert '
        '! glimagesink sync=false'
    ).format(w=CAMERA_WIDTH, h=CAMERA_HEIGHT, fps=CAMERA_FPS)

    src_pipeline = Gst.parse_launch(src_pipeline_str)
    display_pipeline = Gst.parse_launch(display_pipeline_str)

    appsink = src_pipeline.get_by_name('sink')
    appsrc = display_pipeline.get_by_name('src')

    # Shared state for frame handoff between callback and processing thread
    frame_lock = threading.Lock()
    latest_frame = [None]  # mutable container
    running = [True]
    save_request = [False]  # set True by 's' key

    frame_count = 0
    fps_start = time.monotonic()

    def on_new_sample(sink):
        """Grab frame quickly and hand off to processing thread."""
        sample = sink.emit('pull-sample')
        if sample is None:
            return Gst.FlowReturn.ERROR

        buf = sample.get_buffer()
        caps = sample.get_caps()
        height = caps.get_structure(0).get_value('height')
        width = caps.get_structure(0).get_value('width')

        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.ERROR

        frame = np.frombuffer(mapinfo.data, dtype=np.uint8).reshape(
            height, width, 3).copy()
        buf.unmap(mapinfo)

        with frame_lock:
            latest_frame[0] = frame

        return Gst.FlowReturn.OK

    def process_loop():
        """Processing thread: detect + SR + push to display."""
        nonlocal frame_count, fps_start

        while running[0]:
            # Grab latest frame
            with frame_lock:
                frame = latest_frame[0]
                latest_frame[0] = None

            if frame is None:
                time.sleep(0.001)
                continue

            # Check save request
            save_dir = None
            if save_request[0]:
                save_request[0] = False
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                save_dir = os.path.join(script_dir, f'capture_{ts}')
                os.makedirs(save_dir, exist_ok=True)

            # Process
            result_image = process_frame(
                frame, det_interpreter, sr_interpreter, args.threshold,
                save_dir=save_dir)
            result_array = np.array(result_image)

            # FPS calculation
            frame_count += 1
            elapsed = time.monotonic() - fps_start
            if elapsed >= 2.0:
                fps = frame_count / elapsed
                print(f'FPS: {fps:.1f}', flush=True)
                frame_count = 0
                fps_start = time.monotonic()

            # Push to display pipeline
            data = result_array.tobytes()
            out_buf = Gst.Buffer.new_allocate(None, len(data), None)
            out_buf.fill(0, data)
            out_buf.pts = Gst.CLOCK_TIME_NONE
            out_buf.duration = Gst.CLOCK_TIME_NONE
            appsrc.emit('push-buffer', out_buf)

    appsink.connect('new-sample', on_new_sample)

    # Start processing thread
    proc_thread = threading.Thread(target=process_loop, daemon=True)
    proc_thread.start()

    # Start pipelines
    display_pipeline.set_state(Gst.State.PLAYING)
    src_pipeline.set_state(Gst.State.PLAYING)

    print(f'\nStarted: camera={CAMERA_WIDTH}x{CAMERA_HEIGHT}@{CAMERA_FPS}fps')

    # Monitor stdin for 'q' key if running on a TTY
    old_settings = None
    if sys.stdin.isatty():
        print('Press s to save, q to quit\n')
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

        def on_stdin(channel, condition):
            key = sys.stdin.read(1)
            if key == 'q':
                loop.quit()
                return False
            if key == 's':
                save_request[0] = True
                print('Capture requested...', flush=True)
            return True

        GLib.io_add_watch(sys.stdin, GLib.IO_IN, on_stdin)
    else:
        print('Press Ctrl+C to stop\n')

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        running[0] = False
        proc_thread.join(timeout=2)
        if old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        src_pipeline.set_state(Gst.State.NULL)
        display_pipeline.set_state(Gst.State.NULL)
        print('\nStopped.')


if __name__ == '__main__':
    main()
