cmake_minimum_required(VERSION 3.16)
project(face-sharp NONE)

set(PYTHON3 "${CMAKE_CURRENT_LIST_DIR}/../../.venv/bin/python" CACHE FILEPATH
    "Python3 interpreter (must have tensorflow, numpy)")

set(DATA_DIR "${CMAKE_CURRENT_BINARY_DIR}/data")
set(DATA_BASE_URL "https://github.com/google-coral/test_data/raw/master")

file(MAKE_DIRECTORY ${DATA_DIR})

# --- Download face detection model ---
set(FACE_MODEL "ssd_mobilenet_v2_face_quant_postprocess_edgetpu.tflite")

if(NOT EXISTS "${DATA_DIR}/${FACE_MODEL}")
    message(STATUS "Downloading ${FACE_MODEL} ...")
    file(DOWNLOAD
        "${DATA_BASE_URL}/${FACE_MODEL}"
        "${DATA_DIR}/${FACE_MODEL}"
        SHOW_PROGRESS
    )
endif()

# --- Download pre-trained ESPCN x3 and convert to TFLite ---
set(ESPCN_PB "${DATA_DIR}/ESPCN_x3.pb")
set(ESPCN_TFLITE "${DATA_DIR}/espcn_x3.tflite")
set(ESPCN_PB_URL "https://raw.githubusercontent.com/fannymonori/TF-ESPCN/master/export/ESPCN_x3.pb")
set(CONVERT_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/models/convert_espcn.py")

if(NOT EXISTS "${ESPCN_PB}")
    message(STATUS "Downloading ESPCN_x3.pb ...")
    file(DOWNLOAD
        "${ESPCN_PB_URL}"
        "${ESPCN_PB}"
        SHOW_PROGRESS
    )
endif()

if(NOT EXISTS "${ESPCN_TFLITE}")
    message(STATUS "Converting ESPCN_x3.pb to TFLite ...")
    execute_process(
        COMMAND ${PYTHON3} "${CONVERT_SCRIPT}" "${ESPCN_PB}" "${ESPCN_TFLITE}"
        RESULT_VARIABLE CONVERT_RESULT
    )
    if(NOT CONVERT_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to convert ESPCN model to TFLite")
    endif()
endif()

# --- Deploy ---
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/coral-deploy.cmake)

set(DEPLOY_DIR /home/mendel/work/face-sharp)

set(DEPLOY_FILES
    "${CMAKE_CURRENT_SOURCE_DIR}/src/face_sharp.py:face_sharp.py"
    "${ESPCN_TFLITE}:espcn_x3.tflite"
    "${DATA_DIR}/${FACE_MODEL}:${FACE_MODEL}"
)

coral_add_deploy_target(
    DEPLOY_DIR ${DEPLOY_DIR}
    FILES ${DEPLOY_FILES}
)

# --- Run ---
coral_add_run_target(
    COMMAND "python3 ${DEPLOY_DIR}/face_sharp.py"
)
