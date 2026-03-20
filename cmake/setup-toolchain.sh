#!/usr/bin/env bash
# setup-toolchain.sh — Download and extract ARM cross-compiler for Coral Dev Board.
#
# Toolchain: gcc-arm-8.3-2019.03-x86_64-aarch64-linux-gnu
#   GCC 8.3, glibc 2.28 (matches Mendel Linux / Debian 10 Buster)
#
# Usage: ./cmake/setup-toolchain.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOLCHAIN_DIR="$PROJECT_ROOT/toolchain"

TARBALL="gcc-arm-8.3-2019.03-x86_64-aarch64-linux-gnu.tar.xz"
URL="https://developer.arm.com/-/media/Files/downloads/gnu-a/8.3-2019.03/binrel/$TARBALL"
EXTRACTED_DIR="gcc-arm-8.3-2019.03-x86_64-aarch64-linux-gnu"

# Check if already set up
if [ -x "$TOOLCHAIN_DIR/$EXTRACTED_DIR/bin/aarch64-linux-gnu-gcc" ]; then
    echo "Toolchain already installed:"
    "$TOOLCHAIN_DIR/$EXTRACTED_DIR/bin/aarch64-linux-gnu-gcc" --version | head -1
    exit 0
fi

mkdir -p "$TOOLCHAIN_DIR"
cd "$TOOLCHAIN_DIR"

# Download
if [ ! -f "$TARBALL" ]; then
    echo "Downloading $TARBALL ..."
    curl -LO "$URL"
else
    echo "Archive already downloaded."
fi

# Extract
echo "Extracting..."
tar xf "$TARBALL"

# Verify
echo ""
echo "Toolchain installed:"
"$TOOLCHAIN_DIR/$EXTRACTED_DIR/bin/aarch64-linux-gnu-gcc" --version | head -1
echo ""
echo "Location: $TOOLCHAIN_DIR/$EXTRACTED_DIR"
