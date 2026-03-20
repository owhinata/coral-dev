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

# Imprinting models (Edge TPU only)
set(IMPRINTING_MODELS
    mobilenet_v1_1.0_224_l2norm_quant
)

file(MAKE_DIRECTORY ${MODEL_DIR})

# Download imprinting models
foreach(model ${IMPRINTING_MODELS})
    if(NOT EXISTS "${MODEL_DIR}/${model}_edgetpu.tflite")
        message(STATUS "Downloading ${model}_edgetpu.tflite ...")
        file(DOWNLOAD
            "${MODEL_BASE_URL}/${model}_edgetpu.tflite"
            "${MODEL_DIR}/${model}_edgetpu.tflite"
            SHOW_PROGRESS
        )
    endif()
endforeach()

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
    "${CMAKE_CURRENT_SOURCE_DIR}/src/softmax_regression_benchmark.py:softmax_regression_benchmark.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/imprinting_benchmark.py:imprinting_benchmark.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/online_imprinting_benchmark.py:online_imprinting_benchmark.py"
)
foreach(model ${IMPRINTING_MODELS})
    list(APPEND DEPLOY_FILES
        "${MODEL_DIR}/${model}_edgetpu.tflite:${model}_edgetpu.tflite"
    )
endforeach()
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

find_program(PYTHON3 python3 HINTS ${CMAKE_CURRENT_LIST_DIR}/../../.venv/bin NO_DEFAULT_PATH)
if(NOT PYTHON3)
    find_program(PYTHON3 python3)
endif()

add_test(NAME inference-cpu-local
    COMMAND ${PYTHON3} ${CMAKE_CURRENT_SOURCE_DIR}/src/inference_benchmark.py
            --device cpu --model-dir ${MODEL_DIR}
)
set_tests_properties(inference-cpu-local PROPERTIES LABELS "cpu;inference;local")

add_test(NAME softmax-regression
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 softmax_regression_benchmark.py"
)
set_tests_properties(softmax-regression PROPERTIES LABELS "cpu;softmax-regression")

add_test(NAME imprinting
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 imprinting_benchmark.py"
)
set_tests_properties(imprinting PROPERTIES LABELS "edgetpu;imprinting")

add_test(NAME online-imprinting
    COMMAND ${_CORAL_SCRIPTS_DIR}/run.sh
            "cd ${DEPLOY_DIR} && python3 online_imprinting_benchmark.py"
)
set_tests_properties(online-imprinting PROPERTIES LABELS "edgetpu;imprinting")
