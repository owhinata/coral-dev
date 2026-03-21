# PyCoral API Examples

A self-contained port of [pycoral](https://github.com/google-coral/pycoral) [examples](https://github.com/google-coral/pycoral/tree/master/examples). The purpose is to learn [PyCoral API](https://gweb-coral-full.uc.r.appspot.com/docs/reference/py/) usage. It targets 7 examples that can run on a single Edge TPU.

| Example | Description | Key APIs |
|---------|-------------|----------|
| classify_image | Image classification | `classify.get_classes`, `common.input_size`, `common.set_input` |
| detect_image | Object detection | `detect.get_objects`, `common.set_resized_input` |
| semantic_segmentation | Semantic segmentation | `segment.get_output`, `common.set_resized_input` |
| movenet_pose_estimation | Pose estimation (17 keypoints) | `common.output_tensor`, `common.set_input` |
| small_object_detection | Tile-based small object detection + NMS | `detect.get_objects`, `common.set_resized_input` |
| backprop_last_layer | Transfer learning (last layer backprop) | `SoftmaxRegression`, `classify.get_scores` |
| imprinting_learning | Transfer learning (weight imprinting) | `ImprintingEngine`, `classify.get_classes` |

## Prerequisites

- CMake 3.16 or later
- Internet connection (only for initial model/test data download)
- pycoral / tflite-runtime installed on Coral Dev Board (pre-installed on Mendel Linux)
- `python3-opencv` installed on the board if using `--display` flag for image output examples

## Build, Deploy, and Run

### Download Models and Test Data

```bash
cmake -B build/pycoral-examples -S apps/pycoral-examples
```

Downloaded files are saved to `build/pycoral-examples/data/`.

### Deploy to Board

```bash
cmake --build build/pycoral-examples --target deploy
```

Scripts and data are transferred to `/home/mendel/work/pycoral-examples/` on the board.

### Run Examples (ctest)

```bash
# Run all examples (excluding transfer-learning)
ctest --test-dir build/pycoral-examples -V -E "(backprop|imprinting)"

# Classification only
ctest --test-dir build/pycoral-examples -V -R classify

# Detection examples only
ctest --test-dir build/pycoral-examples -V -L detect
```

### Running Transfer Learning

Transfer learning examples require downloading training data to the board first.

```bash
# For backprop_last_layer
cmake --build build/pycoral-examples --target download-flower-photos
ctest --test-dir build/pycoral-examples -V -R backprop

# For imprinting_learning
cmake --build build/pycoral-examples --target download-imprinting-data
ctest --test-dir build/pycoral-examples -V -R imprinting
```

---

## Example Walkthrough

=== "classify_image"

    ### Image Classification

    Classifies a bird image with MobileNet V2 and outputs the top-k class labels and scores.

    Source code: [classify_image.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/classify_image.py)

    **APIs used**: `edgetpu.make_interpreter`, `common.input_size`, `common.input_details`, `common.set_input`, `classify.get_classes`, `dataset.read_label_file`

    **Processing flow**:

    1. `read_label_file()` loads the label file
    2. `make_interpreter()` creates an interpreter with Edge TPU delegate
    3. `common.input_size()` gets the model's input size, PIL resizes the image
    4. Check quantization parameters to determine if preprocessing is needed
    5. `common.set_input()` sets data to the input tensor
    6. `interpreter.invoke()` runs inference (1st run includes model load)
    7. `classify.get_classes()` retrieves classification results

    ```python
    # 1. Load labels
    labels = read_label_file(args.labels) if args.labels else {}

    # 2. Create Edge TPU interpreter
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    # 3. Get input size and resize image
    if common.input_details(interpreter, 'dtype') != np.uint8:
        raise ValueError('Only support uint8 input type.')
    size = common.input_size(interpreter)
    image = Image.open(args.input).convert('RGB').resize(size, Image.LANCZOS)

    # 4. Check quantization parameters
    params = common.input_details(interpreter, 'quantization_parameters')
    scale = params['scales']
    zero_point = params['zero_points']

    # 5. Set input tensor (determine if preprocessing is needed)
    if abs(scale * 128.0 - 1) < 1e-5 and abs(128.0 - zero_point) < 1e-5:
        common.set_input(interpreter, image)  # No preprocessing needed
    else:
        normalized = (np.asarray(image) - 128.0) / (128.0 * scale) + zero_point
        np.clip(normalized, 0, 255, out=normalized)
        common.set_input(interpreter, normalized.astype(np.uint8))

    # 6. Run inference
    interpreter.invoke()

    # 7. Get classification results
    classes = classify.get_classes(interpreter, args.top_k, args.threshold)
    for c in classes:
        print(f'{labels.get(c.id, c.id)}: {c.score:.5f}')
    ```

=== "detect_image"

    ### Object Detection

    Detects objects in an image and draws bounding boxes with labels.

    Source code: [detect_image.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/detect_image.py)

    **APIs used**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **Processing flow**:

    1. `read_label_file()` loads the label file
    2. `make_interpreter()` creates the interpreter
    3. `common.set_resized_input()` resizes the image to model input size while returning the scale factor
    4. `interpreter.invoke()` runs inference
    5. `detect.get_objects()` retrieves detection results above the score threshold
    6. OpenCV draws bounding boxes

    ```python
    # 1. Load labels
    labels = read_label_file(args.labels) if args.labels else {}

    # 2. Create Edge TPU interpreter
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    # 3. set_resized_input handles resize and scale calculation in one call
    image = Image.open(args.input)
    _, scale = common.set_resized_input(
        interpreter, image.size,
        lambda size: image.resize(size, Image.LANCZOS))

    # 4. Run inference
    interpreter.invoke()

    # 5. Get detection results
    objs = detect.get_objects(interpreter, args.threshold, scale)
    for obj in objs:
        print(f'{labels.get(obj.id, obj.id)}')
        print(f'  id:    {obj.id}')
        print(f'  score: {obj.score}')
        print(f'  bbox:  {obj.bbox}')

    # 6. Draw bounding boxes with OpenCV
    result = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    for obj in objs:
        bbox = obj.bbox
        cv2.rectangle(result, (bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax),
                      (0, 0, 255), 2)
        text = f'{labels.get(obj.id, obj.id)} {obj.score:.2f}'
        cv2.putText(result, text, (bbox.xmin + 4, bbox.ymin + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    ```

    Use `--output` to save result images and `--display` to show on HDMI display.

=== "semantic_segmentation"

    ### Semantic Segmentation

    Uses DeepLab V3 to estimate per-pixel classes and visualize with PASCAL VOC colormap.

    Source code: [semantic_segmentation.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/semantic_segmentation.py)

    **APIs used**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_resized_input`, `common.set_input`, `segment.get_output`

    **Processing flow**:

    1. `make_interpreter()` creates the interpreter
    2. `common.input_size()` gets the model input size
    3. With `--keep_aspect_ratio`, `set_resized_input()` maintains aspect ratio; otherwise uses `set_input()`
    4. `interpreter.invoke()` runs inference
    5. `segment.get_output()` retrieves segmentation results
    6. PASCAL VOC colormap assigns colors to each class
    7. Input image and mask are concatenated side-by-side

    ```python
    # 1. Create Edge TPU interpreter
    interpreter = make_interpreter(args.model, device=':0')
    interpreter.allocate_tensors()

    # 2. Get input size
    width, height = common.input_size(interpreter)

    # 3. Resize and set input image
    img = Image.open(args.input)
    if args.keep_aspect_ratio:
        resized_img, _ = common.set_resized_input(
            interpreter, img.size,
            lambda size: img.resize(size, Image.LANCZOS))
    else:
        resized_img = img.resize((width, height), Image.LANCZOS)
        common.set_input(interpreter, resized_img)

    # 4. Run inference
    interpreter.invoke()

    # 5. Get segmentation results
    result = segment.get_output(interpreter)
    if len(result.shape) == 3:
        result = np.argmax(result, axis=-1)

    # 6. Apply PASCAL VOC colormap
    new_width, new_height = resized_img.size
    result = result[:new_height, :new_width]
    colormap = create_pascal_label_colormap()
    mask = colormap[result]

    # 7. Concatenate input image and mask side-by-side
    resized_bgr = cv2.cvtColor(np.array(resized_img.convert('RGB')),
                                cv2.COLOR_RGB2BGR)
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_RGB2BGR)
    output_image = np.hstack([resized_bgr, mask_bgr])
    ```

    Use `--output` to save result images and `--display` to show on HDMI display.

=== "movenet_pose_estimation"

    ### Pose Estimation

    Estimates 17 human body keypoints using MoveNet and draws the skeleton.

    Source code: [movenet_pose_estimation.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/movenet_pose_estimation.py)

    **APIs used**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `common.output_tensor`

    **Processing flow**:

    1. `make_interpreter()` creates the interpreter
    2. `common.input_size()` gets input size and resizes the image with PIL
    3. `common.set_input()` sets the resized image
    4. `interpreter.invoke()` runs inference
    5. `common.output_tensor()` retrieves the output tensor (17 x 3: y, x, score)
    6. Keypoints and skeleton connections are drawn with OpenCV

    ```python
    # 1. Create Edge TPU interpreter
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()

    # 2-3. Get input size, resize, and set input
    img = Image.open(args.input)
    resized_img = img.resize(common.input_size(interpreter), Image.LANCZOS)
    common.set_input(interpreter, resized_img)

    # 4. Run inference
    interpreter.invoke()

    # 5. Get output tensor (17 keypoints x [y, x, score])
    pose = common.output_tensor(interpreter, 0).copy().reshape(17, 3)
    # pose[i] = [y, x, score] (normalized coordinates 0.0-1.0)

    # 6. Draw skeleton
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

    17 keypoints: nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle

    Use `--output` to save result images and `--display` to show on HDMI display.

