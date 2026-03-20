# coral-dev

Google Coral Dev Board 向けの組込みAI開発環境。

## 概要

- CMake ベースのクロスコンパイル環境（aarch64-linux-gnu）
- SSH/mdt によるワンコマンドデプロイ・実行
- TensorFlow Lite + Edge TPU による AI 推論
- MkDocs による日英バイリンガルドキュメント

## ドキュメント

詳細は [Coral Dev Board Guide](https://owhinata.github.io/coral-dev/) を参照してください。

## クイックスタート

### 必要環境

- aarch64 クロスコンパイラ (`sudo apt install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu`)
- CMake 3.16+
- mdt (`pip install mendel-development-tool`)

### ビルド・デプロイ

```bash
# ビルド
cmake -B build/<app> -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>

# デプロイ（ボードへ転送）
cmake --build build/<app> --target deploy

# リモート実行
cmake --build build/<app> --target run
```

### ドキュメントのローカルビルド

```bash
pip install -r requirements.txt
mkdocs serve
```

## ライセンス

[MIT](LICENSE)
