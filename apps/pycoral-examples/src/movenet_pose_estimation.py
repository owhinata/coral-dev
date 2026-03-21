"""Pose estimation using MoveNet on Edge TPU via PyCoral.

Usage:
    python3 movenet_pose_estimation.py \
        --model movenet_single_pose_lightning_ptq_edgetpu.tflite \
        --input squat.bmp \
        --output pose_result.jpg
"""

import argparse
import time

import cv2
import numpy as np
from PIL import Image
from pycoral.adapters import common
from pycoral.utils.edgetpu import make_interpreter

_NUM_KEYPOINTS = 17

# COCO keypoint connections for skeleton drawing
_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),       # head
    (5, 6),                                  # shoulders
    (5, 7), (7, 9), (6, 8), (8, 10),        # arms
    (5, 11), (6, 12),                        # torso
    (11, 12),                                # hips
    (11, 13), (13, 15), (12, 14), (14, 16),  # legs
]

_KEYPOINT_NAMES = [
    'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
    'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
    'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
    'left_knee', 'right_knee', 'left_ankle', 'right_ankle',
]


def draw_pose(image, pose, threshold=0.2):
    """Draws keypoints and skeleton on an OpenCV image."""
    h, w = image.shape[:2]

    # Draw skeleton
    for i, j in _SKELETON:
        if pose[i][2] > threshold and pose[j][2] > threshold:
            y1, x1 = int(pose[i][0] * h), int(pose[i][1] * w)
            y2, x2 = int(pose[j][0] * h), int(pose[j][1] * w)
            cv2.line(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Draw keypoints
    for i in range(_NUM_KEYPOINTS):
        if pose[i][2] > threshold:
            y, x = int(pose[i][0] * h), int(pose[i][1] * w)
            cv2.circle(image, (x, y), 4, (0, 0, 255), -1)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--model', required=True,
                        help='File path of .tflite file.')
    parser.add_argument('-i', '--input', required=True,
                        help='Image for pose estimation.')
    parser.add_argument('-o', '--output', help='File path for the result image')
    parser.add_argument('--display', action='store_true',
                        help='Display result image via OpenCV window')
    args = parser.parse_args()

    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    img = Image.open(args.input)
    resized_img = img.resize(common.input_size(interpreter), Image.LANCZOS)
    common.set_input(interpreter, resized_img)

    # 1st inference (includes model load to Edge TPU)
    start = time.perf_counter()
    interpreter.invoke()
    first_time = (time.perf_counter() - start) * 1000

    # 2nd inference (pure inference time)
    common.set_input(interpreter, resized_img)
    start = time.perf_counter()
    interpreter.invoke()
    second_time = (time.perf_counter() - start) * 1000

    pose = common.output_tensor(interpreter, 0).copy().reshape(
        _NUM_KEYPOINTS, 3)

    print('----INFERENCE TIME----')
    print(f'1st inference (includes model load): {first_time:.2f} ms')
    print(f'2nd inference: {second_time:.2f} ms')
    print('-------RESULTS--------')
    for i, name in enumerate(_KEYPOINT_NAMES):
        y, x, score = pose[i]
        print(f'{name:>16s}: ({x:.3f}, {y:.3f}) score={score:.3f}')

    result = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
    draw_pose(result, pose)

    if args.output:
        cv2.imwrite(args.output, result)
        print(f'Result saved to {args.output}')

    if args.display:
        import os
        os.environ['DISPLAY'] = ':0'
        cv2.imshow('movenet_pose_estimation', result)
        cv2.waitKey(5000)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
