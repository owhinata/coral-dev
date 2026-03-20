# pycoral Benchmark

A self-contained app for running [pycoral](https://github.com/google-coral/pycoral) inference benchmarks. No repository cloning or `PYTHONPATH` configuration is needed. Supports execution on Edge TPU, board CPU, and development PC CPU.

## Prerequisites

- CMake 3.16 or later
- Internet connection (only for the initial model download)
- Board execution: pycoral / tflite-runtime installed on Coral Dev Board (pre-installed on Mendel Linux)
- Dev PC execution: Python 3 + venv with `ai-edge-litert` (successor to `tflite-runtime`) and `numpy` installed

## Design

### Why self-contained

Running benchmarks from the pycoral repository requires cloning the repo and configuring `PYTHONPATH`. There are also conflicts with the system pycoral package. This app consolidates benchmark scripts and model files in `apps/pycoral-benchmark/`, eliminating these issues.

### Conditional imports

`pycoral` is only imported in Edge TPU mode. CPU mode uses only `ai_edge_litert` (dev PC) or `tflite_runtime` (board), so CPU benchmarks can run on development PCs without pycoral installed.

### Benchmark management with ctest

Benchmarks are registered with `enable_testing()` + `add_test()` and classified by labels. The `ctest` filter feature allows selective execution of Edge TPU / CPU benchmarks. To add future benchmarks, simply add `add_test()` + `set_tests_properties()`.

## CMakeLists.txt

**`apps/pycoral-benchmark/CMakeLists.txt`**:

```cmake
cmake_minimum_required(VERSION 3.16)
project(pycoral-benchmark NONE)

# --- Download test models from google-coral/test_data ---
set(MODEL_DIR "${CMAKE_CURRENT_BINARY_DIR}/models")
set(MODEL_BASE_URL "https://github.com/google-coral/test_data/raw/master")

set(MODELS
    inception_v1_224_quant
    inception_v4_299_quant
    mobilenet_v1_1.0_224_quant
    mobilenet_v2_1.0_224_quant
    ssd_mobilenet_v1_coco_quant_postprocess
    ssd_mobilenet_v2_face_quant_postprocess
)

file(MAKE_DIRECTORY ${MODEL_DIR})

foreach(model ${MODELS})
    # CPU version
    if(NOT EXISTS "${MODEL_DIR}/${model}.tflite")
        message(STATUS "Downloading ${model}.tflite ...")
        file(DOWNLOAD
            "${MODEL_BASE_URL}/${model}.tflite"
            "${MODEL_DIR}/${model}.tflite"
            SHOW_PROGRESS
        )
    endif()

    # Edge TPU version
    if(NOT EXISTS "${MODEL_DIR}/${model}_edgetpu.tflite")
        message(STATUS "Downloading ${model}_edgetpu.tflite ...")
        file(DOWNLOAD
            "${MODEL_BASE_URL}/${model}_edgetpu.tflite"
            "${MODEL_DIR}/${model}_edgetpu.tflite"
            SHOW_PROGRESS
        )
    endif()
endforeach()

# --- Deploy ---
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/coral-deploy.cmake)

set(DEPLOY_DIR /home/mendel/work/pycoral-benchmark)

# Collect deploy file mappings (flat: all files go to DEPLOY_DIR root)
set(DEPLOY_FILES
    "${CMAKE_CURRENT_SOURCE_DIR}/src/inference_benchmark.py:inference_benchmark.py"
)
foreach(model ${MODELS})
    list(APPEND DEPLOY_FILES
        "${MODEL_DIR}/${model}.tflite:${model}.tflite"
        "${MODEL_DIR}/${model}_edgetpu.tflite:${model}_edgetpu.tflite"
    )
endforeach()

coral_add_deploy_target(
    DEPLOY_DIR ${DEPLOY_DIR}
    FILES ${DEPLOY_FILES}
)

# --- Tests (ctest) ---
enable_testing()

add_test(NAME inference-edgetpu
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 inference_benchmark.py --device edgetpu"
)
set_tests_properties(inference-edgetpu PROPERTIES LABELS "edgetpu;inference")

add_test(NAME inference-cpu
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 inference_benchmark.py --device cpu"
)
set_tests_properties(inference-cpu PROPERTIES LABELS "cpu;inference")
```

`project(pycoral-benchmark NONE)` skips compiler detection, so no toolchain file is needed for configure. `file(DOWNLOAD ...)` automatically downloads 12 models (6 models x CPU/TPU) from google-coral/test_data.

## Model Download

Run from the repository root directory. No toolchain file is needed.

```bash
cmake -B build/pycoral-benchmark -S apps/pycoral-benchmark
```

Downloaded models are saved to `build/pycoral-benchmark/models/`.

### Target Models

| Base Name | CPU Version | TPU Version |
|-----------|-------------|-------------|
| inception_v1_224_quant | `.tflite` | `_edgetpu.tflite` |
| inception_v4_299_quant | `.tflite` | `_edgetpu.tflite` |
| mobilenet_v1_1.0_224_quant | `.tflite` | `_edgetpu.tflite` |
| mobilenet_v2_1.0_224_quant | `.tflite` | `_edgetpu.tflite` |
| ssd_mobilenet_v1_coco_quant_postprocess | `.tflite` | `_edgetpu.tflite` |
| ssd_mobilenet_v2_face_quant_postprocess | `.tflite` | `_edgetpu.tflite` |

## Deploy and Run

### Deploy to Board

```bash
cmake --build build/pycoral-benchmark --target deploy
```

Scripts and model files are transferred to `/home/mendel/work/pycoral-benchmark/` on the board.

### Run Benchmarks (ctest)

```bash
# Run all benchmarks
ctest --test-dir build/pycoral-benchmark -V

# Edge TPU only
ctest --test-dir build/pycoral-benchmark -V -L edgetpu

# CPU only
ctest --test-dir build/pycoral-benchmark -V -L cpu

# inference only (filter by name)
ctest --test-dir build/pycoral-benchmark -V -R inference
```

## Running on Development PC

CPU benchmarks can be run in a venv environment.

```bash
source .venv/bin/activate
pip install -r requirements.txt
python3 apps/pycoral-benchmark/src/inference_benchmark.py \
    --device cpu --model-dir build/pycoral-benchmark/models
```

## Example Output

```
Device: Edge TPU
Iterations: 200
Model directory: /home/mendel/work/pycoral-benchmark

Model                                                  Mean (ms)    Std (ms)    Min (ms)    Max (ms)
----------------------------------------------------------------------------------------------------
inception_v1_224_quant_edgetpu.tflite                       3.02        0.11        2.87        3.61
inception_v4_299_quant_edgetpu.tflite                      23.40        0.18       23.11       24.32
mobilenet_v1_1.0_224_quant_edgetpu.tflite                   2.96        0.09        2.82        3.44
mobilenet_v2_1.0_224_quant_edgetpu.tflite                   3.62        0.12        3.45        4.21
ssd_mobilenet_v1_coco_quant_postprocess_edgetpu.tflite     10.15        0.14        9.92       10.71
ssd_mobilenet_v2_face_quant_postprocess_edgetpu.tflite      6.58        0.13        6.38        7.15
```

---

## CMake Targets / ctest List { #cmake-targets }

### Configuration

```bash
cmake -B build/pycoral-benchmark -S apps/pycoral-benchmark
```

### Target List

| Target | Command | Description |
|--------|---------|-------------|
| `deploy` | `cmake --build build/pycoral-benchmark --target deploy` | Transfer scripts + models to board |

### ctest List

| Test Name | Labels | Description |
|-----------|--------|-------------|
| `inference-edgetpu` | `edgetpu`, `inference` | Edge TPU inference benchmark |
| `inference-cpu` | `cpu`, `inference` | Board CPU inference benchmark |

### Connection Settings

Customize connection parameters via CMake cache variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CORAL_IP` | (empty = auto-detect via mdt) | Coral Dev Board IP address |
