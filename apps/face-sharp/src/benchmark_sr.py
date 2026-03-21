"""Benchmark ESPCN super-resolution inference on Coral Dev Board (CPU).

Usage:
    python3 benchmark_sr.py [--model espcn_x3.tflite] [--iterations 100]
"""

import argparse
import time

import numpy as np
from tflite_runtime.interpreter import Interpreter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="espcn_x3.tflite")
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()

    interpreter = Interpreter(model_path=args.model)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    input_shape = input_details["shape"]
    output_shape = output_details["shape"]
    input_dtype = input_details["dtype"]

    print(f"Model: {args.model}")
    print(f"Input:  {input_shape} ({input_dtype.__name__})")
    print(f"Output: {output_shape}")
    print()

    # Prepare dummy input
    if input_dtype == np.float32:
        dummy = np.random.rand(*input_shape).astype(np.float32)
    else:
        dummy = np.random.randint(0, 255, size=input_shape, dtype=input_dtype)

    interpreter.set_tensor(input_details["index"], dummy)

    # Warmup
    print("Warming up (5 iterations)...")
    for _ in range(5):
        interpreter.invoke()

    # Benchmark
    print(f"Benchmarking ({args.iterations} iterations)...")
    times = []
    for _ in range(args.iterations):
        start = time.perf_counter()
        interpreter.invoke()
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    times_ms = [t * 1000 for t in times]
    avg = sum(times_ms) / len(times_ms)
    minimum = min(times_ms)
    maximum = max(times_ms)
    fps = 1000.0 / avg

    print()
    print(f"Results ({args.iterations} iterations):")
    print(f"  Avg:  {avg:.2f} ms ({fps:.1f} fps)")
    print(f"  Min:  {minimum:.2f} ms")
    print(f"  Max:  {maximum:.2f} ms")


if __name__ == "__main__":
    main()
