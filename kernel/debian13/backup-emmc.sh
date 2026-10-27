#!/usr/bin/env bash
# Run on the host while the board is booted from the trial SD card.
set -euo pipefail
[[ $# == 1 ]] || { echo 'Usage: backup-emmc.sh NEW_BACKUP_DIRECTORY' >&2; exit 2; }
out=$1
repo=$(cd "$(dirname "$0")/../.." && pwd)
run=$repo/scripts/run.sh
[[ ! -e $out ]] || { echo "Backup destination already exists: $out" >&2; exit 1; }
umask 077
mkdir -p "$(dirname "$out")"
mkdir -m 700 "$out"
read -r -s -p 'Board sudo password: ' board_password < /dev/tty
printf '\n' > /dev/tty
remote_sudo() { printf '%s\n' "$board_password" | CORAL_QUIET=1 "$run" "sudo -S -p '' $1"; }
trap 'unset board_password' EXIT
remote_sudo "sh -c 'test \"\$(findmnt -n -o SOURCE /)\" = /dev/mmcblk1p2 && ! findmnt -rn -S /dev/mmcblk0p1 && ! findmnt -rn -S /dev/mmcblk0p2'"
for dev in mmcblk0boot0 mmcblk0boot1 mmcblk0; do
  echo "Backing up /dev/$dev ..." >&2
  size=$(remote_sudo "blockdev --getsize64 /dev/$dev")
  remote_sudo "sh -c 'exec gzip -1 < /dev/$dev'" > "$out/$dev.img.gz.partial"
  actual=$(gzip -dc "$out/$dev.img.gz.partial" | wc -c)
  [[ $actual == "$size" ]] || { echo "Incorrect backup size for $dev: $actual != $size" >&2; exit 1; }
  mv "$out/$dev.img.gz.partial" "$out/$dev.img.gz"
  printf '%s %s\n' "$dev" "$size" >> "$out/SIZES"
done
(cd "$out" && sha256sum mmcblk0.img.gz mmcblk0boot0.img.gz mmcblk0boot1.img.gz > SHA256SUMS && sha256sum -c SHA256SUMS)
echo "Verified backup: $out"
