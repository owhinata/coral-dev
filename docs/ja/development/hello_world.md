# Hello World

Coral Dev Board で動作する最小限のアプリケーションです。
クロスコンパイル・デプロイ・実行の一連の流れを確認できます。

## ソースコード

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
    DEPLOY_DIR /home/mendel/work/hello_world
    DEPENDS hello_world
    FILES "$<TARGET_FILE:hello_world>:hello_world"
)

coral_add_run_target(
    COMMAND /home/mendel/work/hello_world/hello_world
)
```

`coral-deploy.cmake` を include することで `deploy` / `run` ターゲットが追加されます。

- **`DEPLOY_DIR`**: ボード上の配置先ディレクトリ
- **`DEPENDS`**: デプロイ前にビルドするターゲット
- **`FILES`**: 転送するファイル（`ローカルパス:リモートファイル名`）
- **`COMMAND`**: リモート実行するコマンド

## ビルド

```bash
cmake -B build/hello_world -S apps/hello_world \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/hello_world
```

## デプロイ

ビルドしたバイナリを Coral Dev Board に転送します。

```bash
cmake --build build/hello_world --target deploy
```

## 実行

ボード上でリモート実行します。

```bash
cmake --build build/hello_world --target run
```

期待される出力:

```
Hello from Coral Dev Board!
```
