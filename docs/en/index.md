# Coral Dev Board Guide

A guide for embedded AI development with Google Coral Dev Board.

## About This Project

This repository provides a development environment for the Coral Dev Board.

- **Cross-compilation**: Build environment with CMake + aarch64-linux-gnu toolchain
- **Deploy & Run**: One-command deployment via SSH/mdt
- **AI Inference**: High-speed inference with TensorFlow Lite + Edge TPU

## What is Coral Dev Board?

[Coral Dev Board](https://coral.ai/products/dev-board/) is a single-board computer provided by Google.

- **SoC**: NXP i.MX 8M (Quad-core Cortex-A53 + Cortex-M4F)
- **AI Accelerator**: Google Edge TPU (4 TOPS)
- **Memory**: 1GB LPDDR4
- **OS**: Mendel Linux (Debian-based)

## Quick Start

1. Follow the [Getting Started guide](setup/getting_started.md) to set up your board
2. Cross-compile and deploy an application

```bash
# Build
cmake -B apps/<app>/build -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-coral-aarch64.cmake
cmake --build apps/<app>/build

# Deploy & Run
cmake --build apps/<app>/build --target deploy
cmake --build apps/<app>/build --target run
```
