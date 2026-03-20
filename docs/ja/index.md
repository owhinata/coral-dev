# Coral Dev Board Guide

Google Coral Dev Board を使った組込みAI開発のためのガイドです。

## このプロジェクトについて

本リポジトリは Coral Dev Board 向けの開発環境を提供します。

- **クロスコンパイル**: CMake + aarch64-linux-gnu ツールチェーンによるビルド環境
- **デプロイ・実行**: SSH/mdt によるワンコマンドデプロイ
- **AI推論**: TensorFlow Lite + Edge TPU による高速推論

## Coral Dev Board とは

[Coral Dev Board](https://coral.ai/products/dev-board/) は Google が提供するシングルボードコンピュータです。

- **SoC**: NXP i.MX 8M (Quad-core Cortex-A53 + Cortex-M4F)
- **AI アクセラレータ**: Google Edge TPU (4 TOPS)
- **メモリ**: 1GB LPDDR4
- **OS**: Mendel Linux (Debian ベース)

## クイックスタート

1. [セットアップガイド](setup/getting_started.md) に従ってボードを準備
2. アプリをクロスコンパイルしてデプロイ

```bash
# ビルド
cmake -B build/<app> -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>

# デプロイ & 実行
cmake --build build/<app> --target deploy
cmake --build build/<app> --target run
```
