#!/usr/bin/env bash
# build.sh — Cross-build Linux kernel + gasket/apex modules for Coral Dev Board
# inside the coral-kernel-builder Docker image (see kernel/docker/Dockerfile).
#
# Usage:
#   kernel/build.sh image      # Docker image build
#   kernel/build.sh config     # defconfig + coral fragment -> kernel/out/.config
#   kernel/build.sh kernel     # Image + modules + dtbs
#   kernel/build.sh gasket     # out-of-tree gasket/apex modules
#   kernel/build.sh install    # stage modules into kernel/out/modules-staging
#   kernel/build.sh shell      # interactive shell in the container
#   kernel/build.sh all        # config + kernel + gasket
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMG=coral-kernel-builder
SRC="$SCRIPT_DIR/linux"
OUT="$SCRIPT_DIR/out"
GASKET="$SCRIPT_DIR/gasket-driver"
JOBS="${JOBS:-$(nproc)}"

run() {
    docker run --rm -i $( [ -t 0 ] && echo -t ) \
        -u "$(id -u):$(id -g)" \
        -v "$SCRIPT_DIR:$SCRIPT_DIR" -w "$SRC" \
        -e ARCH=arm64 -e CROSS_COMPILE=aarch64-linux-gnu- -e HOME=/tmp \
        "$IMG" "$@"
}

cmd="${1:-all}"
case "$cmd" in
    image)
        docker build -t "$IMG" "$SCRIPT_DIR/docker" ;;
    config)
        mkdir -p "$OUT"
        run make O="$OUT" defconfig
        run scripts/kconfig/merge_config.sh -O "$OUT" "$OUT/.config" "$SCRIPT_DIR/coral.config"
        ;;
    kernel)
        run make O="$OUT" -j"$JOBS" Image modules dtbs ;;
    gasket)
        run make -C "$OUT" M="$GASKET/src" -j"$JOBS" modules ;;
    install)
        # Stage modules (kernel + gasket/apex) under out/modules-staging for deploy.sh
        rm -rf "$OUT/modules-staging"
        run make O="$OUT" INSTALL_MOD_PATH="$OUT/modules-staging" INSTALL_MOD_STRIP=1 modules_install
        run make -C "$OUT" M="$GASKET/src" INSTALL_MOD_PATH="$OUT/modules-staging" INSTALL_MOD_STRIP=1 modules_install
        ;;
    shell)
        run bash ;;
    all)
        "$0" config && "$0" kernel && "$0" gasket && "$0" install ;;
    *)
        echo "unknown command: $cmd" >&2; exit 1 ;;
esac
