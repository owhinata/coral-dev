#!/usr/bin/env python3
"""Inference benchmark for TFLite models on Edge TPU and CPU.

Measures per-model inference latency. Supports Edge TPU (via pycoral) and
CPU-only (via tflite-runtime) execution modes.

Based on: https://github.com/google-coral/pycoral/blob/master/benchmarks/inference_benchmarks.py
"""

import argparse
import os
import sys
import time

import numpy as np


def find_models(model_dir, edgetpu):
    """Find .tflite model files in model_dir."""
    suffix = '_edgetpu.tflite' if edgetpu else '.tflite'
    models = []
    for f in sorted(os.listdir(model_dir)):
        if not f.endswith('.tflite'):
            continue
        if edgetpu and f.endswith('_edgetpu.tflite'):
            models.append(f)
        elif not edgetpu and not f.endswith('_edgetpu.tflite'):
            models.append(f)
    return models


def make_interpreter(model_path, edgetpu):
    """Create a TFLite interpreter for the given model."""
    if edgetpu:
        from pycoral.utils.edgetpu import make_interpreter as _make
        return _make(model_path)
    else:
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:
            from tflite_runtime.interpreter import Interpreter
        return Interpreter(model_path=model_path)


def run_inference(interpreter, iterations):
    """Run inference and return list of per-iteration times in ms."""
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()

    # Fill input tensors with random data
    for detail in input_details:
        shape = detail['shape']
        dtype = detail['dtype']
        if np.issubdtype(dtype, np.floating):
            data = np.random.random(shape).astype(dtype)
        else:
            info = np.iinfo(dtype)
            data = np.random.randint(info.min, info.max + 1,
                                     size=shape, dtype=dtype)
        interpreter.set_tensor(detail['index'], data)

    # Warmup
    interpreter.invoke()

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        interpreter.invoke()
        elapsed = (time.perf_counter() - start) * 1000.0
        times.append(elapsed)
    return times


def main():
    parser = argparse.ArgumentParser(
        description='TFLite inference benchmark for Edge TPU and CPU')
    parser.add_argument('--device', choices=['edgetpu', 'cpu'],
                        default='edgetpu',
                        help='Execution device (default: edgetpu)')
    parser.add_argument('--model-dir', default=None,
                        help='Directory containing .tflite models '
                             '(default: same directory as this script)')
    args = parser.parse_args()

    edgetpu = args.device == 'edgetpu'
    iterations = 200 if edgetpu else 20

    if args.model_dir is None:
        model_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        model_dir = args.model_dir

    models = find_models(model_dir, edgetpu)
    if not models:
        suffix = '*_edgetpu.tflite' if edgetpu else '*.tflite (non-edgetpu)'
        print(f'No models found matching {suffix} in {model_dir}',
              file=sys.stderr)
        sys.exit(1)

    np.random.seed(12345)

    device_label = 'Edge TPU' if edgetpu else 'CPU'
    print(f'Device: {device_label}')
    print(f'Iterations: {iterations}')
    print(f'Model directory: {model_dir}')
    print()

    name_width = max(len(m) for m in models)
    header = f'{"Model":<{name_width}}  {"Mean (ms)":>10}  {"Std (ms)":>10}  {"Min (ms)":>10}  {"Max (ms)":>10}'
    print(header)
    print('-' * len(header))

    for model_file in models:
        model_path = os.path.join(model_dir, model_file)
        interpreter = make_interpreter(model_path, edgetpu)
        times = run_inference(interpreter, iterations)
        mean = np.mean(times)
        std = np.std(times)
        mn = np.min(times)
        mx = np.max(times)
        print(f'{model_file:<{name_width}}  {mean:10.2f}  {std:10.2f}  {mn:10.2f}  {mx:10.2f}')


if __name__ == '__main__':
    main()
