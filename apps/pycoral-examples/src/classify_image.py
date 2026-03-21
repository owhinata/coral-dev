"""Image classification using PyCoral on Edge TPU.

Usage:
    python3 classify_image.py \
        --model mobilenet_v2_1.0_224_inat_bird_quant_edgetpu.tflite \
        --labels inat_bird_labels.txt \
        --input parrot.jpg
"""

import argparse
import time

import numpy as np
from PIL import Image
from pycoral.adapters import classify
from pycoral.adapters import common
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--model', required=True,
                        help='File path of .tflite file.')
    parser.add_argument('-i', '--input', required=True,
                        help='Image to be classified.')
    parser.add_argument('-l', '--labels', help='File path of labels file.')
    parser.add_argument('-k', '--top_k', type=int, default=3,
                        help='Max number of classification results')
    parser.add_argument('-t', '--threshold', type=float, default=0.0,
                        help='Classification score threshold')
    args = parser.parse_args()

    labels = read_label_file(args.labels) if args.labels else {}

    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    if common.input_details(interpreter, 'dtype') != np.uint8:
        raise ValueError('Only support uint8 input type.')

    size = common.input_size(interpreter)
    image = Image.open(args.input).convert('RGB').resize(size, Image.LANCZOS)

    params = common.input_details(interpreter, 'quantization_parameters')
    scale = params['scales']
    zero_point = params['zero_points']
    if abs(scale * 128.0 - 1) < 1e-5 and abs(128.0 - zero_point) < 1e-5:
        common.set_input(interpreter, image)
    else:
        normalized = (np.asarray(image) - 128.0) / (128.0 * scale) + zero_point
        np.clip(normalized, 0, 255, out=normalized)
        common.set_input(interpreter, normalized.astype(np.uint8))

    # 1st inference (includes model load to Edge TPU)
    start = time.perf_counter()
    interpreter.invoke()
    first_time = (time.perf_counter() - start) * 1000

    # 2nd inference (pure inference time)
    start = time.perf_counter()
    interpreter.invoke()
    second_time = (time.perf_counter() - start) * 1000

    classes = classify.get_classes(interpreter, args.top_k, args.threshold)

    print('----INFERENCE TIME----')
    print(f'1st inference (includes model load): {first_time:.2f} ms')
    print(f'2nd inference: {second_time:.2f} ms')
    print('-------RESULTS--------')
    for c in classes:
        print(f'{labels.get(c.id, c.id)}: {c.score:.5f}')


if __name__ == '__main__':
    main()
