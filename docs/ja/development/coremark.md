# CoreMark

[CoreMark](https://github.com/eembc/coremark) は EEMBC が提供する CPU ベンチマークです。`apps/coremark/` では CMake FetchContent で upstream ソースを自動取得し、**カスタムソースファイルなし**（CMakeLists.txt のみ）でビルドできます。

## 前提条件

- aarch64 クロスコンパイラが `toolchain/` に展開済みであること
- ホスト OS: x86_64 Linux
- CMake 3.16 以上
- インターネット接続（初回の FetchContent 取得時のみ）

## 設計

### posix/ port 選択理由

CoreMark の upstream `posix/` port は以下の設定で動作します:

- `USE_CLOCK=0`, `HAS_TIME_H=1` → `clock_gettime(CLOCK_REALTIME)` でタイミング計測
- `SEED_METHOD=SEED_ARG` → コマンドライン引数でシード設定（引数なしで自動検出）
- `MEM_METHOD=MEM_MALLOC` → 標準ヒープ割り当て

Coral Dev Board の Mendel Linux (Debian ベース / glibc) で問題なく動作します。

### カスタムソースファイル不要の理由

- `CORETIMETYPE` は `core_portme.c` 内でのみ使用（`core_main.c` では `CORE_TICKS`=`clock_t` を使用）
- posix port の `core_portme.c` がそのまま利用可能
- 設定差分（ITERATIONS 等）は実行時引数または CMake `-D` で対応可能
- `FLAGS_STR` のみ CMake から定義（upstream Makefile でも `-D` で渡す設計）

### -O2 最適化

ベンチマークとして意味のある結果を得るため、`-O2` を明示的に指定しています。`FLAGS_STR` にも反映され、CoreMark のレポート出力にコンパイラフラグとして表示されます。

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

FetchContent でビルド時に CoreMark ソースを自動取得するため、手動でのソース配置は不要です。`coremark_src_SOURCE_DIR` に展開されたソースから、コアファイル 5 つと `posix/core_portme.c` をビルドします。

## ビルド

リポジトリのルートディレクトリから実行します。

```bash
cmake -B build/coremark -S apps/coremark \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/coremark
```

### 生成された ELF を確認

```bash
file build/coremark/coremark
```

期待される出力:

```
coremark: ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), dynamically linked, ...
```

## デプロイと実行

CMake の `deploy` / `run` ターゲットで転送・実行をワンコマンドで行えます:

```bash
cmake --build build/coremark --target deploy
cmake --build build/coremark --target run
```

実行結果の例:

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

## 実行オプション

CoreMark は引数なしで実行すると、デフォルト設定（ITERATIONS 自動検出、SEED 自動選択）で動作します。

```
coremark <seed1> <seed2> <seed3> <iterations>
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| seed1, seed2, seed3 | ベンチマークの入力シード | 自動選択（validation/performance/profile） |
| iterations | 実行回数 | 自動（最低 10 秒間実行される値） |

例: 50000 イテレーションで実行:

```bash
scripts/run.sh '/home/mendel/work/coremark/coremark 0 0 0x66 50000'
```

---

## CMake ターゲット { #cmake-targets }

### 設定

```bash
cmake -B build/coremark -S apps/coremark \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
```

### ターゲット一覧

| ターゲット | コマンド | 説明 |
|-----------|---------|------|
| (デフォルト) | `cmake --build build/coremark` | C バイナリのビルド |
| `deploy` | `cmake --build build/coremark --target deploy` | ビルド + ボードへの転送 |
| `run` | `cmake --build build/coremark --target run` | ボード上でリモート実行 |

### 接続設定

CMake キャッシュ変数で接続先をカスタマイズできます:

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `CORAL_IP` | (空 = mdt で自動検出) | Coral Dev Board の IP アドレス |

## 将来の拡張

### マルチスレッド対応

マルチスレッドで CoreMark を実行する場合:

1. `apps/coremark/src/core_portme.c` に upstream の `posix/core_portme.c` をコピー
2. CMakeLists.txt のソースパスを `src/core_portme.c` に変更
3. CMake で `-DMULTITHREAD=4 -DUSE_PTHREAD=1` を追加し、`target_link_libraries` に `pthread` を追加
