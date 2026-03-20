# toolchain-coral-aarch64.cmake
# Coral Dev Board (Mendel Linux) 向けクロスコンパイル設定
# ARM GNU Toolchain 8.3-2019.03 (glibc 2.28, Mendel Linux / Debian 10 互換)

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# Toolchain path (setup-toolchain.sh でダウンロード)
file(REAL_PATH "${CMAKE_CURRENT_LIST_DIR}/../toolchain/gcc-arm-8.3-2019.03-x86_64-aarch64-linux-gnu" TC_ROOT)
set(TC_BIN "${TC_ROOT}/bin")

if(NOT EXISTS "${TC_BIN}/aarch64-linux-gnu-gcc")
    message(FATAL_ERROR
        "Cross-compiler not found at ${TC_BIN}\n"
        "Run: ./cmake/setup-toolchain.sh")
endif()

set(CMAKE_C_COMPILER   "${TC_BIN}/aarch64-linux-gnu-gcc")
set(CMAKE_CXX_COMPILER "${TC_BIN}/aarch64-linux-gnu-g++")

# Compile flags
set(CMAKE_C_FLAGS   "-Wall -O2 -g" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS "-Wall -O2 -g" CACHE STRING "" FORCE)

# Dynamic linking (Mendel Linux has standard shared libraries)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build static libraries by default")

# Edge TPU paths on target
set(EDGETPU_INCLUDE_DIR "/usr/include" CACHE PATH "Edge TPU header directory on target")
set(EDGETPU_LIB_DIR "/usr/lib/aarch64-linux-gnu" CACHE PATH "Edge TPU library directory on target")

# Prevent CMake from searching host libraries
set(CMAKE_FIND_ROOT_PATH "${TC_ROOT}/aarch64-linux-gnu")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
