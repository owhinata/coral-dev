# pycoral Examples

[pycoral](https://github.com/google-coral/pycoral) の [examples](https://github.com/google-coral/pycoral/tree/master/examples) を自己完結型で移植したアプリです。pycoral API の使い方を学ぶことが目的で、Edge TPU 1 つで実行可能な 7 つの example を対象としています。

| Example | 内容 | 主要 API |
|---------|------|----------|
| classify_image | 画像分類 | `classify.get_classes`, `common.input_size`, `common.set_input` |
| detect_image | 物体検出 | `detect.get_objects`, `common.set_resized_input` |
| semantic_segmentation | セマンティックセグメンテーション | `segment.get_output`, `common.set_resized_input` |
| movenet_pose_estimation | 姿勢推定（17 キーポイント） | `common.output_tensor`, `common.set_input` |
| small_object_detection | タイルベース小物体検出 + NMS | `detect.get_objects`, `common.set_resized_input` |
| backprop_last_layer | 転移学習（最終層バックプロップ） | `SoftmaxRegression`, `classify.get_scores` |
| imprinting_learning | 転移学習（weight imprinting） | `ImprintingEngine`, `classify.get_classes` |

## 前提条件

- CMake 3.16 以上
- インターネット接続（初回のモデル・テストデータダウンロード時のみ）
- Coral Dev Board に pycoral / tflite-runtime がインストール済み（Mendel Linux にプリインストール）
- 画像出力のある example で `--display` を使用する場合は `python3-opencv`（ボードにインストール）

## ビルド・デプロイ・実行

### モデル・テストデータのダウンロード

```bash
cmake -B build/pycoral-examples -S apps/pycoral-examples
```

ダウンロードされたファイルは `build/pycoral-examples/data/` に保存されます。

### ボードへのデプロイ

```bash
cmake --build build/pycoral-examples --target deploy
```

スクリプトとデータがボードの `/home/mendel/work/pycoral-examples/` に転送されます。

### example 実行（ctest）

```bash
# 全 example 実行（transfer-learning を除く）
ctest --test-dir build/pycoral-examples -V -E "(backprop|imprinting)"

# 分類のみ
ctest --test-dir build/pycoral-examples -V -R classify

# 検出系のみ
ctest --test-dir build/pycoral-examples -V -L detect
```

### 転移学習の実行

転移学習の example は訓練データをボード上にダウンロードしてから実行します。

```bash
# backprop_last_layer 用
cmake --build build/pycoral-examples --target download-flower-photos
ctest --test-dir build/pycoral-examples -V -R backprop

# imprinting_learning 用
cmake --build build/pycoral-examples --target download-imprinting-data
ctest --test-dir build/pycoral-examples -V -R imprinting
```

---

## Example 解説

=== "classify_image"

    ### 画像分類

    鳥画像を MobileNet V2 で分類し、上位 k クラスのラベルとスコアを出力します。

    **使用 API**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `classify.get_classes`, `dataset.read_label_file`

    **処理の流れ**:

    1. `make_interpreter()` で Edge TPU delegate 付きインタープリタを作成
    2. `common.input_size()` でモデルの入力サイズを取得し、PIL で画像をリサイズ
    3. 量子化パラメータを確認し、前処理が必要かどうか判定
    4. `common.set_input()` で入力テンソルにデータをセット
    5. `interpreter.invoke()` で推論実行（1 回目はモデルロード含む）
    6. `classify.get_classes()` で分類結果を取得

    ```python
    # 量子化パラメータの確認
    params = common.input_details(interpreter, 'quantization_parameters')
    scale = params['scales']
    zero_point = params['zero_points']
    if abs(scale * 128.0 - 1) < 1e-5 and abs(128.0 - zero_point) < 1e-5:
        common.set_input(interpreter, image)  # 前処理不要
    else:
        normalized = (np.asarray(image) - 128.0) / (128.0 * scale) + zero_point
        common.set_input(interpreter, normalized.astype(np.uint8))
    ```

=== "detect_image"

    ### 物体検出

    画像から物体を検出し、バウンディングボックスとラベルを描画します。

    **使用 API**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **処理の流れ**:

    1. `common.set_resized_input()` で画像をモデル入力サイズにリサイズしつつセット（スケール係数を返す）
    2. `detect.get_objects()` でスコア閾値以上の検出結果を取得
    3. OpenCV で BBox を描画

    ```python
    # set_resized_input はリサイズとスケール計算を一度に行う
    _, scale = common.set_resized_input(
        interpreter, image.size,
        lambda size: image.resize(size, Image.LANCZOS))

    interpreter.invoke()
    objs = detect.get_objects(interpreter, args.threshold, scale)
    ```

    `--output` で結果画像を保存、`--display` で HDMI ディスプレイに表示できます。

=== "semantic_segmentation"

    ### セマンティックセグメンテーション

    DeepLab V3 で画像のピクセルごとにクラスを推定し、PASCAL VOC カラーマップで可視化します。

    **使用 API**: `edgetpu.make_interpreter`, `common.set_resized_input`, `common.set_input`, `segment.get_output`

    **処理の流れ**:

    1. `--keep_aspect_ratio` 指定時は `set_resized_input()` でアスペクト比を維持
    2. `segment.get_output()` でセグメンテーション結果を取得
    3. PASCAL VOC カラーマップで各クラスを色分け
    4. 入力画像とマスクを横並びで結合

    ```python
    result = segment.get_output(interpreter)
    if len(result.shape) == 3:
        result = np.argmax(result, axis=-1)

    colormap = create_pascal_label_colormap()
    mask = colormap[result]
    ```

=== "movenet_pose_estimation"

    ### 姿勢推定

    MoveNet で人体の 17 キーポイントを推定し、スケルトンを描画します。

    **使用 API**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `common.output_tensor`

    **処理の流れ**:

    1. `common.set_input()` でリサイズした画像をセット
    2. `common.output_tensor()` で出力テンソルを取得（17 × 3: y, x, score）
    3. キーポイントとスケルトン接続を OpenCV で描画

    ```python
    pose = common.output_tensor(interpreter, 0).copy().reshape(17, 3)
    # pose[i] = [y, x, score]（正規化座標）
    ```

    17 キーポイント: nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle

=== "small_object_detection"

    ### タイルベース小物体検出

    大きな画像を複数サイズのタイルに分割して検出し、NMS で重複を除去します。

    **使用 API**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **処理の流れ**:

    1. `--tile_sizes` で指定された複数のタイルサイズでループ
    2. 各タイルを切り出し、`set_resized_input()` でモデルに入力
    3. 検出結果の BBox をタイル位置基準から元画像基準に変換
    4. ラベルごとに NMS（Non-Maximum Suppression）を適用

    ```python
    # タイルごとに検出、BBox を元画像座標に変換
    for tile_location in tiles_location_gen(img_size, tile_size, overlap):
        tile = img.crop(tile_location)
        _, scale = common.set_resized_input(interpreter, tile.size, ...)
        interpreter.invoke()
        objs = detect.get_objects(interpreter, threshold, scale)
        # BBox を元画像座標に変換
    ```

    NMS なしモデル（`_no_nms`）を使用することで、後処理を自前で実装し約 2 倍の高速化を実現しています。

=== "backprop_last_layer"

    ### 転移学習（最終層バックプロップ）

    Embedding extractor で特徴抽出し、SoftmaxRegression で最終層を学習します。花の画像データセットを使用。

    **使用 API**: `edgetpu.make_interpreter`, `common.set_input`, `classify.get_scores`, `SoftmaxRegression`

    **処理の流れ**:

    1. `get_image_paths()` でサブディレクトリ構造から画像パスとラベルを取得
    2. Embedding extractor モデルで全画像の特徴ベクトルを抽出
    3. `SoftmaxRegression` で最終層を SGD で学習（500 イテレーション）
    4. `model.serialize_model()` で学習済み重みを元モデルに結合して保存
    5. 保存したモデルでテストデータの精度を検証

    ```python
    # 特徴抽出
    common.set_input(interpreter, img.resize(input_size, Image.NEAREST))
    interpreter.invoke()
    embeddings[idx, :] = classify.get_scores(interpreter)

    # 学習
    model = SoftmaxRegression(feature_dim, num_classes, ...)
    model.train_with_sgd(train_and_val, num_iter=500, learning_rate=1e-2, ...)
    ```

    **訓練データ**: `download-flower-photos` ターゲットでボード上にダウンロード（flower_photos: 5 クラス × 約 700 枚）

=== "imprinting_learning"

    ### 転移学習（weight imprinting）

    Weight imprinting で新しいクラスを追加学習します。バックプロップ不要で高速に学習可能。

    **使用 API**: `ImprintingEngine`, `edgetpu.make_interpreter`, `common.set_input`, `classify.get_scores`, `classify.get_classes`

    **処理の流れ**:

    1. `ImprintingEngine` でモデルから extractor を生成
    2. 訓練画像の特徴ベクトルを抽出し、`engine.train()` で重みを更新
    3. `engine.serialize_model()` で学習済みモデルを保存
    4. 保存したモデルで Top-1〜5 精度を評価

    ```python
    engine = ImprintingEngine(args.model_path, keep_classes=args.keep_classes)
    extractor = make_interpreter(engine.serialize_extractor_model(), device=':0')
    extractor.allocate_tensors()

    # 学習
    common.set_input(extractor, tensor)
    extractor.invoke()
    embedding = classify.get_scores(extractor)
    engine.train(embedding, class_id=num_classes + class_id)
    ```

    **訓練データ**: `download-imprinting-data` ターゲットでボード上にダウンロード（open_image_v4_subset: 10 カテゴリ × 20 枚）

---

## CMake ターゲット / ctest 一覧 { #cmake-targets }

### 設定

```bash
cmake -B build/pycoral-examples -S apps/pycoral-examples
```

### ターゲット一覧

| ターゲット | コマンド | 説明 |
|-----------|---------|------|
| `deploy` | `cmake --build build/pycoral-examples --target deploy` | スクリプト + データをボードへ転送 |
| `download-flower-photos` | `cmake --build build/pycoral-examples --target download-flower-photos` | flower_photos データセットをボード上に DL |
| `download-imprinting-data` | `cmake --build build/pycoral-examples --target download-imprinting-data` | imprinting データセットをボード上に DL |

### ctest 一覧

| テスト名 | ラベル | 説明 |
|---------|--------|------|
| `classify-image` | `edgetpu`, `classify` | 画像分類 |
| `detect-image` | `edgetpu`, `detect` | 物体検出 |
| `semantic-segmentation` | `edgetpu`, `segmentation` | セマンティックセグメンテーション |
| `movenet-pose` | `edgetpu`, `pose` | 姿勢推定 |
| `small-object-detection` | `edgetpu`, `detect` | タイルベース小物体検出 |
| `backprop-last-layer` | `edgetpu`, `transfer-learning` | 転移学習（バックプロップ） |
| `imprinting-learning` | `edgetpu`, `transfer-learning` | 転移学習（imprinting） |

### 接続設定

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `CORAL_IP` | (空 = mdt で自動検出) | Coral Dev Board の IP アドレス |

## 実行結果

=== "推論系"

    ### classify_image

    | 項目 | 値 |
    |------|-----|
    | モデル | mobilenet_v2_1.0_224_inat_bird_quant_edgetpu |
    | 1st inference (model load 含む) | 14.70 ms |
    | 2nd inference | 3.37 ms |

    | ラベル | スコア |
    |--------|--------|
    | Ara macao (Scarlet Macaw) | 0.75781 |
    | Platycercus elegans (Crimson Rosella) | 0.07422 |
    | Coracias caudatus (Lilac-breasted Roller) | 0.01562 |

    ### detect_image

    | 項目 | 値 |
    |------|-----|
    | モデル | ssd_mobilenet_v2_coco_quant_postprocess_edgetpu |
    | 1st inference (model load 含む) | 36.96 ms |
    | 2nd inference | 12.58 ms |

    | ラベル | スコア | BBox |
    |--------|--------|------|
    | tie | 0.840 | (227, 419, 292, 541) |
    | person | 0.805 | (2, 4, 513, 595) |

    ### semantic_segmentation

    | 項目 | 値 |
    |------|-----|
    | モデル | deeplabv3_mnv2_pascal_quant_edgetpu |
    | 1st inference (model load 含む) | 223.14 ms |
    | 2nd inference | 220.26 ms |

    ### movenet_pose_estimation

    | 項目 | 値 |
    |------|-----|
    | モデル | movenet_single_pose_lightning_ptq_edgetpu |
    | 1st inference (model load 含む) | 29.12 ms |
    | 2nd inference | 26.90 ms |

    | キーポイント | 座標 (x, y) | スコア |
    |-------------|-------------|--------|
    | nose | (0.578, 0.332) | 0.500 |
    | left_eye | (0.590, 0.320) | 0.635 |
    | right_eye | (0.565, 0.311) | 0.701 |
    | left_shoulder | (0.578, 0.422) | 0.635 |
    | right_shoulder | (0.418, 0.414) | 0.500 |
    | left_hip | (0.389, 0.598) | 0.754 |
    | right_hip | (0.287, 0.615) | 0.430 |
    | left_ankle | (0.512, 0.848) | 0.635 |
    | right_ankle | (0.340, 0.889) | 0.701 |

    ### small_object_detection

    | 項目 | 値 |
    |------|-----|
    | モデル | ssd_mobilenet_v2_coco_quant_no_nms_edgetpu |
    | タイルサイズ | 1352x900, 500x500, 250x250 |
    | 検出時間 | 922.44 ms |
    | 検出数 | 18 オブジェクト（kite: 7, person: 10, backpack: 1） |

=== "転移学習"

    ### backprop_last_layer

    | 項目 | 値 |
    |------|-----|
    | モデル | mobilenet_v1_1.0_224_quant_embedding_extractor_edgetpu |
    | データセット | flower_photos（5 クラス × 約 700 枚） |
    | 前処理時間 | 38.48 秒 |
    | 学習時間 | 7.64 秒 |
    | 合計時間 | 50.34 秒 |
    | テスト精度 | 89.65% |

    ### imprinting_learning

    | 項目 | 値 |
    |------|-----|
    | モデル | mobilenet_v1_1.0_224_l2norm_quant_edgetpu |
    | データセット | open_image_v4_subset（10 カテゴリ × 20 枚） |
    | 学習時間 | 36576.60 ms |

    | Top-k | 精度 |
    |-------|------|
    | Top 1 | 98% |
    | Top 2 | 100% |
    | Top 3 | 100% |
    | Top 4 | 100% |
    | Top 5 | 100% |