=== "small_object_detection"

    ### Tile-based Small Object Detection

    Splits a large image into tiles of multiple sizes for detection, then applies NMS to remove duplicates. Uses a no-NMS model (`_no_nms`) with custom post-processing for ~2x speedup.

    Source code: [small_object_detection.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/small_object_detection.py)

    **APIs used**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **Processing flow**:

    1. `make_interpreter()` creates the interpreter, `read_label_file()` loads labels
    2. Loop over multiple tile sizes specified by `--tile_sizes`
    3. Crop each tile and feed to model via `set_resized_input()`
    4. `detect.get_objects()` retrieves detection results
    5. Remap detection BBox from tile coordinates to original image coordinates
    6. Apply NMS (Non-Maximum Suppression) per label

    ```python
    # 1. Create interpreter and load labels
    interpreter = make_interpreter(args.model)
    interpreter.allocate_tensors()
    labels = read_label_file(args.labels) if args.labels else {}

    img = Image.open(args.input).convert('RGB')
    img_size = img.size
    tile_sizes = [
        tuple(map(int, ts.split('x')))
        for ts in args.tile_sizes.split(',')
    ]

    # 2-5. Detect per tile, remap BBox to original image coordinates
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
                # Remap tile coordinates to original image coordinates
                bbox[0] += tile_location[0]
                bbox[1] += tile_location[1]
                bbox[2] += tile_location[0]
                bbox[3] += tile_location[1]

                label = labels.get(obj.id, '')
                objects_by_label.setdefault(label, []).append(
                    Object(label, obj.score, bbox))

    # 6. Apply NMS per label
    all_objects = []
    for label, objects in objects_by_label.items():
        idxs = non_max_suppression(objects, args.iou_threshold)
        for idx in idxs:
            all_objects.append(objects[idx])
    ```

    Use `--output` to save result images and `--display` to show on HDMI display.

