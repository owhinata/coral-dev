#!/bin/bash
# Run on the host. The selected removable disk is completely overwritten.
set -euo pipefail
[[ $(id -u) == 0 && $# == 6 && $1 == --write ]] || {
  echo 'Usage: sudo write-sd.sh --write DEVICE RECOVERY_IMG ROOTFS_TAR KERNEL_IMAGE DTB' >&2; exit 2;
}
dev=$(readlink -f "$2")
recovery=$(realpath "$3")
root_tar=$(realpath "$4")
image=$(realpath "$5")
dtb=$(realpath "$6")
for cmd in sgdisk mkfs.ext2 mkfs.ext4 mkimage partprobe blkid python3; do command -v "$cmd" >/dev/null; done
[[ -b $dev && $(lsblk -nd -o TYPE "$dev") == disk && $(lsblk -nd -o RM "$dev") == 1 ]]
[[ $(stat -c %s "$recovery") == 4194304 ]]
[[ $(blockdev --getsize64 "$dev") -ge 8000000000 ]]
if lsblk -nr -o MOUNTPOINTS "$dev" | grep -q '[^[:space:]]'; then
  echo "Unmount every partition of $dev first" >&2; exit 1
fi
root_guid=$(python3 -c 'import uuid; print(uuid.uuid4())')
work=$(mktemp -d)
cleanup() {
  if mountpoint -q "$work/boot"; then umount "$work/boot" || true; fi
  if mountpoint -q "$work/root"; then umount "$work/root" || true; fi
  rm -f "$work/boot.cmd" "$work/archive-files"
  rmdir "$work/boot" "$work/root" "$work" 2>/dev/null || true
}
trap cleanup EXIT
mkdir "$work/boot" "$work/root"
tar -tf "$root_tar" > "$work/archive-files"
for required in '(^|/)home/mendel/[.]venvs/pycoral/bin/activate$' '(^|/)home/mendel/[.]venvs/pycoral/lib/python3[.]7/site-packages/pycoral/__init__[.]py$' '(^|/)etc/avahi/services/mdt.service$' '(^|/)lib/modules/7[.]3[.]0-imx-coral[+]/modules.dep$'; do
  grep -Eq "$required" "$work/archive-files" || { echo "Rootfs archive is missing $required" >&2; exit 1; }
done
dd if="$recovery" of="$dev" bs=4M conv=fsync status=progress
sgdisk --clear --new=1:8192:+256M --typecode=1:8300 --change-name=1:boot \
  --new=2:0:0 --typecode=2:8300 --change-name=2:debian13 --partition-guid=2:"$root_guid" "$dev"
partprobe "$dev"
command -v udevadm >/dev/null && udevadm settle
if [[ $dev =~ [0-9]$ ]]; then boot=${dev}p1; root=${dev}p2; else boot=${dev}1; root=${dev}2; fi
[[ -b $boot && -b $root ]]
mkfs.ext2 -F -L CORALBOOT "$boot"
mkfs.ext4 -F -L DEBIAN13 "$root"
mount "$root" "$work/root"
mount "$boot" "$work/boot"
tar --xattrs --acls --numeric-owner -xpf "$root_tar" -C "$work/root"
install -m 644 "$image" "$work/boot/Image-7.3.0-imx-coral+"
install -m 644 "$dtb" "$work/boot/imx8mq-phanbell-7.3.0-imx-coral+.dtb"
cat > "$work/boot.cmd" <<EOF
setenv fdt_addr 0x48000000
setenv bootargs "console=ttymxc0,115200 earlycon=ec_imx6q,0x30860000,115200 root=PARTUUID=$root_guid rootfstype=ext4 rw rootwait net.ifnames=0"
if ext2load mmc \${bootdev}:1 \${loadaddr} Image-7.3.0-imx-coral+; then
    if ext2load mmc \${bootdev}:1 \${fdt_addr} imx8mq-phanbell-7.3.0-imx-coral+.dtb; then
        booti \${loadaddr} - \${fdt_addr}
    fi
fi
echo "Debian SD boot failed"
EOF
mkimage -A arm64 -T script -C none -n 'Coral Debian 13 SD' -d "$work/boot.cmd" "$work/boot/boot.scr"
boot_uuid=$(blkid -s UUID -o value "$boot")
printf '%s\n' "PARTUUID=$root_guid / ext4 defaults,noatime 0 1" "UUID=$boot_uuid /boot ext2 defaults,noatime 0 2" > "$work/root/etc/fstab"
sync
cmp "$image" "$work/boot/Image-7.3.0-imx-coral+"
cmp "$dtb" "$work/boot/imx8mq-phanbell-7.3.0-imx-coral+.dtb"
echo "SD card prepared: $dev; root PARTUUID=$root_guid"
