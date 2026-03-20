# pycoral ベンチマーク

[pycoral](https://github.com/google-coral/pycoral) の推論ベンチマークを自己完結型で実行するアプリです。元リポジトリのクローンや `PYTHONPATH` 設定が不要で、Edge TPU / ボード CPU / 開発 PC CPU の 3 環境で実行できます。

## 前提条件

- CMake 3.16 以上
- インターネット接続（初回のモデルダウンロード時のみ）
- ボード実行: Coral Dev Board に pycoral / tflite-runtime がインストール済み（Mendel Linux にプリインストール）
- 開発 PC 実行: Python 3 + venv 環境に `ai-edge-litert`（`tflite-runtime` の後継）と `numpy` をインストール

## 設計

### 自己完結型の理由

pycoral リポジトリのベンチマークを実行するには、リポジトリのクローンと `PYTHONPATH` 設定が必要です。また、システムの pycoral パッケージと衝突する問題があります。本アプリではベンチマークスクリプトとモデルファイルを `apps/pycoral-benchmark/` に集約し、これらの問題を解消しています。

### 条件付き import

`pycoral` は Edge TPU モード時のみ import します。CPU モードでは `ai_edge_litert`（開発 PC）または `tflite_runtime`（ボード）のみを使用するため、pycoral がインストールされていない開発 PC でも CPU ベンチマークを実行できます。

### ctest によるベンチマーク管理

`enable_testing()` + `add_test()` でベンチマークを登録し、ラベルで分類しています。`ctest` のフィルタ機能で Edge TPU / CPU を選択的に実行できます。将来のベンチマーク追加時は `add_test()` + `set_tests_properties()` を追加するだけです。

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

`project(pycoral-benchmark NONE)` でコンパイラ検出をスキップし、ツールチェーンファイル不要で configure できます。`file(DOWNLOAD ...)` で google-coral/test_data から 12 モデル（6 モデル x CPU/TPU）を自動ダウンロードします。

## モデルのダウンロード

リポジトリのルートディレクトリから実行します。ツールチェーンファイルは不要です。

```bash
cmake -B build/pycoral-benchmark -S apps/pycoral-benchmark
```

ダウンロードされたモデルは `build/pycoral-benchmark/models/` に保存されます。

### 対象モデル

| ベース名 | CPU 版 | TPU 版 |
|---------|--------|--------|
| inception_v1_224_quant | `.tflite` | `_edgetpu.tflite` |
| inception_v4_299_quant | `.tflite` | `_edgetpu.tflite` |
| mobilenet_v1_1.0_224_quant | `.tflite` | `_edgetpu.tflite` |
| mobilenet_v2_1.0_224_quant | `.tflite` | `_edgetpu.tflite` |
| ssd_mobilenet_v1_coco_quant_postprocess | `.tflite` | `_edgetpu.tflite` |
| ssd_mobilenet_v2_face_quant_postprocess | `.tflite` | `_edgetpu.tflite` |

## デプロイと実行

### ボードへのデプロイ

```bash
cmake --build build/pycoral-benchmark --target deploy
```

スクリプトとモデルファイルがボードの `/home/mendel/work/pycoral-benchmark/` に転送されます。

### ベンチマーク実行（ctest）

```bash
# 全ベンチマーク実行
ctest --test-dir build/pycoral-benchmark -V

# Edge TPU のみ
ctest --test-dir build/pycoral-benchmark -V -L edgetpu

# CPU のみ
ctest --test-dir build/pycoral-benchmark -V -L cpu

# inference のみ（名前でフィルタ）
ctest --test-dir build/pycoral-benchmark -V -R inference
```

## 開発 PC での実行

venv 環境で ctest から CPU ベンチマークを実行できます。

```bash
source .venv/bin/activate
pip install -r requirements.txt
ctest --test-dir build/pycoral-benchmark -V -L local
```

直接実行も可能です:

```bash
python3 apps/pycoral-benchmark/src/inference_benchmark.py \
    --device cpu --model-dir build/pycoral-benchmark/models
```

---

## CMake ターゲット / ctest 一覧 { #cmake-targets }

### 設定

```bash
cmake -B build/pycoral-benchmark -S apps/pycoral-benchmark
```

### ターゲット一覧

| ターゲット | コマンド | 説明 |
|-----------|---------|------|
| `deploy` | `cmake --build build/pycoral-benchmark --target deploy` | スクリプト + モデルをボードへ転送 |

### ctest 一覧

| テスト名 | ラベル | 説明 |
|---------|--------|------|
| `inference-edgetpu` | `edgetpu`, `inference` | Edge TPU 推論ベンチマーク |
| `inference-cpu` | `cpu`, `inference` | ボード CPU 推論ベンチマーク |
| `inference-cpu-local` | `cpu`, `inference`, `local` | 開発 PC CPU 推論ベンチマーク |
| `softmax-regression` | `cpu`, `softmax-regression` | Softmax 回帰学習ベンチマーク |
| `imprinting` | `edgetpu`, `imprinting` | Weight imprinting 学習ベンチマーク |

### 接続設定

CMake キャッシュ変数で接続先をカスタマイズできます:

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `CORAL_IP` | (空 = mdt で自動検出) | Coral Dev Board の IP アドレス |

## 実行結果

=== "Inference"

    ### Edge TPU（ボード、200 iterations）

    | モデル | Mean (ms) | Std (ms) | Min (ms) | Max (ms) |
    |--------|-----------|----------|----------|----------|
    | inception_v1_224_quant_edgetpu | 5.65 | 0.42 | 4.74 | 6.70 |
    | inception_v4_299_quant_edgetpu | 101.37 | 0.13 | 100.79 | 101.67 |
    | mobilenet_v1_1.0_224_quant_edgetpu | 3.15 | 0.27 | 2.68 | 4.05 |
    | mobilenet_v2_1.0_224_quant_edgetpu | 3.39 | 0.23 | 3.21 | 4.28 |
    | ssd_mobilenet_v1_coco_quant_postprocess_edgetpu | 11.44 | 0.28 | 10.51 | 11.74 |
    | ssd_mobilenet_v2_face_quant_postprocess_edgetpu | 8.07 | 0.66 | 6.38 | 9.02 |

    ### CPU（ボード、20 iterations）

    | モデル | Mean (ms) | Std (ms) | Min (ms) | Max (ms) |
    |--------|-----------|----------|----------|----------|
    | inception_v1_224_quant | 376.13 | 1.57 | 375.60 | 382.97 |
    | inception_v4_299_quant | 2973.37 | 0.28 | 2972.86 | 2973.91 |
    | mobilenet_v1_1.0_224_quant | 167.42 | 1.75 | 166.87 | 175.04 |
    | mobilenet_v2_1.0_224_quant | 126.85 | 0.08 | 126.72 | 127.07 |
    | ssd_mobilenet_v1_coco_quant_postprocess | 350.32 | 0.09 | 350.17 | 350.51 |
    | ssd_mobilenet_v2_face_quant_postprocess | 288.89 | 0.09 | 288.70 | 289.04 |

    ### CPU（開発 PC、20 iterations）

    参考スペック: AMD Ryzen 7 8840U（16 スレッド）/ 16 GB RAM

    | モデル | Mean (ms) | Std (ms) | Min (ms) | Max (ms) |
    |--------|-----------|----------|----------|----------|
    | inception_v1_224_quant | 21.81 | 0.41 | 21.52 | 23.36 |
    | inception_v4_299_quant | 159.80 | 0.54 | 159.01 | 160.62 |
    | mobilenet_v1_1.0_224_quant | 8.26 | 0.14 | 8.14 | 8.57 |
    | mobilenet_v2_1.0_224_quant | 5.49 | 0.06 | 5.45 | 5.70 |
    | ssd_mobilenet_v1_coco_quant_postprocess | 17.84 | 0.12 | 17.73 | 18.24 |
    | ssd_mobilenet_v2_face_quant_postprocess | 13.94 | 0.02 | 13.88 | 14.00 |

=== "Softmax Regression"

    ### Softmax 回帰学習（ボード CPU、500 SGD iterations）

    | Classes | Features | Time (ms) | Accuracy |
    |---------|----------|-----------|----------|
    | 4 | 256 | 1035.28 | 25.39% |
    | 16 | 256 | 1504.50 | 7.81% |
    | 4 | 1024 | 4994.52 | 23.83% |
    | 16 | 1024 | 6260.45 | 5.08% |

    ランダムデータでの学習のため、精度は低い値になります（正常な動作です）。

=== "Imprinting"

    ### Weight Imprinting 学習（ボード Edge TPU、10 カテゴリ × 20 画像）

    | モデル | Training time (ms) |
    |--------|--------------------|
    | mobilenet_v1_1.0_224_l2norm_quant_edgetpu | 1057.06 |
