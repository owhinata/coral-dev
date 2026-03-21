"""Transfer learning via backpropagation of the last layer on Edge TPU.

Usage:
    # Training
    python3 backprop_last_layer.py \
        --embedding_extractor_path \
            mobilenet_v1_1.0_224_quant_embedding_extractor_edgetpu.tflite \
        --data_dir flower_photos \
        --output_dir output

    # Inference test with retrained model
    python3 classify_image.py \
        --model output/retrained_model_edgetpu.tflite \
        --labels output/label_map.txt \
        --input sunflower.bmp
"""

import argparse
import os
import sys
import time

import numpy as np
from PIL import Image

from pycoral.adapters import classify
from pycoral.adapters import common
from pycoral.learn.backprop.softmax_regression import SoftmaxRegression
from pycoral.utils.edgetpu import make_interpreter


def get_image_paths(data_dir):
    """Walks data_dir and returns image paths, labels, and label map."""
    classes = None
    image_paths = []
    labels = []

    class_idx = 0
    for root, dirs, files in os.walk(data_dir):
        if root == data_dir:
            classes = sorted(dirs)
        else:
            dirname = os.path.basename(root)
            if dirname not in classes:
                continue
            class_idx = classes.index(dirname)
            print(f'Reading dir: {root}, which has {len(files)} images')
            for img_name in files:
                image_paths.append(os.path.join(root, img_name))
                labels.append(class_idx)

    label_map = dict(zip(range(len(classes)), classes))
    return image_paths, labels, label_map


def shuffle_and_split(image_paths, labels, val_percent=0.1, test_percent=0.1):
    """Shuffles and splits data into train, validation, and test sets."""
    image_paths = np.array(image_paths)
    labels = np.array(labels)
    perm = np.random.permutation(image_paths.shape[0])
    image_paths = image_paths[perm]
    labels = labels[perm]

    num_total = image_paths.shape[0]
    num_val = int(num_total * val_percent)
    num_test = int(num_total * test_percent)
    num_train = num_total - num_val - num_test

    train_and_val = {
        'data_train': image_paths[:num_train],
        'labels_train': labels[:num_train],
        'data_val': image_paths[num_train:num_train + num_val],
        'labels_val': labels[num_train:num_train + num_val],
    }
    test = {
        'data_test': image_paths[num_train + num_val:],
        'labels_test': labels[num_train + num_val:],
    }
    return train_and_val, test


def extract_embeddings(image_paths, interpreter):
    """Extracts feature embeddings for the given images."""
    input_size = common.input_size(interpreter)
    feature_dim = classify.num_classes(interpreter)
    embeddings = np.empty((len(image_paths), feature_dim), dtype=np.float32)
    for idx, path in enumerate(image_paths):
        with Image.open(path) as img:
            img = img.convert('RGB').resize(input_size, Image.NEAREST)
            common.set_input(interpreter, img)
            interpreter.invoke()
            embeddings[idx, :] = classify.get_scores(interpreter)
    return embeddings


def train(model_path, data_dir, output_dir):
    """Trains a softmax regression model using the embedding extractor."""
    t0 = time.perf_counter()
    image_paths, labels, label_map = get_image_paths(data_dir)
    train_and_val, test_data = shuffle_and_split(image_paths, labels)

    interpreter = make_interpreter(model_path, device=':0')
    interpreter.allocate_tensors()

    print('Extract embeddings for data_train')
    train_and_val['data_train'] = extract_embeddings(
        train_and_val['data_train'], interpreter)
    print('Extract embeddings for data_val')
    train_and_val['data_val'] = extract_embeddings(
        train_and_val['data_val'], interpreter)
    t1 = time.perf_counter()
    print(f'Data preprocessing takes {t1 - t0:.2f} seconds')

    feature_dim = train_and_val['data_train'].shape[1]
    num_classes = np.max(train_and_val['labels_train']) + 1
    model = SoftmaxRegression(
        feature_dim, num_classes, weight_scale=5e-2, reg=0.0)

    model.train_with_sgd(
        train_and_val, num_iter=500, learning_rate=1e-2, batch_size=100)
    t2 = time.perf_counter()
    print(f'Training takes {t2 - t1:.2f} seconds')

    out_model_path = os.path.join(output_dir, 'retrained_model_edgetpu.tflite')
    with open(out_model_path, 'wb') as f:
        f.write(model.serialize_model(model_path))
    print(f'Model {out_model_path} saved.')

    label_map_path = os.path.join(output_dir, 'label_map.txt')
    with open(label_map_path, 'w') as f:
        for key, val in label_map.items():
            f.write(f'{key} {val}\n')
    print(f'Label map {label_map_path} saved.')

    retrained_interpreter = make_interpreter(out_model_path, device=':0')
    retrained_interpreter.allocate_tensors()
    test_embeddings = extract_embeddings(
        test_data['data_test'], retrained_interpreter)
    accuracy = np.mean(
        np.argmax(test_embeddings, axis=1) == test_data['labels_test'])
    print(f'Saved tflite model test accuracy: {accuracy * 100:.2f}%')
    t3 = time.perf_counter()
    print(f'Total time: {t3 - t0:.2f} seconds')


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--embedding_extractor_path', required=True,
                        help='Path to embedding extractor tflite model.')
    parser.add_argument('--data_dir', required=True,
                        help='Directory with training data.')
    parser.add_argument('--output_dir', default='output',
                        help='Directory to save retrained model and label map.')
    args = parser.parse_args()

    if not os.path.exists(args.data_dir):
        sys.exit(f'{args.data_dir} does not exist!')

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    train(args.embedding_extractor_path, args.data_dir, args.output_dir)


if __name__ == '__main__':
    main()
