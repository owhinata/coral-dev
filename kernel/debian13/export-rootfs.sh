#!/usr/bin/env bash
# Run on the host; export a prepared rootfs from the original Mendel board.
set -euo pipefail
[[ $# == 2 ]] || { echo 'Usage: export-rootfs.sh /home/mendel/ROOTFS OUTPUT_TAR' >&2; exit 2; }
root=$1
out=$2
[[ $root =~ ^/home/mendel/[a-zA-Z0-9._/-]+$ && $root != *..* && ! -e $out && ! -e $out.partial ]] || {
  echo 'Unsafe path or output already exists' >&2; exit 1;
}
repo=$(cd "$(dirname "$0")/../.." && pwd)
umask 077
read -r -s -p 'Board sudo password: ' board_password < /dev/tty
printf '\n' > /dev/tty
trap 'unset board_password' EXIT
printf '%s\n' "$board_password" | CORAL_QUIET=1 "$repo/scripts/run.sh" \
  "sudo -S -p '' tar --xattrs --acls --numeric-owner -C '$root' -cpf - ." > "$out.partial"
tar -tf "$out.partial" > /dev/null
mv "$out.partial" "$out"
echo "Rootfs archive: $out"
