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

    **APIs used**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `classify.get_classes`, `dataset.read_label_file`

    **Processing flow**:

    1. `make_interpreter()` creates an interpreter with Edge TPU delegate
    2. `common.input_size()` gets the model's input size, PIL resizes the image
    3. Check quantization parameters to determine if preprocessing is needed
    4. `common.set_input()` sets data to the input tensor
    5. `interpreter.invoke()` runs inference (1st run includes model load)
    6. `classify.get_classes()` retrieves classification results

    ```python
    # Check quantization parameters
    params = common.input_details(interpreter, 'quantization_parameters')
    scale = params['scales']
    zero_point = params['zero_points']
    if abs(scale * 128.0 - 1) < 1e-5 and abs(128.0 - zero_point) < 1e-5:
        common.set_input(interpreter, image)  # No preprocessing needed
    else:
        normalized = (np.asarray(image) - 128.0) / (128.0 * scale) + zero_point
        common.set_input(interpreter, normalized.astype(np.uint8))
    ```

=== "detect_image"

    ### Object Detection

    Detects objects in an image and draws bounding boxes with labels.

    **APIs used**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **Processing flow**:

    1. `common.set_resized_input()` resizes the image to model input size while returning the scale factor
    2. `detect.get_objects()` retrieves detection results above the score threshold
    3. OpenCV draws bounding boxes

    ```python
    # set_resized_input handles resize and scale calculation in one call
    _, scale = common.set_resized_input(
        interpreter, image.size,
        lambda size: image.resize(size, Image.LANCZOS))

    interpreter.invoke()
    objs = detect.get_objects(interpreter, args.threshold, scale)
    ```

    Use `--output` to save result images and `--display` to show on HDMI display.

=== "semantic_segmentation"

    ### Semantic Segmentation

    Uses DeepLab V3 to estimate per-pixel classes and visualize with PASCAL VOC colormap.

    **APIs used**: `edgetpu.make_interpreter`, `common.set_resized_input`, `common.set_input`, `segment.get_output`

    **Processing flow**:

    1. With `--keep_aspect_ratio`, `set_resized_input()` maintains aspect ratio
    2. `segment.get_output()` retrieves segmentation results
    3. PASCAL VOC colormap assigns colors to each class
    4. Input image and mask are concatenated side-by-side

    ```python
    result = segment.get_output(interpreter)
    if len(result.shape) == 3:
        result = np.argmax(result, axis=-1)

    colormap = create_pascal_label_colormap()
    mask = colormap[result]
    ```

=== "movenet_pose_estimation"

    ### Pose Estimation

    Estimates 17 human body keypoints using MoveNet and draws the skeleton.

    **APIs used**: `edgetpu.make_interpreter`, `common.input_size`, `common.set_input`, `common.output_tensor`

    **Processing flow**:

    1. `common.set_input()` sets the resized image
    2. `common.output_tensor()` retrieves the output tensor (17 x 3: y, x, score)
    3. Keypoints and skeleton connections are drawn with OpenCV

    ```python
    pose = common.output_tensor(interpreter, 0).copy().reshape(17, 3)
    # pose[i] = [y, x, score] (normalized coordinates)
    ```

    17 keypoints: nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle

=== "small_object_detection"

    ### Tile-based Small Object Detection

    Splits a large image into tiles of multiple sizes for detection, then applies NMS to remove duplicates.

    **APIs used**: `edgetpu.make_interpreter`, `common.set_resized_input`, `detect.get_objects`, `dataset.read_label_file`

    **Processing flow**:

    1. Loop over multiple tile sizes specified by `--tile_sizes`
    2. Crop each tile and feed to model via `set_resized_input()`
    3. Remap detection BBox from tile coordinates to original image coordinates
    4. Apply NMS (Non-Maximum Suppression) per label

    ```python
    # Detect per tile, remap BBox to original image coordinates
    for tile_location in tiles_location_gen(img_size, tile_size, overlap):
        tile = img.crop(tile_location)
        _, scale = common.set_resized_input(interpreter, tile.size, ...)
        interpreter.invoke()
        objs = detect.get_objects(interpreter, threshold, scale)
        # Remap BBox to original image coordinates
    ```

    Uses a no-NMS model (`_no_nms`) with custom post-processing for ~2x speedup.

=== "backprop_last_layer"

    ### Transfer Learning (Last Layer Backprop)

    Extracts features with an embedding extractor and trains the last layer using SoftmaxRegression. Uses the flower photos dataset.

    **APIs used**: `edgetpu.make_interpreter`, `common.set_input`, `classify.get_scores`, `SoftmaxRegression`

    **Processing flow**:

    1. `get_image_paths()` extracts image paths and labels from subdirectory structure
    2. Extract feature vectors for all images using the embedding extractor model
    3. Train the last layer with `SoftmaxRegression` using SGD (500 iterations)
    4. `model.serialize_model()` combines trained weights with the original model and saves
    5. Verify accuracy on test data with the saved model

    ```python
    # Feature extraction
    common.set_input(interpreter, img.resize(input_size, Image.NEAREST))
    interpreter.invoke()
    embeddings[idx, :] = classify.get_scores(interpreter)

    # Training
    model = SoftmaxRegression(feature_dim, num_classes, ...)
    model.train_with_sgd(train_and_val, num_iter=500, learning_rate=1e-2, ...)
    ```

    **Training data**: Download to board via the `download-flower-photos` target (flower_photos: 5 classes x ~700 images)

=== "imprinting_learning"

    ### Transfer Learning (Weight Imprinting)

    Adds new classes via weight imprinting. Fast learning without backpropagation.

    **APIs used**: `ImprintingEngine`, `edgetpu.make_interpreter`, `common.set_input`, `classify.get_scores`, `classify.get_classes`

    **Processing flow**:

    1. `ImprintingEngine` generates an extractor from the model
    2. Extract feature vectors from training images and update weights via `engine.train()`
    3. `engine.serialize_model()` saves the trained model
    4. Evaluate Top-1 through Top-5 accuracy with the saved model

    ```python
    engine = ImprintingEngine(args.model_path, keep_classes=args.keep_classes)
    extractor = make_interpreter(engine.serialize_extractor_model(), device=':0')
    extractor.allocate_tensors()

    # Training
    common.set_input(extractor, tensor)
    extractor.invoke()
    embedding = classify.get_scores(extractor)
    engine.train(embedding, class_id=num_classes + class_id)
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
