# coral-dev

Google Coral Dev Board 向けの組込みAI開発環境。

[English version](README.md)

## 概要

- CMake ベースのクロスコンパイル環境（aarch64-linux-gnu）
- SSH/mdt によるワンコマンドデプロイ・実行
- TensorFlow Lite + Edge TPU による AI 推論
- MkDocs による日英バイリンガルドキュメント

## ドキュメント

詳細は [Coral Dev Board Guide](https://owhinata.github.io/coral-dev/) を参照してください。

## クイックスタート

### 必要環境

- CMake 3.16+
- Python 3（venv 用）

### セットアップ

```bash
# 仮想環境を作成し、ツール（mdt, mkdocs 等）をインストール
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# クロスコンパイラのインストール（ARM GNU Toolchain 8.3, glibc 2.28）
./cmake/setup-toolchain.sh
```

### ビルド・デプロイ

```bash
# ビルド
cmake -B build/<app> -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>

# デプロイ（ボードへ転送）
cmake --build build/<app> --target deploy

# リモート実行
cmake --build build/<app> --target run
```

### ドキュメントのローカルビルド

```bash
.venv/bin/mkdocs serve
```

## ライセンス

[MIT](LICENSE)
