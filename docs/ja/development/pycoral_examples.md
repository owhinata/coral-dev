# PyCoral API Examples

[pycoral](https://github.com/google-coral/pycoral) の [examples](https://github.com/google-coral/pycoral/tree/master/examples) を自己完結型で移植したアプリです。[PyCoral API](https://gweb-coral-full.uc.r.appspot.com/docs/reference/py/) の使い方を学ぶことが目的で、Edge TPU 1 つで実行可能な 7 つの example を対象としています。

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

    ソースコード: [classify_image.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/classify_image.py)

    **使用 API**: `edgetpu.make_interpreter`, `common.input_size`, `common.input_details`, `common.set_input`, `classify.get_classes`, `dataset.read_label_file`

    **処理の流れ**:

    1. `read_label_file()` でラベルファイルを読み込み
    2. `make_interpreter()` で Edge TPU delegate 付きインタープリタを作成
    3. `common.input_size()` でモデルの入力サイズを取得し、PIL で画像をリサイズ
    4. 量子化パラメータを確認し、前処理が必要かどうか判定
    5. `common.set_input()` で入力テンソルにデータをセット
    6. `interpreter.invoke()` で推論実行（1 回目はモデルロード含む）
    7. `classify.get_classes()` で分類結果を取得

    ```python
    # 1. ラベル読み込み
    labels = read_label_file(args.labels) if args.labels else {}

    # 2. Edge TPU インタープリタ作成
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    # 3. 入力サイズ取得・画像リサイズ
    if common.input_details(interpreter, 'dtype') != np.uint8:
        raise ValueError('Only support uint8 input type.')
    size = common.input_size(interpreter)
    image = Image.open(args.input).convert('RGB').resize(size, Image.LANCZOS)

    # 4. 量子化パラメータの確認
    params = common.input_details(interpreter, 'quantization_parameters')
    scale = params['scales']
    zero_point = params['zero_points']

    # 5. 入力テンソルにデータをセット（前処理の要否を判定）
    if abs(scale * 128.0 - 1) < 1e-5 and abs(128.0 - zero_point) < 1e-5:
        common.set_input(interpreter, image)  # 前処理不要
    else:
        normalized = (np.asarray(image) - 128.0) / (128.0 * scale) + zero_point
        np.clip(normalized, 0, 255, out=normalized)
        common.set_input(interpreter, normalized.astype(np.uint8))

    # 6. 推論実行
    interpreter.invoke()

    # 7. 分類結果を取得
    classes = classify.get_classes(interpreter, args.top_k, args.threshold)
    for c in classes:
        print(f'{labels.get(c.id, c.id)}: {c.score:.5f}')
    ```

=== "detect_image"

    ### 物体検出

    画像から物体を検出し、バウンディングボックスとラベルを描画します。

    ソースコード: [detect_image.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/detect_image.py)

    **使用 API**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **処理の流れ**:

    1. `read_label_file()` でラベルファイルを読み込み
    2. `make_interpreter()` でインタープリタを作成
    3. `common.set_resized_input()` で画像をモデル入力サイズにリサイズしつつセット（スケール係数を返す）
    4. `interpreter.invoke()` で推論実行
    5. `detect.get_objects()` でスコア閾値以上の検出結果を取得
    6. OpenCV で BBox を描画

    ```python
    # 1. ラベル読み込み
    labels = read_label_file(args.labels) if args.labels else {}

    # 2. Edge TPU インタープリタ作成
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    # 3. set_resized_input はリサイズとスケール計算を一度に行う
    image = Image.open(args.input)
    _, scale = common.set_resized_input(
        interpreter, image.size,
        lambda size: image.resize(size, Image.LANCZOS))

    # 4. 推論実行
    interpreter.invoke()

    # 5. 検出結果を取得
    objs = detect.get_objects(interpreter, args.threshold, scale)
    for obj in objs:
        print(f'{labels.get(obj.id, obj.id)}')
        print(f'  id:    {obj.id}')
        print(f'  score: {obj.score}')
        print(f'  bbox:  {obj.bbox}')

    # 6. OpenCV で BBox 描画
    result = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    for obj in objs:
        bbox = obj.bbox
        cv2.rectangle(result, (bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax),
                      (0, 0, 255), 2)
        text = f'{labels.get(obj.id, obj.id)} {obj.score:.2f}'
        cv2.putText(result, text, (bbox.xmin + 4, bbox.ymin + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    ```

    `--output` で結果画像を保存、`--display` で HDMI ディスプレイに表示できます。

=== "semantic_segmentation"

    ### セマンティックセグメンテーション

    DeepLab V3 で画像のピクセルごとにクラスを推定し、PASCAL VOC カラーマップで可視化します。

    ソースコード: [semantic_segmentation.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/semantic_segmentation.py)

    **使用 API**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_resized_input`, `common.set_input`, `segment.get_output`

    **処理の流れ**:

    1. `make_interpreter()` でインタープリタを作成
    2. `common.input_size()` でモデル入力サイズを取得
    3. `--keep_aspect_ratio` 指定時は `set_resized_input()` でアスペクト比を維持、それ以外は `set_input()` を使用
    4. `interpreter.invoke()` で推論実行
    5. `segment.get_output()` でセグメンテーション結果を取得
    6. PASCAL VOC カラーマップで各クラスを色分け
    7. 入力画像とマスクを横並びで結合

    ```python
    # 1. Edge TPU インタープリタ作成
    interpreter = make_interpreter(args.model, device=':0')
    interpreter.allocate_tensors()

    # 2. 入力サイズ取得
    width, height = common.input_size(interpreter)

    # 3. 画像のリサイズとセット
    img = Image.open(args.input)
    if args.keep_aspect_ratio:
        resized_img, _ = common.set_resized_input(
            interpreter, img.size,
            lambda size: img.resize(size, Image.LANCZOS))
    else:
        resized_img = img.resize((width, height), Image.LANCZOS)
        common.set_input(interpreter, resized_img)

    # 4. 推論実行
    interpreter.invoke()

    # 5. セグメンテーション結果取得
    result = segment.get_output(interpreter)
    if len(result.shape) == 3:
        result = np.argmax(result, axis=-1)

    # 6. PASCAL VOC カラーマップで色分け
    new_width, new_height = resized_img.size
    result = result[:new_height, :new_width]
    colormap = create_pascal_label_colormap()
    mask = colormap[result]

    # 7. 入力画像とマスクを横並びで結合
    resized_bgr = cv2.cvtColor(np.array(resized_img.convert('RGB')),
                                cv2.COLOR_RGB2BGR)
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_RGB2BGR)
    output_image = np.hstack([resized_bgr, mask_bgr])
    ```

    `--output` で結果画像を保存、`--display` で HDMI ディスプレイに表示できます。

=== "movenet_pose_estimation"

    ### 姿勢推定

    MoveNet で人体の 17 キーポイントを推定し、スケルトンを描画します。

    ソースコード: [movenet_pose_estimation.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/movenet_pose_estimation.py)

    **使用 API**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `common.output_tensor`

    **処理の流れ**:

    1. `make_interpreter()` でインタープリタを作成
    2. `common.input_size()` で入力サイズを取得し、PIL で画像をリサイズ
    3. `common.set_input()` でリサイズした画像をセット
    4. `interpreter.invoke()` で推論実行
    5. `common.output_tensor()` で出力テンソルを取得（17 × 3: y, x, score）
    6. キーポイントとスケルトン接続を OpenCV で描画

    ```python
    # 1. Edge TPU インタープリタ作成
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    # 2-3. 入力サイズ取得・リサイズ・セット
    img = Image.open(args.input)
    resized_img = img.resize(common.input_size(interpreter), Image.LANCZOS)
    common.set_input(interpreter, resized_img)

    # 4. 推論実行
    interpreter.invoke()

    # 5. 出力テンソル取得（17 キーポイント × [y, x, score]）
    pose = common.output_tensor(interpreter, 0).copy().reshape(17, 3)
    # pose[i] = [y, x, score]（正規化座標 0.0〜1.0）

    # 6. スケルトン描画
    _SKELETON = [
        (0, 1), (0, 2), (1, 3), (2, 4),       # head
        (5, 6),                                  # shoulders
        (5, 7), (7, 9), (6, 8), (8, 10),        # arms
        (5, 11), (6, 12),                        # torso
        (11, 12),                                # hips
        (11, 13), (13, 15), (12, 14), (14, 16),  # legs
    ]
    result = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
    h, w = result.shape[:2]
    for i, j in _SKELETON:
        if pose[i][2] > 0.2 and pose[j][2] > 0.2:
            y1, x1 = int(pose[i][0] * h), int(pose[i][1] * w)
            y2, x2 = int(pose[j][0] * h), int(pose[j][1] * w)
            cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for i in range(17):
        if pose[i][2] > 0.2:
            y, x = int(pose[i][0] * h), int(pose[i][1] * w)
            cv2.circle(result, (x, y), 4, (0, 0, 255), -1)
    ```

    17 キーポイント: nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle

    `--output` で結果画像を保存、`--display` で HDMI ディスプレイに表示できます。

=== "small_object_detection"

    ### タイルベース小物体検出

    大きな画像を複数サイズのタイルに分割して検出し、NMS で重複を除去します。NMS なしモデル（`_no_nms`）を使用することで、後処理を自前で実装し約 2 倍の高速化を実現しています。

    ソースコード: [small_object_detection.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/small_object_detection.py)

    **使用 API**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **処理の流れ**:

    1. `make_interpreter()` でインタープリタを作成、`read_label_file()` でラベル読み込み
    2. `--tile_sizes` で指定された複数のタイルサイズでループ
    3. 各タイルを切り出し、`set_resized_input()` でモデルに入力
    4. `detect.get_objects()` で検出結果を取得
    5. 検出結果の BBox をタイル位置基準から元画像基準に変換
    6. ラベルごとに NMS（Non-Maximum Suppression）を適用

    ```python
    # 1. インタープリタ作成・ラベル読み込み
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()
    labels = read_label_file(args.labels) if args.labels else {}

    img = Image.open(args.input).convert('RGB')
    img_size = img.size
    tile_sizes = [
        tuple(map(int, ts.split('x')))
        for ts in args.tile_sizes.split(',')
    ]

    # 2-5. タイルごとに検出、BBox を元画像座標に変換
    objects_by_label = {}
    for tile_size in tile_sizes:
        for tile_location in tiles_location_gen(img_size, tile_size,
                                                args.tile_overlap):
            tile = img.crop(tile_location)
            _, scale = common.set_resized_input(
                interpreter, tile.size,
                lambda size, t=tile: t.resize(size, Image.NEAREST))
            interpreter.invoke()
            objs = detect.get_objects(interpreter, args.score_threshold, scale)

            for obj in objs:
                bbox = [obj.bbox.xmin, obj.bbox.ymin,
                        obj.bbox.xmax, obj.bbox.ymax]
                # タイル座標 → 元画像座標に変換
                bbox[0] += tile_location[0]
                bbox[1] += tile_location[1]
                bbox[2] += tile_location[0]
                bbox[3] += tile_location[1]

                label = labels.get(obj.id, '')
                objects_by_label.setdefault(label, []).append(
                    Object(label, obj.score, bbox))

    # 6. ラベルごとに NMS を適用
    all_objects = []
    for label, objects in objects_by_label.items():
        idxs = non_max_suppression(objects, args.iou_threshold)
        for idx in idxs:
            all_objects.append(objects[idx])
    ```

    `--output` で結果画像を保存、`--display` で HDMI ディスプレイに表示できます。

=== "backprop_last_layer"

    ### 転移学習（最終層バックプロップ）

    Embedding extractor で特徴抽出し、SoftmaxRegression で最終層を学習します。花の画像データセットを使用。

    ソースコード: [backprop_last_layer.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/backprop_last_layer.py)

    **使用 API**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `classify.get_scores`, `classify.num_classes`, `SoftmaxRegression`

    **処理の流れ**:

    1. `get_image_paths()` でサブディレクトリ構造から画像パスとラベルを取得
    2. `shuffle_and_split()` でデータを train / val / test に分割
    3. `make_interpreter()` で Embedding extractor のインタープリタを作成
    4. 全画像の特徴ベクトルを `classify.get_scores()` で抽出
    5. `SoftmaxRegression` で最終層を SGD で学習（500 イテレーション）
    6. `model.serialize_model()` で学習済み重みを元モデルに結合して保存
    7. 保存したモデルでテストデータの精度を検証

    ```python
    # 1-2. データ読み込み・分割
    image_paths, labels, label_map = get_image_paths(data_dir)
    train_and_val, test_data = shuffle_and_split(image_paths, labels)

    # 3. Embedding extractor インタープリタ作成
    interpreter = make_interpreter(model_path, device=':0')
    interpreter.allocate_tensors()

    # 4. 特徴ベクトル抽出
    input_size = common.input_size(interpreter)
    feature_dim = classify.num_classes(interpreter)
    embeddings = np.empty((len(image_paths), feature_dim), dtype=np.float32)
    for idx, path in enumerate(image_paths):
        with Image.open(path) as img:
            img = img.convert('RGB').resize(input_size, Image.NEAREST)
            common.set_input(interpreter, img)
            interpreter.invoke()
            embeddings[idx, :] = classify.get_scores(interpreter)

    # 5. SoftmaxRegression で最終層を学習
    feature_dim = train_and_val['data_train'].shape[1]
    num_classes = np.max(train_and_val['labels_train']) + 1
    model = SoftmaxRegression(
        feature_dim, num_classes, weight_scale=5e-2, reg=0.0)
    model.train_with_sgd(
        train_and_val, num_iter=500, learning_rate=1e-2, batch_size=100)

    # 6. 学習済み重みを元モデルに結合して保存
    out_model_path = os.path.join(output_dir, 'retrained_model_edgetpu.tflite')
    with open(out_model_path, 'wb') as f:
        f.write(model.serialize_model(model_path))

    # 7. テストデータの精度検証
    retrained_interpreter = make_interpreter(out_model_path, device=':0')
    retrained_interpreter.allocate_tensors()
    test_embeddings = extract_embeddings(
        test_data['data_test'], retrained_interpreter)
    accuracy = np.mean(
        np.argmax(test_embeddings, axis=1) == test_data['labels_test'])
    ```

    **訓練データ**: `download-flower-photos` ターゲットでボード上にダウンロード（flower_photos: 5 クラス × 約 700 枚）

=== "imprinting_learning"

    ### 転移学習（weight imprinting）

    Weight imprinting で新しいクラスを追加学習します。バックプロップ不要で高速に学習可能。

    ソースコード: [imprinting_learning.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/imprinting_learning.py)

    **使用 API**: `ImprintingEngine`, `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `classify.get_scores`, `classify.get_classes`

    **処理の流れ**:

    1. `ImprintingEngine` でモデルから extractor を生成
    2. `make_interpreter()` で extractor のインタープリタを作成
    3. `read_data()` でデータセットを train / test に分割
    4. 訓練画像の特徴ベクトルを `classify.get_scores()` で抽出し、`engine.train()` で重みを更新
    5. `engine.serialize_model()` で学習済みモデルを保存
    6. 保存したモデルで `classify.get_classes()` を使い Top-1〜5 精度を評価

    ```python
    # 1. ImprintingEngine でモデルから extractor を生成
    engine = ImprintingEngine(args.model_path, keep_classes=args.keep_classes)

    # 2. extractor のインタープリタ作成
    extractor = make_interpreter(
        engine.serialize_extractor_model(), device=':0')
    extractor.allocate_tensors()
    shape = common.input_size(extractor)

    # 3. データセットの分割
    train_set, test_set = read_data(args.data, args.test_ratio)

    # 4. 特徴抽出 + 重み更新
    num_classes = engine.num_classes
    for class_id, (category, image_list) in enumerate(train_set.items()):
        images = prepare_images(
            image_list, os.path.join(args.data, category), shape)
        for tensor in images:
            common.set_input(extractor, tensor)
            extractor.invoke()
            embedding = classify.get_scores(extractor)
            engine.train(embedding, class_id=num_classes + class_id)

    # 5. 学習済みモデルを保存
    with open(args.output, 'wb') as f:
        f.write(engine.serialize_model())

    # 6. 保存したモデルで精度評価
    interpreter = make_interpreter(args.output)
    interpreter.allocate_tensors()
    size = common.input_size(interpreter)

    for category, image_list in test_set.items():
        for img_name in image_list:
            img = Image.open(os.path.join(args.data, category, img_name))
            img = img.resize(size, Image.NEAREST)
            common.set_input(interpreter, img)
            interpreter.invoke()
            candidates = classify.get_classes(
                interpreter, top_k=5, score_threshold=0.1)
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
