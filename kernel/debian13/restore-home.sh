#!/bin/bash
set -euo pipefail
[[ ${1:-} == --mount-home && $# == 1 ]] || { echo 'Usage: sudo restore-home.sh --mount-home' >&2; exit 2; }
test "$(id -u)" = 0
test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p2
test "$(blkid -s UUID -o value /dev/mmcblk1p1)" = 395738a2-5c37-4441-aa21-78126cbb9a0c
if findmnt -rn -S /dev/mmcblk1p1; then echo 'SD card is already mounted' >&2; exit 1; fi
mkdir -p /mnt/home-inspect
if mountpoint -q /mnt/home-inspect || findmnt -rn -M /home || grep -Eq '^[[:space:]]*[^#[:space:]]+[[:space:]]+/home[[:space:]]' /etc/fstab; then
  echo 'A home mount or fstab entry already exists' >&2; exit 1
fi
mount /dev/mmcblk1p1 /mnt/home-inspect
cleanup() { if mountpoint -q /mnt/home-inspect; then umount /mnt/home-inspect || true; fi; }
trap cleanup EXIT
test "$(stat -c '%u:%g' /mnt/home-inspect/mendel)" = 1000:1000
cmp /home/mendel/.ssh/authorized_keys /mnt/home-inspect/mendel/.ssh/authorized_keys
if [[ -e /mnt/home-inspect/mendel/.venvs/pycoral ]]; then
  echo 'Preserving the existing SD-card PyCoral venv without merging it.'
  rsync -aHAX --numeric-ids --ignore-existing --exclude='/mendel/.venvs/pycoral/***' /home/ /mnt/home-inspect/
else
  rsync -aHAX --numeric-ids --ignore-existing /home/ /mnt/home-inspect/
fi
sync
umount /mnt/home-inspect
cp -a /etc/fstab /etc/fstab.before-home-sd
printf '%s\n' 'UUID=395738a2-5c37-4441-aa21-78126cbb9a0c /home ext4 defaults,noatime,nosuid,nodev 0 2' >> /etc/fstab
systemctl daemon-reload
mount /home
findmnt -n -o SOURCE,TARGET,FSTYPE /home
