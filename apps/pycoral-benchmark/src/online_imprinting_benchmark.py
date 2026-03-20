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
"""Online imprinting inference benchmark on Edge TPU.

Measures inference time under online training mode: after training each
category, a new interpreter is created from the updated model and one
inference is performed. The total inference time across all categories is
reported. Requires Edge TPU and pycoral.

Based on: https://github.com/google-coral/pycoral/blob/master/benchmarks/online_imprinting_benchmarks.py

Differences from the original:
  - Self-contained: no dependency on benchmark_utils; no CSV export or
    reference comparison.
  - Model discovery: finds *_l2norm_quant_edgetpu.tflite in --model-dir
    instead of reading from a reference CSV.
  - Output: prints a summary table with inference time per model.
  - Delegate sharing: creates one delegate and reuses it across all models,
    matching the original behavior.
  - Uses pycoral edgetpu.make_interpreter with model_content instead of
    tflite_runtime directly, for consistent delegate handling.
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

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter


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
    """Measure online imprinting inference time. Returns time in ms."""
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

    inference_time = 0.0
    for class_id, tensors in enumerate(data_by_category.values()):
        # Train on all images in this category
        for tensor in tensors:
            common.set_input(extractor, tensor)
            extractor.invoke()
            imprinting_engine.train(
                classify.get_scores(extractor), class_id=class_id)

        # Measure inference with the updated model
        start = time.perf_counter()
        interpreter = Interpreter(
            model_content=imprinting_engine.serialize_model(),
            experimental_delegates=[delegate])
        interpreter.allocate_tensors()
        common.set_input(interpreter, tensors[0])
        interpreter.invoke()
        classify.get_classes(interpreter, top_k=3)
        inference_time += (time.perf_counter() - start) * 1000.0

    return inference_time


def main():
    parser = argparse.ArgumentParser(
        description='Online imprinting inference benchmark for Edge TPU')
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
    header = f'{"Model":<{name_width}}  {"Inference time (ms)":>20}'
    print(header)
    print('-' * len(header))

    delegate = edgetpu.load_edgetpu_delegate()
    for model_file in models:
        model_path = os.path.join(model_dir, model_file)
        elapsed = run_benchmark(model_path, delegate)
        print(f'{model_file:<{name_width}}  {elapsed:20.2f}')


if __name__ == '__main__':
    main()
