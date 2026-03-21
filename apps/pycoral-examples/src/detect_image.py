"""Object detection using PyCoral on Edge TPU.

Usage:
    python3 detect_image.py \
        --model ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite \
        --labels coco_labels.txt \
        --input grace_hopper.bmp \
        --output detection_result.jpg
"""

import argparse
import time

import cv2
import numpy as np
from PIL import Image

from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter


def draw_objects(image, objs, labels):
    """Draws bounding boxes and labels on an OpenCV image."""
    for obj in objs:
        bbox = obj.bbox
        cv2.rectangle(image, (bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax),
                      (0, 0, 255), 2)
        text = f'{labels.get(obj.id, obj.id)} {obj.score:.2f}'
        cv2.putText(image, text, (bbox.xmin + 4, bbox.ymin + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--model', required=True,
                        help='File path of .tflite file')
    parser.add_argument('-i', '--input', required=True,
                        help='File path of image to process')
    parser.add_argument('-l', '--labels', help='File path of labels file')
    parser.add_argument('-t', '--threshold', type=float, default=0.4,
                        help='Score threshold for detected objects')
    parser.add_argument('-o', '--output', help='File path for the result image')
    parser.add_argument('--display', action='store_true',
                        help='Display result image via OpenCV window')
    args = parser.parse_args()

    labels = read_label_file(args.labels) if args.labels else {}

    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    image = Image.open(args.input)
    _, scale = common.set_resized_input(
        interpreter, image.size,
        lambda size: image.resize(size, Image.LANCZOS))

    # 1st inference (includes model load to Edge TPU)
    start = time.perf_counter()
    interpreter.invoke()
    first_time = (time.perf_counter() - start) * 1000

    # 2nd inference (pure inference time)
    start = time.perf_counter()
    interpreter.invoke()
    second_time = (time.perf_counter() - start) * 1000

    objs = detect.get_objects(interpreter, args.threshold, scale)

    print('----INFERENCE TIME----')
    print(f'1st inference (includes model load): {first_time:.2f} ms')
    print(f'2nd inference: {second_time:.2f} ms')
    print('-------RESULTS--------')
    if not objs:
        print('No objects detected')
    for obj in objs:
        print(f'{labels.get(obj.id, obj.id)}')
        print(f'  id:    {obj.id}')
        print(f'  score: {obj.score}')
        print(f'  bbox:  {obj.bbox}')

    result = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    draw_objects(result, objs, labels)

    if args.output:
        cv2.imwrite(args.output, result)
        print(f'Result saved to {args.output}')

    if args.display:
        import os
        os.environ['DISPLAY'] = ':0'
        cv2.imshow('detect_image', result)
        cv2.waitKey(5000)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
