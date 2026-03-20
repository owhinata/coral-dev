# Lint as: python3
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Imprinting (weight imprinting) training benchmark on Edge TPU.

Measures training time for weight imprinting with synthetic random data
(10 categories, 20 images each). Requires Edge TPU and pycoral.

Based on: https://github.com/google-coral/pycoral/blob/master/benchmarks/imprinting_benchmarks.py

Differences from the original:
  - Self-contained: no dependency on benchmark_utils; no CSV export or
    reference comparison.
  - Model discovery: finds *_l2norm_quant_edgetpu.tflite in --model-dir
    instead of reading from a reference CSV.
  - Output: prints a summary table with training time per model.
  - Delegate sharing: creates one delegate and reuses it across all models,
    matching the original behavior.
"""

import argparse
import collections
import os
import sys
import time

import numpy as np
from pycoral.adapters import classify
from pycoral.adapters import common
from pycoral.learn.imprinting import engine
from pycoral.utils import edgetpu


NUM_CATEGORIES = 10
IMAGES_PER_CATEGORY = 20


def find_models(model_dir):
    """Find imprinting-compatible models (*_l2norm_quant_edgetpu.tflite)."""
    models = []
    for f in sorted(os.listdir(model_dir)):
        if f.endswith('_l2norm_quant_edgetpu.tflite'):
            models.append(f)
    return models


def run_benchmark(model_path, delegate):
    """Measure training time for a single model. Returns time in ms."""
    imprinting_engine = engine.ImprintingEngine(
        model_path, keep_classes=False)

    extractor = edgetpu.make_interpreter(
        imprinting_engine.serialize_extractor_model(), delegate=delegate)
    extractor.allocate_tensors()
    width, height = common.input_size(extractor)

    np.random.seed(12345)

    # Generate synthetic data: 10 categories, 20 images each
    data_by_category = collections.defaultdict(list)
    for i in range(NUM_CATEGORIES):
        for _ in range(IMAGES_PER_CATEGORY):
            data_by_category[i].append(
                np.random.randint(0, 256, (height, width, 3), dtype=np.uint8))

    start = time.perf_counter()

    for class_id, tensors in enumerate(data_by_category.values()):
        for tensor in tensors:
            common.set_input(extractor, tensor)
            extractor.invoke()
            imprinting_engine.train(
                classify.get_scores(extractor), class_id=class_id)

    imprinting_engine.serialize_model()

    return (time.perf_counter() - start) * 1000.0


def main():
    parser = argparse.ArgumentParser(
        description='Imprinting training benchmark for Edge TPU')
    parser.add_argument('--model-dir', default=None,
                        help='Directory containing .tflite models '
                             '(default: same directory as this script)')
    args = parser.parse_args()

    if args.model_dir is None:
        model_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        model_dir = args.model_dir

    models = find_models(model_dir)
    if not models:
        print('No imprinting models (*_l2norm_quant_edgetpu.tflite) found '
              f'in {model_dir}', file=sys.stderr)
        sys.exit(1)

    print(f'Data: {NUM_CATEGORIES} categories, '
          f'{IMAGES_PER_CATEGORY} images each')
    print(f'Model directory: {model_dir}')
    print()

    name_width = max(len(m) for m in models)
    header = f'{"Model":<{name_width}}  {"Training time (ms)":>20}'
    print(header)
    print('-' * len(header))

    delegate = edgetpu.load_edgetpu_delegate()
    for model_file in models:
        model_path = os.path.join(model_dir, model_file)
        elapsed = run_benchmark(model_path, delegate)
        print(f'{model_file:<{name_width}}  {elapsed:20.2f}')


if __name__ == '__main__':
    main()