=== "backprop_last_layer"

    ### Transfer Learning (Last Layer Backprop)

    Extracts features with an embedding extractor and trains the last layer using SoftmaxRegression. Uses the flower photos dataset.

    Source code: [backprop_last_layer.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/backprop_last_layer.py)

    **APIs used**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `classify.get_scores`, `classify.num_classes`, `SoftmaxRegression`

    **Processing flow**:

    1. `get_image_paths()` extracts image paths and labels from subdirectory structure
    2. `shuffle_and_split()` splits data into train / val / test sets
    3. `make_interpreter()` creates the embedding extractor interpreter
    4. Extract feature vectors for all images using `classify.get_scores()`
    5. Train the last layer with `SoftmaxRegression` using SGD (500 iterations)
    6. `model.serialize_model()` combines trained weights with the original model and saves
    7. Verify accuracy on test data with the saved model

    ```python
    # 1-2. Load data and split
    image_paths, labels, label_map = get_image_paths(data_dir)
    train_and_val, test_data = shuffle_and_split(image_paths, labels)

    # 3. Create embedding extractor interpreter
    interpreter = make_interpreter(model_path, device=':0')
    interpreter.allocate_tensors()

    # 4. Extract feature vectors
    input_size = common.input_size(interpreter)
    feature_dim = classify.num_classes(interpreter)
    embeddings = np.empty((len(image_paths), feature_dim), dtype=np.float32)
    for idx, path in enumerate(image_paths):
        with Image.open(path) as img:
            img = img.convert('RGB').resize(input_size, Image.NEAREST)
            common.set_input(interpreter, img)
            interpreter.invoke()
            embeddings[idx, :] = classify.get_scores(interpreter)

    # 5. Train last layer with SoftmaxRegression
    feature_dim = train_and_val['data_train'].shape[1]
    num_classes = np.max(train_and_val['labels_train']) + 1
    model = SoftmaxRegression(
        feature_dim, num_classes, weight_scale=5e-2, reg=0.0)
    model.train_with_sgd(
        train_and_val, num_iter=500, learning_rate=1e-2, batch_size=100)

    # 6. Combine trained weights with original model and save
    out_model_path = os.path.join(output_dir, 'retrained_model_edgetpu.tflite')
    with open(out_model_path, 'wb') as f:
        f.write(model.serialize_model(model_path))

    # 7. Verify accuracy on test data
    retrained_interpreter = make_interpreter(out_model_path, device=':0')
    retrained_interpreter.allocate_tensors()
    test_embeddings = extract_embeddings(
        test_data['data_test'], retrained_interpreter)
    accuracy = np.mean(
        np.argmax(test_embeddings, axis=1) == test_data['labels_test'])
    ```

    **Training data**: Download to board via the `download-flower-photos` target (flower_photos: 5 classes x ~700 images)

