#!/usr/bin/env bash
# deploy.sh — Copy the mainline kernel build to the Coral Dev Board WITHOUT
# touching the existing Mendel kernel. Files are installed under new names:
#   /boot/Image-<ver>            kernel image
#   /boot/imx8mq-phanbell-<ver>.dtb
#   /lib/modules/<ver>/          modules (incl. gasket/apex)
# The stock /boot/Image symlink and boot.scr are left unchanged; the new kernel
# is booted manually from U-Boot (see uboot-boot.py).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT="$SCRIPT_DIR/out"
STAGE="$OUT/modules-staging/lib/modules"

VER="$(ls "$STAGE")"
[ "$(echo "$VER" | wc -l)" -eq 1 ] || { echo "expected exactly one kernel version in $STAGE, got: $VER" >&2; exit 1; }

IMAGE="$OUT/arch/arm64/boot/Image"
DTB="$OUT/arch/arm64/boot/dts/freescale/imx8mq-phanbell.dtb"
DTB_NOPCIE="$OUT/arch/arm64/boot/dts/freescale/imx8mq-phanbell-nopcie.dtb"
DTB_TPUONLY="$OUT/arch/arm64/boot/dts/freescale/imx8mq-phanbell-tpuonly.dtb"
TARBALL="$OUT/modules-$VER.tar.gz"

echo "Kernel version: $VER"
tar -C "$OUT/modules-staging/lib/modules" -czf "$TARBALL" "$VER"
ls -lh "$IMAGE" "$DTB" "$TARBALL"

REMOTE_DIR="/home/mendel/kernel-$VER"
CORAL_DEPLOY_DIR="$REMOTE_DIR" "$ROOT/scripts/deploy.sh" \
    "$IMAGE:Image" \
    "$DTB:imx8mq-phanbell.dtb" \
    "$DTB_NOPCIE:imx8mq-phanbell-nopcie.dtb" \
    "$DTB_TPUONLY:imx8mq-phanbell-tpuonly.dtb" \
    "$TARBALL:modules.tar.gz"

"$ROOT/scripts/run.sh" "set -e; cd $REMOTE_DIR; \
  sudo install -m 644 Image /boot/Image-$VER; \
  sudo install -m 644 imx8mq-phanbell.dtb /boot/imx8mq-phanbell-$VER.dtb; \
  sudo install -m 644 imx8mq-phanbell-nopcie.dtb /boot/imx8mq-phanbell-nopcie-$VER.dtb; \
  sudo install -m 644 imx8mq-phanbell-tpuonly.dtb /boot/imx8mq-phanbell-tpuonly-$VER.dtb; \
  sudo rm -rf /lib/modules/$VER; sudo tar -C /lib/modules -xzf modules.tar.gz; \
  sudo depmod -a $VER; \
  ls -l /boot/Image-$VER /boot/imx8mq-phanbell*-$VER.dtb; ls /lib/modules/$VER | head; df -h /boot | tail -1"
echo
echo "U-Boot one-shot boot commands (via serial console):"
echo "  ext2load mmc 0:1 0x40480000 Image-$VER"
echo "  ext2load mmc 0:1 0x48000000 imx8mq-phanbell-$VER.dtb"
echo "  setenv bootargs console=ttymxc0,115200 earlycon=ec_imx6q,0x30860000,115200 root=PARTUUID=70672ec3-5eee-49ff-b3b1-eb1fbd406bf5 rootfstype=ext4 rw rootwait net.ifnames=0"
echo "  booti 0x40480000 - 0x48000000"
