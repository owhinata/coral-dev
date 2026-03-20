# CoreMark

[CoreMark](https://github.com/eembc/coremark) is a CPU benchmark provided by EEMBC. `apps/coremark/` uses CMake FetchContent to automatically fetch the upstream source and builds with **no custom source files** — only a CMakeLists.txt.

## Prerequisites

- aarch64 cross-compiler extracted in `toolchain/`
- Host OS: x86_64 Linux
- CMake 3.16 or later
- Internet connection (only for the initial FetchContent download)

## Design

### Why the posix/ port

The upstream CoreMark `posix/` port operates with the following settings:

- `USE_CLOCK=0`, `HAS_TIME_H=1` → uses `clock_gettime(CLOCK_REALTIME)` for timing
- `SEED_METHOD=SEED_ARG` → seed configurable via command-line arguments (auto-detect when no arguments)
- `MEM_METHOD=MEM_MALLOC` → standard heap allocation

This works out of the box on the Coral Dev Board's Mendel Linux (Debian-based / glibc).

### Why no custom source files are needed

- `CORETIMETYPE` is only used within `core_portme.c` (`core_main.c` uses `CORE_TICKS`=`clock_t`)
- The posix port's `core_portme.c` works as-is
- Configuration differences (ITERATIONS, etc.) can be handled via runtime arguments or CMake `-D`
- Only `FLAGS_STR` needs to be defined from CMake (upstream Makefile also passes it via `-D`)

### -O2 optimization

`-O2` is explicitly specified to produce meaningful benchmark results. It is also reflected in `FLAGS_STR`, which appears in the CoreMark report output as the compiler flags used.

## CMakeLists.txt

**`apps/coremark/CMakeLists.txt`**:

```cmake
cmake_minimum_required(VERSION 3.16)
project(coremark C)

# --- Fetch upstream CoreMark source ---
include(FetchContent)
FetchContent_Declare(
    coremark_src
    GIT_REPOSITORY https://github.com/eembc/coremark.git
    GIT_TAG        main
    GIT_SHALLOW    TRUE
)
FetchContent_GetProperties(coremark_src)
if(NOT coremark_src_POPULATED)
    FetchContent_Populate(coremark_src)
endif()

# --- Build the CoreMark benchmark ---
add_executable(coremark
    ${coremark_src_SOURCE_DIR}/core_list_join.c
    ${coremark_src_SOURCE_DIR}/core_main.c
    ${coremark_src_SOURCE_DIR}/core_matrix.c
    ${coremark_src_SOURCE_DIR}/core_state.c
    ${coremark_src_SOURCE_DIR}/core_util.c
    ${coremark_src_SOURCE_DIR}/posix/core_portme.c
)

target_include_directories(coremark PRIVATE
    ${coremark_src_SOURCE_DIR}
    ${coremark_src_SOURCE_DIR}/posix
)

# Benchmark-meaningful optimization
target_compile_options(coremark PRIVATE -O2)

# Suppress -Werror from toolchain for upstream code
target_compile_options(coremark PRIVATE -Wno-error)

# FLAGS_STR: required by posix/core_portme.h for benchmark report output
target_compile_definitions(coremark PRIVATE "FLAGS_STR=\"-O2\"")

# Deploy / Run
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/coral-deploy.cmake)

coral_add_deploy_target(
    DEPLOY_DIR /home/mendel/work/coremark
    DEPENDS coremark
    FILES "$<TARGET_FILE:coremark>:coremark"
)

coral_add_run_target(
    COMMAND /home/mendel/work/coremark/coremark
)
```

FetchContent automatically downloads the CoreMark source at build time, so no manual source placement is needed. It builds the 5 core files plus `posix/core_portme.c` from the sources extracted into `coremark_src_SOURCE_DIR`.

## Build

Run from the repository root directory.

```bash
cmake -B build/coremark -S apps/coremark \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/coremark
```

### Verify the generated ELF

```bash
file build/coremark/coremark
```

Expected output:

```
coremark: ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), dynamically linked, ...
```

## Deploy and Run

The CMake `deploy` / `run` targets handle transfer and execution in one command:

```bash
cmake --build build/coremark --target deploy
cmake --build build/coremark --target run
```

Example output:

```
2K performance run parameters for coremark.
CoreMark Size    : 666
Total ticks      : 12187
Total time (secs): 12.187000
Iterations/Sec   : 4923.278904
Iterations       : 60000
Compiler version : GCC8.3.0
Compiler flags   : -O2
Memory location  : Please put data memory location here
		(e.g. code in flash, data on heap etc)
seedcrc          : 0xe9f5
[0]crclist       : 0xe714
[0]crcmatrix     : 0x1fd7
[0]crcstate      : 0x8e3a
[0]crcfinal      : 0xbd59
Correct operation validated. See README.md for run and reporting rules.
CoreMark 1.0 : 4923.278904 / GCC8.3.0 -O2 / Heap
```

## Runtime Options

CoreMark runs with default settings (auto-detect ITERATIONS, auto-select SEED) when executed without arguments.

```
coremark <seed1> <seed2> <seed3> <iterations>
```

| Argument | Description | Default |
|----------|-------------|---------|
| seed1, seed2, seed3 | Benchmark input seeds | Auto-selected (validation/performance/profile) |
| iterations | Number of iterations | Auto (minimum value for ~10 seconds execution) |

Example: run with 50000 iterations:

```bash
cmake/scripts/run.sh '/home/mendel/work/coremark/coremark 0 0 0x66 50000'
```

---

## CMake Targets { #cmake-targets }

### Configuration

```bash
cmake -B build/coremark -S apps/coremark \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
```

### Target List

| Target | Command | Description |
|--------|---------|-------------|
| (default) | `cmake --build build/coremark` | Build C binary |
| `deploy` | `cmake --build build/coremark --target deploy` | Build + transfer to board |
| `run` | `cmake --build build/coremark --target run` | Run remotely on board |

### Connection Settings

Customize connection parameters via CMake cache variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CORAL_IP` | (empty = auto-detect via mdt) | Coral Dev Board IP address |

## Future Extensions

### Multi-threaded support

To run CoreMark in multi-threaded mode:

1. Copy the upstream `posix/core_portme.c` to `apps/coremark/src/core_portme.c`
2. Change the source path in CMakeLists.txt to `src/core_portme.c`
3. Add `-DMULTITHREAD=4 -DUSE_PTHREAD=1` in CMake and add `pthread` to `target_link_libraries`
