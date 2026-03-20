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
"""Softmax regression training benchmark.

Measures training time of pycoral's SoftmaxRegression (on-device backprop)
with synthetic data across different class/feature dimension combinations.
No Edge TPU required — runs on CPU only, but requires pycoral.

Based on: https://github.com/google-coral/pycoral/blob/master/benchmarks/softmax_regression_benchmarks.py

Differences from the original:
  - Self-contained: no dependency on benchmark_utils; no CSV export or
    reference comparison.
  - Output: prints a summary table with training time and final accuracy
    for each configuration.
  - Configurations are the same as the original: 4/16 classes x 256/1024
    feature dimensions, 500 SGD iterations.
"""

import time

import numpy as np
from pycoral.learn.backprop.softmax_regression import SoftmaxRegression

# Training parameters (same as original)
NUM_TRAIN = 1024
NUM_VAL = 256
NUM_ITER = 500
LEARNING_RATE = 0.01
BATCH_SIZE = 100

CONFIGS = [
    (4, 256),
    (16, 256),
    (4, 1024),
    (16, 1024),
]


def run_benchmark(num_classes, feature_dim):
    """Train a SoftmaxRegression model and return (elapsed_ms, accuracy)."""
    np.random.seed(12345)

    data = {
        'data_train': np.random.rand(NUM_TRAIN, feature_dim).astype(np.float32),
        'labels_train': np.random.randint(0, num_classes, NUM_TRAIN),
        'data_val': np.random.rand(NUM_VAL, feature_dim).astype(np.float32),
        'labels_val': np.random.randint(0, num_classes, NUM_VAL),
    }

    model = SoftmaxRegression(
        feature_dim=feature_dim,
        num_classes=num_classes,
        weight_scale=0.01,
        reg=0.0,
    )

    start = time.perf_counter()
    model.train_with_sgd(
        data,
        num_iter=NUM_ITER,
        learning_rate=LEARNING_RATE,
        batch_size=BATCH_SIZE,
        print_every=0,
    )
    elapsed = (time.perf_counter() - start) * 1000.0

    accuracy = model.get_accuracy(data['data_val'], data['labels_val'])
    return elapsed, accuracy


def main():
    print(f'Training: {NUM_TRAIN} samples, Validation: {NUM_VAL} samples')
    print(f'SGD: {NUM_ITER} iterations, lr={LEARNING_RATE}, '
          f'batch_size={BATCH_SIZE}')
    print()

    header = (f'{"Classes":>8}  {"Features":>8}  '
              f'{"Time (ms)":>10}  {"Accuracy":>10}')
    print(header)
    print('-' * len(header))

    for num_classes, feature_dim in CONFIGS:
        elapsed, accuracy = run_benchmark(num_classes, feature_dim)
        print(f'{num_classes:>8}  {feature_dim:>8}  '
              f'{elapsed:10.2f}  {accuracy:10.2%}')


if __name__ == '__main__':
    main()