=== "imprinting_learning"

    ### Transfer Learning (Weight Imprinting)

    Adds new classes via weight imprinting. Fast learning without backpropagation.

    Source code: [imprinting_learning.py](https://github.com/owhinata/coral-dev/blob/99fd61ac/apps/pycoral-examples/src/imprinting_learning.py)

    **APIs used**: `ImprintingEngine`, `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `classify.get_scores`, `classify.get_classes`

    **Processing flow**:

    1. `ImprintingEngine` generates an extractor from the model
    2. `make_interpreter()` creates the extractor interpreter
    3. `read_data()` splits the dataset into train / test sets
    4. Extract feature vectors from training images using `classify.get_scores()` and update weights via `engine.train()`
    5. `engine.serialize_model()` saves the trained model
    6. Evaluate Top-1 through Top-5 accuracy using `classify.get_classes()` with the saved model

    ```python
    # 1. Generate extractor from model via ImprintingEngine
    engine = ImprintingEngine(args.model_path, keep_classes=args.keep_classes)

    # 2. Create extractor interpreter
    extractor = make_interpreter(
        engine.serialize_extractor_model(), device=':0')
    extractor.allocate_tensors()
    shape = common.input_size(extractor)

    # 3. Split dataset
    train_set, test_set = read_data(args.data, args.test_ratio)

    # 4. Extract features and update weights
    num_classes = engine.num_classes
    for class_id, (category, image_list) in enumerate(train_set.items()):
        images = prepare_images(
            image_list, os.path.join(args.data, category), shape)
        for tensor in images:
            common.set_input(extractor, tensor)
            extractor.invoke()
            embedding = classify.get_scores(extractor)
            engine.train(embedding, class_id=num_classes + class_id)

    # 5. Save trained model
    with open(args.output, 'wb') as f:
        f.write(engine.serialize_model())

    # 6. Evaluate accuracy with saved model
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

    **Training data**: Download to board via the `download-imprinting-data` target (open_image_v4_subset: 10 categories x 20 images)

---

## CMake Targets / ctest List { #cmake-targets }

### Configuration

```bash
cmake -B build/pycoral-examples -S apps/pycoral-examples
```

### Target List

| Target | Command | Description |
|--------|---------|-------------|
| `deploy` | `cmake --build build/pycoral-examples --target deploy` | Transfer scripts + data to board |
| `download-flower-photos` | `cmake --build build/pycoral-examples --target download-flower-photos` | Download flower_photos dataset on board |
| `download-imprinting-data` | `cmake --build build/pycoral-examples --target download-imprinting-data` | Download imprinting dataset on board |

### ctest List

| Test Name | Labels | Description |
|-----------|--------|-------------|
| `classify-image` | `edgetpu`, `classify` | Image classification |
| `detect-image` | `edgetpu`, `detect` | Object detection |
| `semantic-segmentation` | `edgetpu`, `segmentation` | Semantic segmentation |
| `movenet-pose` | `edgetpu`, `pose` | Pose estimation |
| `small-object-detection` | `edgetpu`, `detect` | Tile-based small object detection |
| `backprop-last-layer` | `edgetpu`, `transfer-learning` | Transfer learning (backprop) |
| `imprinting-learning` | `edgetpu`, `transfer-learning` | Transfer learning (imprinting) |

### Connection Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CORAL_IP` | (empty = auto-detect via mdt) | Coral Dev Board IP address |

## Results

=== "Inference"

    ### classify_image

    | Item | Value |
    |------|-------|
    | Model | mobilenet_v2_1.0_224_inat_bird_quant_edgetpu |
    | 1st inference (includes model load) | 14.70 ms |
    | 2nd inference | 3.37 ms |

    | Label | Score |
    |-------|-------|
    | Ara macao (Scarlet Macaw) | 0.75781 |
    | Platycercus elegans (Crimson Rosella) | 0.07422 |
    | Coracias caudatus (Lilac-breasted Roller) | 0.01562 |

    ### detect_image

    | Item | Value |
    |------|-------|
    | Model | ssd_mobilenet_v2_coco_quant_postprocess_edgetpu |
    | 1st inference (includes model load) | 36.96 ms |
    | 2nd inference | 12.58 ms |

    | Label | Score | BBox |
    |-------|-------|------|
    | tie | 0.840 | (227, 419, 292, 541) |
    | person | 0.805 | (2, 4, 513, 595) |

    ### semantic_segmentation

    | Item | Value |
    |------|-------|
    | Model | deeplabv3_mnv2_pascal_quant_edgetpu |
    | 1st inference (includes model load) | 223.14 ms |
    | 2nd inference | 220.26 ms |

    ### movenet_pose_estimation

    | Item | Value |
    |------|-------|
    | Model | movenet_single_pose_lightning_ptq_edgetpu |
    | 1st inference (includes model load) | 29.12 ms |
    | 2nd inference | 26.90 ms |

    | Keypoint | Coordinates (x, y) | Score |
    |----------|---------------------|-------|
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

    | Item | Value |
    |------|-------|
    | Model | ssd_mobilenet_v2_coco_quant_no_nms_edgetpu |
    | Tile sizes | 1352x900, 500x500, 250x250 |
    | Detection time | 922.44 ms |
    | Detected | 18 objects (kite: 7, person: 10, backpack: 1) |

=== "Transfer Learning"

    ### backprop_last_layer

    | Item | Value |
    |------|-------|
    | Model | mobilenet_v1_1.0_224_quant_embedding_extractor_edgetpu |
    | Dataset | flower_photos (5 classes x ~700 images) |
    | Preprocessing time | 38.48 sec |
    | Training time | 7.64 sec |
    | Total time | 50.34 sec |
    | Test accuracy | 89.65% |

    ### imprinting_learning

    | Item | Value |
    |------|-------|
    | Model | mobilenet_v1_1.0_224_l2norm_quant_edgetpu |
    | Dataset | open_image_v4_subset (10 categories x 20 images) |
    | Training time | 36576.60 ms |

    | Top-k | Accuracy |
    |-------|----------|
    | Top 1 | 98% |
    | Top 2 | 100% |
    | Top 3 | 100% |
    | Top 4 | 100% |
    | Top 5 | 100% |
