# coral-dev

Embedded AI development environment for the Google Coral Dev Board.

[日本語版はこちら](README_ja.md)

## Overview

- CMake-based cross-compilation (aarch64-linux-gnu)
- One-command deploy & run via SSH/mdt
- AI inference with TensorFlow Lite + Edge TPU
- Bilingual documentation (JA/EN) with MkDocs

## Documentation

See the [Coral Dev Board Guide](https://owhinata.github.io/coral-dev/en/) for details.

## Quick Start

### Prerequisites

- CMake 3.16+
- Python 3 (for venv)

### Setup

```bash
# Create venv and install tools (mdt, mkdocs, etc.)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Install cross-compiler (ARM GNU Toolchain 8.3, glibc 2.28)
./cmake/setup-toolchain.sh
```

### Build & Deploy

```bash
# Build
cmake -B build/<app> -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>

# Deploy to board
cmake --build build/<app> --target deploy

# Run remotely
cmake --build build/<app> --target run
```

### Build Documentation Locally

```bash
.venv/bin/mkdocs serve
```

## License

[MIT](LICENSE)
