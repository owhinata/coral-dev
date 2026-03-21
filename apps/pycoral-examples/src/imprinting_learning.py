"""Transfer learning via weight imprinting on Edge TPU.

Usage:
    python3 imprinting_learning.py \
        --model_path mobilenet_v1_1.0_224_l2norm_quant_edgetpu.tflite \
        --data open_image_v4_subset \
        --output retrained_imprinting.tflite
"""

import argparse
import os
import time

import numpy as np
from PIL import Image

from pycoral.adapters import classify
from pycoral.adapters import common
from pycoral.learn.imprinting.engine import ImprintingEngine
from pycoral.utils.edgetpu import make_interpreter


def read_data(path, test_ratio):
    """Splits dataset into train/test sets."""
    train_set = {}
    test_set = {}
    for category in sorted(os.listdir(path)):
        category_dir = os.path.join(path, category)
        if os.path.isdir(category_dir):
            images = [
                f for f in os.listdir(category_dir)
                if os.path.isfile(os.path.join(category_dir, f))
            ]
            if images:
                k = max(int(test_ratio * len(images)), 1)
                test_set[category] = images[:k]
                train_set[category] = images[k:]
    return train_set, test_set


def prepare_images(image_list, directory, shape):
    """Reads and resizes images to numpy arrays."""
    ret = []
    for filename in image_list:
        with Image.open(os.path.join(directory, filename)) as img:
            img = img.convert('RGB').resize(shape, Image.NEAREST)
            ret.append(np.asarray(img))
    return np.array(ret)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--model_path', required=True,
                        help='Path to the model.')
    parser.add_argument('--data', required=True,
                        help='Path to training data directory.')
    parser.add_argument('--output',
                        help='Output path for retrained model.')
    parser.add_argument('--test_ratio', type=float, default=0.25,
                        help='Ratio of data used for testing.')
    parser.add_argument('--keep_classes', action='store_true',
                        help='Whether to keep base model classes.')
    args = parser.parse_args()

    if not args.output:
        model_name = os.path.basename(args.model_path)
        args.output = model_name.replace('.tflite', '_retrained.tflite')

    print(f'Output path: {args.output}')
    print(f'Test ratio: {args.test_ratio:.0%}')

    t0 = time.perf_counter()

    engine = ImprintingEngine(args.model_path, keep_classes=args.keep_classes)
    extractor = make_interpreter(
        engine.serialize_extractor_model(), device=':0')
    extractor.allocate_tensors()
    shape = common.input_size(extractor)

    print(f'Dataset path: {args.data}')
    train_set, test_set = read_data(args.data, args.test_ratio)
    print(f'Image list parsed. Category Num = {len(train_set)}')

    print('Processing training data...')
    train_input = []
    labels_map = {}
    for class_id, (category, image_list) in enumerate(train_set.items()):
        print(f'  Processing category: {category}')
        train_input.append(
            prepare_images(image_list, os.path.join(args.data, category),
                           shape))
        labels_map[class_id] = category

    print('Training...')
    num_classes = engine.num_classes
    for class_id, tensors in enumerate(train_input):
        for tensor in tensors:
            common.set_input(extractor, tensor)
            extractor.invoke()
            embedding = classify.get_scores(extractor)
            engine.train(embedding, class_id=num_classes + class_id)

    t1 = time.perf_counter()
    print(f'Training time: {(t1 - t0) * 1000:.2f} ms')

    with open(args.output, 'wb') as f:
        f.write(engine.serialize_model())
    print(f'Model saved as: {args.output}')

    label_file = args.output.replace('.tflite', '.txt')
    with open(label_file, 'w') as f:
        for label_id, label in labels_map.items():
            f.write(f'{label_id}  {label}\n')
    print(f'Labels file saved as: {label_file}')

    print('Evaluating...')
    interpreter = make_interpreter(args.output)
    interpreter.allocate_tensors()
    size = common.input_size(interpreter)

    top_k = 5
    correct = [0] * top_k
    wrong = [0] * top_k
    for category, image_list in test_set.items():
        for img_name in image_list:
            img = Image.open(os.path.join(args.data, category, img_name))
            img = img.resize(size, Image.NEAREST)
            common.set_input(interpreter, img)
            interpreter.invoke()
            candidates = classify.get_classes(
                interpreter, top_k, score_threshold=0.1)
            recognized = False
            for i in range(top_k):
                if i < len(candidates) and \
                        labels_map.get(candidates[i].id) == category:
                    recognized = True
                if recognized:
                    correct[i] += 1
                else:
                    wrong[i] += 1

    print('-------RESULTS--------')
    for i in range(top_k):
        total = correct[i] + wrong[i]
        if total > 0:
            print(f'Top {i + 1}: {correct[i] / total:.0%}')


if __name__ == '__main__':
    main()
