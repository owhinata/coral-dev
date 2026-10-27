#!/usr/bin/env bash
# install-bootscr.sh — Build kernel/boot/boot.cmd into boot.scr and install it on the
# board as /boot/boot.scr (the original is kept once as /boot/boot.scr.mendel-orig).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
docker run --rm -u "$(id -u):$(id -g)" -v "$SCRIPT_DIR:$SCRIPT_DIR" -w "$SCRIPT_DIR/boot" \
    coral-kernel-builder mkimage -A arm64 -T script -C none -d boot.cmd boot.scr
CORAL_DEPLOY_DIR=/home/mendel/coral-boot "$ROOT/scripts/deploy.sh" "$SCRIPT_DIR/boot/boot.scr:boot.scr"
"$ROOT/scripts/run.sh" 'set -e; [ -e /boot/boot.scr.mendel-orig ] || sudo cp -a /boot/boot.scr /boot/boot.scr.mendel-orig; \
  sudo install -m 644 /home/mendel/coral-boot/boot.scr /boot/boot.scr; ls -l /boot/boot.scr*'
