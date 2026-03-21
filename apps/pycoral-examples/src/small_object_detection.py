"""Tile-based small object detection with NMS using PyCoral on Edge TPU.

Usage:
    python3 small_object_detection.py \
        --model ssd_mobilenet_v2_coco_quant_no_nms_edgetpu.tflite \
        --labels coco_labels.txt \
        --input kite_and_cold.jpg \
        --tile_sizes 1352x900,500x500,250x250 \
        --output small_object_result.jpg
"""

import argparse
import collections
import time

import cv2
import numpy as np
from PIL import Image

from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter

Object = collections.namedtuple('Object', ['label', 'score', 'bbox'])


def tiles_location_gen(img_size, tile_size, overlap):
    """Generates tile coordinates for the given image."""
    tile_width, tile_height = tile_size
    img_width, img_height = img_size
    h_stride = tile_height - overlap
    w_stride = tile_width - overlap
    for h in range(0, img_height, h_stride):
        for w in range(0, img_width, w_stride):
            xmin = w
            ymin = h
            xmax = min(img_width, w + tile_width)
            ymax = min(img_height, h + tile_height)
            yield [xmin, ymin, xmax, ymax]


def non_max_suppression(objects, threshold):
    """Returns indexes of objects that pass NMS."""
    if len(objects) <= 1:
        return list(range(len(objects)))

    boxes = np.array([o.bbox for o in objects])
    xmins = boxes[:, 0]
    ymins = boxes[:, 1]
    xmaxs = boxes[:, 2]
    ymaxs = boxes[:, 3]

    areas = (xmaxs - xmins) * (ymaxs - ymins)
    scores = [o.score for o in objects]
    idxs = np.argsort(scores)

    selected_idxs = []
    while idxs.size != 0:
        selected_idx = idxs[-1]
        selected_idxs.append(selected_idx)

        overlapped_xmins = np.maximum(xmins[selected_idx], xmins[idxs[:-1]])
        overlapped_ymins = np.maximum(ymins[selected_idx], ymins[idxs[:-1]])
        overlapped_xmaxs = np.minimum(xmaxs[selected_idx], xmaxs[idxs[:-1]])
        overlapped_ymaxs = np.minimum(ymaxs[selected_idx], ymaxs[idxs[:-1]])

        w = np.maximum(0, overlapped_xmaxs - overlapped_xmins)
        h = np.maximum(0, overlapped_ymaxs - overlapped_ymins)

        intersections = w * h
        unions = areas[idxs[:-1]] + areas[selected_idx] - intersections
        ious = intersections / unions

        idxs = np.delete(
            idxs,
            np.concatenate(([len(idxs) - 1], np.where(ious > threshold)[0])))

    return selected_idxs


def draw_objects(image, objects):
    """Draws detected objects on an OpenCV image."""
    for obj in objects:
        x1, y1, x2, y2 = obj.bbox
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        text = f'{obj.label} {obj.score:.2f}'
        cv2.putText(image, text, (x1 + 4, y2 + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--model', required=True,
                        help='Detection SSD model path')
    parser.add_argument('-l', '--labels', help='Labels file path')
    parser.add_argument('-i', '--input', required=True,
                        help='Input image path')
    parser.add_argument('--score_threshold', type=float, default=0.5,
                        help='Score threshold for candidates')
    parser.add_argument('--tile_sizes', required=True,
                        help='Tile sizes as widthxheight,... '
                             '(e.g. "1352x900,500x500,250x250")')
    parser.add_argument('--tile_overlap', type=int, default=50,
                        help='Pixels to overlap tiles')
    parser.add_argument('--iou_threshold', type=float, default=0.1,
                        help='IoU threshold for NMS')
    parser.add_argument('-o', '--output', help='Output image path')
    parser.add_argument('--display', action='store_true',
                        help='Display result image via OpenCV window')
    args = parser.parse_args()

    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()
    labels = read_label_file(args.labels) if args.labels else {}

    img = Image.open(args.input).convert('RGB')
    img_size = img.size

    tile_sizes = [
        tuple(map(int, ts.split('x')))
        for ts in args.tile_sizes.split(',')
    ]

    start = time.perf_counter()

    objects_by_label = {}
    for tile_size in tile_sizes:
        for tile_location in tiles_location_gen(img_size, tile_size,
                                                args.tile_overlap):
            tile = img.crop(tile_location)
            _, scale = common.set_resized_input(
                interpreter, tile.size,
                lambda size, t=tile: t.resize(size, Image.NEAREST))
            interpreter.invoke()
            objs = detect.get_objects(interpreter, args.score_threshold, scale)

            for obj in objs:
                bbox = [obj.bbox.xmin, obj.bbox.ymin,
                        obj.bbox.xmax, obj.bbox.ymax]
                bbox[0] += tile_location[0]
                bbox[1] += tile_location[1]
                bbox[2] += tile_location[0]
                bbox[3] += tile_location[1]

                label = labels.get(obj.id, '')
                objects_by_label.setdefault(label, []).append(
                    Object(label, obj.score, bbox))

    total_time = (time.perf_counter() - start) * 1000

    # Apply NMS per label
    all_objects = []
    for label, objects in objects_by_label.items():
        idxs = non_max_suppression(objects, args.iou_threshold)
        for idx in idxs:
            all_objects.append(objects[idx])

    print('----INFERENCE TIME----')
    print(f'Total detection time: {total_time:.2f} ms')
    print('-------RESULTS--------')
    print(f'Detected {len(all_objects)} objects')
    for obj in all_objects:
        print(f'  {obj.label}: {obj.score:.2f} bbox={obj.bbox}')

    result = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    draw_objects(result, all_objects)

    if args.output:
        cv2.imwrite(args.output, result)
        print(f'Result saved to {args.output}')

    if args.display:
        import os
        os.environ['DISPLAY'] = ':0'
        cv2.imshow('small_object_detection', result)
        cv2.waitKey(5000)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
