# toolchain-coral-aarch64.cmake
# Coral Dev Board (Mendel Linux) 向けクロスコンパイル設定
# Debian 標準の aarch64 クロスコンパイラを使用

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# Toolchain — Debian パッケージ: gcc-aarch64-linux-gnu
set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

# Compile flags
set(CMAKE_C_FLAGS   "-Wall -O2 -g" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS "-Wall -O2 -g" CACHE STRING "" FORCE)

# Dynamic linking (Mendel Linux has standard shared libraries)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build static libraries by default")

# Sysroot (optional — set if using a custom sysroot)
# set(CMAKE_SYSROOT /path/to/mendel-sysroot)

# Edge TPU paths on target
set(EDGETPU_INCLUDE_DIR "/usr/include" CACHE PATH "Edge TPU header directory on target")
set(EDGETPU_LIB_DIR "/usr/lib/aarch64-linux-gnu" CACHE PATH "Edge TPU library directory on target")

# Prevent CMake from searching host libraries
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
