#!/bin/bash
set -euo pipefail
[[ ${1:-} == --write-emmc && $# == 1 ]] || { echo 'Usage: sudo install-emmc.sh --write-emmc' >&2; exit 2; }
# This script is deliberately pinned to the verified board and partition layout.
# Back up the disk on the host before running it; see README.md.
rootdev=/dev/mmcblk0p2
bootdev=/dev/mmcblk0p1
target=/mnt/debian13-emmc
bootcheck=/mnt/emmc-boot-inspect
test "$(id -u)" = 0
test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk1p2
test "$(blkid -s PARTUUID -o value "$rootdev")" = 70672ec3-5eee-49ff-b3b1-eb1fbd406bf5
test "$(blkid -s UUID -o value "$bootdev")" = 7b4cfc91-9ee8-487d-88ca-2966f21ba005
if findmnt -rn -S "$rootdev" || findmnt -rn -S "$bootdev"; then
  echo 'An eMMC partition is mounted' >&2; exit 1
fi
mkdir -p "$target" "$bootcheck"
if mountpoint -q "$target" || mountpoint -q "$bootcheck"; then
  echo 'A staging directory is already mounted' >&2; exit 1
fi
cleanup() {
  if mountpoint -q "$bootcheck"; then umount "$bootcheck" || true; fi
  if mountpoint -q "$target"; then umount "$target" || true; fi
}
trap cleanup EXIT
mount -o ro "$bootdev" "$bootcheck"
cmp /boot/Image-7.3.0-imx-coral+ "$bootcheck/Image-7.3.0-imx-coral+"
cmp /boot/imx8mq-phanbell-7.3.0-imx-coral+.dtb "$bootcheck/imx8mq-phanbell-7.3.0-imx-coral+.dtb"
grep -aq '70672ec3-5eee-49ff-b3b1-eb1fbd406bf5' "$bootcheck/boot.scr"
umount "$bootcheck"
mkfs.ext4 -F -L DEBIAN13_EMMC "$rootdev"
mount "$rootdev" "$target"
rsync -aHAXx --numeric-ids --exclude='/boot/***' --exclude='/dev/***' --exclude='/proc/***' --exclude='/sys/***' --exclude='/run/***' --exclude='/tmp/***' --exclude='/mnt/***' --exclude='/media/***' --exclude='/lost+found/***' / "$target/"
mkdir -p "$target"/{boot,dev,proc,sys,run,tmp,mnt,media}
chmod 1777 "$target/tmp"
printf '%s\n' 'PARTUUID=70672ec3-5eee-49ff-b3b1-eb1fbd406bf5 / ext4 defaults,noatime 0 1' 'UUID=7b4cfc91-9ee8-487d-88ca-2966f21ba005 /boot ext2 defaults,noatime 0 2' > "$target/etc/fstab"
sync
test -f "$target/home/mendel/.venvs/pycoral/bin/activate"
test -f "$target/home/mendel/.venvs/pycoral/lib/python3.7/site-packages/pycoral/__init__.py"
test -e "$target/etc/avahi/services/mdt.service"
test -e "$target/lib/modules/7.3.0-imx-coral+/modules.dep"
umount "$target"
e2fsck -fn "$rootdev"
echo 'Debian 13 copied to eMMC; existing eMMC boot files verified.'
