# Hello World

A minimal application that runs on the Coral Dev Board.
Use this to verify the cross-compile, deploy, and run workflow.

## Source Code

### main.c

[`apps/hello_world/src/main.c`](https://github.com/owhinata/coral-dev/blob/8fd917a95bfcf00101f0c7ddb712c1dc2a49f485/apps/hello_world/src/main.c)

```c
#include <stdio.h>

int main(void) {
  printf("Hello from Coral Dev Board!\n");
  return 0;
}
```

### CMakeLists.txt

[`apps/hello_world/CMakeLists.txt`](https://github.com/owhinata/coral-dev/blob/8fd917a95bfcf00101f0c7ddb712c1dc2a49f485/apps/hello_world/CMakeLists.txt)

```cmake
cmake_minimum_required(VERSION 3.16)
project(hello_world C)

add_executable(hello_world src/main.c)

# Deploy / Run
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/coral-deploy.cmake)

coral_add_deploy_target(
    DEPLOY_DIR /home/mendel/hello_world
    DEPENDS hello_world
    FILES "$<TARGET_FILE:hello_world>:hello_world"
)

coral_add_run_target(
    COMMAND /home/mendel/hello_world/hello_world
)
```

Including `coral-deploy.cmake` adds the `deploy` and `run` targets.

- **`DEPLOY_DIR`**: Target directory on the board
- **`DEPENDS`**: Targets to build before deploying
- **`FILES`**: Files to transfer (`local_path:remote_filename`)
- **`COMMAND`**: Command to execute remotely

## Build

```bash
cmake -B build/hello_world -S apps/hello_world \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/hello_world
```

## Deploy

Transfer the built binary to the Coral Dev Board.

```bash
cmake --build build/hello_world --target deploy
```

## Run

Execute the application remotely on the board.

```bash
cmake --build build/hello_world --target run
```

Expected output:

```
Hello from Coral Dev Board!
```
