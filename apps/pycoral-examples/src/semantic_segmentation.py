"""Semantic segmentation using PyCoral on Edge TPU.

Usage:
    python3 semantic_segmentation.py \
        --model deeplabv3_mnv2_pascal_quant_edgetpu.tflite \
        --input bird.bmp \
        --output segmentation_result.jpg
"""

import argparse
import time

import cv2
import numpy as np
from PIL import Image

from pycoral.adapters import common
from pycoral.adapters import segment
from pycoral.utils.edgetpu import make_interpreter


def create_pascal_label_colormap():
    """Creates the PASCAL VOC segmentation colormap."""
    colormap = np.zeros((256, 3), dtype=np.uint8)
    indices = np.arange(256, dtype=int)

    for shift in reversed(range(8)):
        for channel in range(3):
            colormap[:, channel] |= (((indices >> channel) & 1) << shift).astype(np.uint8)
        indices >>= 3

    return colormap


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--model', required=True,
                        help='Path of the segmentation model.')
    parser.add_argument('-i', '--input', required=True,
                        help='File path of the input image.')
    parser.add_argument('-o', '--output', help='File path of the output image.')
    parser.add_argument('--keep_aspect_ratio', action='store_true',
                        default=False,
                        help='Keep aspect ratio when resizing input image.')
    parser.add_argument('--display', action='store_true',
                        help='Display result image via OpenCV window')
    args = parser.parse_args()

    interpreter = make_interpreter(args.model, device=':0')
    interpreter.allocate_tensors()
    width, height = common.input_size(interpreter)

    img = Image.open(args.input)
    if args.keep_aspect_ratio:
        resized_img, _ = common.set_resized_input(
            interpreter, img.size,
            lambda size: img.resize(size, Image.LANCZOS))
    else:
        resized_img = img.resize((width, height), Image.LANCZOS)
        common.set_input(interpreter, resized_img)

    # 1st inference (includes model load to Edge TPU)
    start = time.perf_counter()
    interpreter.invoke()
    first_time = (time.perf_counter() - start) * 1000

    # 2nd inference (pure inference time)
    start = time.perf_counter()
    interpreter.invoke()
    second_time = (time.perf_counter() - start) * 1000

    result = segment.get_output(interpreter)
    if len(result.shape) == 3:
        result = np.argmax(result, axis=-1)

    new_width, new_height = resized_img.size
    result = result[:new_height, :new_width]

    colormap = create_pascal_label_colormap()
    mask = colormap[result]

    print('----INFERENCE TIME----')
    print(f'1st inference (includes model load): {first_time:.2f} ms')
    print(f'2nd inference: {second_time:.2f} ms')

    # Build side-by-side result: original | mask
    resized_bgr = cv2.cvtColor(np.array(resized_img.convert('RGB')),
                                cv2.COLOR_RGB2BGR)
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_RGB2BGR)
    output_image = np.hstack([resized_bgr, mask_bgr])

    if args.output:
        cv2.imwrite(args.output, output_image)
        print(f'Result saved to {args.output}')

    if args.display:
        import os
        os.environ['DISPLAY'] = ':0'
        cv2.imshow('semantic_segmentation', output_image)
        cv2.waitKey(5000)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
