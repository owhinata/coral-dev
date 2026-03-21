cmake_minimum_required(VERSION 3.16)
project(pycoral-examples NONE)

# --- Download models and test data from google-coral/test_data ---
set(DATA_DIR "${CMAKE_CURRENT_BINARY_DIR}/data")
set(DATA_BASE_URL "https://github.com/google-coral/test_data/raw/master")

file(MAKE_DIRECTORY ${DATA_DIR})

# Models (Edge TPU compiled)
set(MODELS
    mobilenet_v2_1.0_224_inat_bird_quant_edgetpu.tflite
    ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite
    deeplabv3_mnv2_pascal_quant_edgetpu.tflite
    movenet_single_pose_lightning_ptq_edgetpu.tflite
    ssd_mobilenet_v2_coco_quant_no_nms_edgetpu.tflite
    mobilenet_v1_1.0_224_quant_embedding_extractor_edgetpu.tflite
    mobilenet_v1_1.0_224_l2norm_quant_edgetpu.tflite
)

# Test data (images + labels)
set(TEST_DATA
    parrot.jpg
    inat_bird_labels.txt
    grace_hopper.bmp
    coco_labels.txt
    bird.bmp
    squat.bmp
    kite_and_cold.jpg
    sunflower.bmp
    cat.bmp
)

foreach(file ${MODELS} ${TEST_DATA})
    if(NOT EXISTS "${DATA_DIR}/${file}")
        message(STATUS "Downloading ${file} ...")
        file(DOWNLOAD
            "${DATA_BASE_URL}/${file}"
            "${DATA_DIR}/${file}"
            SHOW_PROGRESS
        )
    endif()
endforeach()

# --- Deploy ---
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/coral-deploy.cmake)

set(DEPLOY_DIR /home/mendel/work/pycoral-examples)

# Collect deploy file mappings (flat: all files go to DEPLOY_DIR root)
set(DEPLOY_FILES
    "${CMAKE_CURRENT_SOURCE_DIR}/src/classify_image.py:classify_image.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/detect_image.py:detect_image.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/semantic_segmentation.py:semantic_segmentation.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/movenet_pose_estimation.py:movenet_pose_estimation.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/small_object_detection.py:small_object_detection.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/backprop_last_layer.py:backprop_last_layer.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/imprinting_learning.py:imprinting_learning.py"
)
foreach(file ${MODELS} ${TEST_DATA})
    list(APPEND DEPLOY_FILES "${DATA_DIR}/${file}:${file}")
endforeach()

coral_add_deploy_target(
    DEPLOY_DIR ${DEPLOY_DIR}
    FILES ${DEPLOY_FILES}
)

# --- Training data download targets (run on board) ---
add_custom_target(download-flower-photos
    COMMAND ${CMAKE_COMMAND} -E env
            "CORAL_IP=${CORAL_IP}"
            ${_CORAL_SCRIPTS_DIR}/run.sh
            "curl -L http://download.tensorflow.org/example_images/flower_photos.tgz -o /tmp/flower_photos.tgz"
    COMMAND ${CMAKE_COMMAND} -E env
            "CORAL_IP=${CORAL_IP}"
            ${_CORAL_SCRIPTS_DIR}/run.sh
            "tar xzf /tmp/flower_photos.tgz -C ${DEPLOY_DIR}"
    COMMAND ${CMAKE_COMMAND} -E env
            "CORAL_IP=${CORAL_IP}"
            ${_CORAL_SCRIPTS_DIR}/run.sh
            "rm /tmp/flower_photos.tgz"
    USES_TERMINAL
    COMMENT "Downloading flower_photos dataset to board"
)

add_custom_target(download-imprinting-data
    COMMAND ${CMAKE_COMMAND} -E env
            "CORAL_IP=${CORAL_IP}"
            ${_CORAL_SCRIPTS_DIR}/run.sh
            "wget -q https://dl.google.com/coral/sample_data/imprinting_data_script.tar.gz -O /tmp/imp.tar.gz"
    COMMAND ${CMAKE_COMMAND} -E env
            "CORAL_IP=${CORAL_IP}"
            ${_CORAL_SCRIPTS_DIR}/run.sh
            "tar xzf /tmp/imp.tar.gz -C /tmp"
    COMMAND ${CMAKE_COMMAND} -E env
            "CORAL_IP=${CORAL_IP}"
            ${_CORAL_SCRIPTS_DIR}/run.sh
            "/tmp/imprinting_data_script/download_imprinting_test_data.sh ${DEPLOY_DIR}"
    USES_TERMINAL
    COMMENT "Downloading imprinting dataset to board"
)

# --- Tests (ctest) ---
enable_testing()

add_test(NAME classify-image
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 classify_image.py -m mobilenet_v2_1.0_224_inat_bird_quant_edgetpu.tflite -l inat_bird_labels.txt -i parrot.jpg"
)
set_tests_properties(classify-image PROPERTIES LABELS "edgetpu;classify")

add_test(NAME detect-image
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 detect_image.py -m ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite -l coco_labels.txt -i grace_hopper.bmp"
)
set_tests_properties(detect-image PROPERTIES LABELS "edgetpu;detect")

add_test(NAME semantic-segmentation
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 semantic_segmentation.py -m deeplabv3_mnv2_pascal_quant_edgetpu.tflite -i bird.bmp --keep_aspect_ratio"
)
set_tests_properties(semantic-segmentation PROPERTIES LABELS "edgetpu;segmentation")

add_test(NAME movenet-pose
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 movenet_pose_estimation.py -m movenet_single_pose_lightning_ptq_edgetpu.tflite -i squat.bmp"
)
set_tests_properties(movenet-pose PROPERTIES LABELS "edgetpu;pose")

add_test(NAME small-object-detection
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 small_object_detection.py -m ssd_mobilenet_v2_coco_quant_no_nms_edgetpu.tflite -l coco_labels.txt -i kite_and_cold.jpg --tile_sizes 1352x900,500x500,250x250"
)
set_tests_properties(small-object-detection PROPERTIES LABELS "edgetpu;detect")

add_test(NAME backprop-last-layer
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 backprop_last_layer.py --embedding_extractor_path mobilenet_v1_1.0_224_quant_embedding_extractor_edgetpu.tflite --data_dir flower_photos --output_dir output"
)
set_tests_properties(backprop-last-layer PROPERTIES LABELS "edgetpu;transfer-learning")

add_test(NAME imprinting-learning
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 imprinting_learning.py --model_path mobilenet_v1_1.0_224_l2norm_quant_edgetpu.tflite --data open_image_v4_subset --output retrained_imprinting.tflite"
)
set_tests_properties(imprinting-learning PROPERTIES LABELS "edgetpu;transfer-learning")
