#!/bin/bash
# Run on the original Mendel board, booted with the patched mainline kernel.
set -euo pipefail
[[ $# == 2 && $(id -u) == 0 ]] || { echo 'Usage: sudo prepare-rootfs.sh DEBIAN_BASE_TAR NEW_ROOTFS_DIR' >&2; exit 2; }
base=$(realpath "$1")
root=$2
[[ $(uname -m) == aarch64 && ! -e $root ]] || { echo 'Requires arm64 and a new rootfs directory' >&2; exit 1; }
[[ $(id -u mendel) == 1000 && $(id -g mendel) == 1000 ]]
for file in /home/mendel/.ssh/authorized_keys /usr/bin/python3.7 /usr/lib/aarch64-linux-gnu/libssl.so.1.1 /usr/lib/aarch64-linux-gnu/libcrypto.so.1.1 /lib/firmware/bdwlan30.bin /usr/bin/mdt-keymaster /usr/bin/usb-gadget-start.sh; do
  [[ -e $file ]] || { echo "Missing Mendel dependency: $file" >&2; exit 1; }
done
mkdir -p "$root"
root=$(realpath "$root")
cleanup() {
  for path in "$root/dev/pts" "$root/dev" "$root/sys" "$root/proc"; do
    if mountpoint -q "$path"; then umount "$path" || true; fi
  done
}
trap cleanup EXIT
tar --numeric-owner -xf "$base" -C "$root"
cp -L /etc/resolv.conf "$root/etc/resolv.conf"
mkdir -p "$root"/{proc,sys,dev/pts}
mount -t proc proc "$root/proc"
mount --bind /sys "$root/sys"
mount --bind /dev "$root/dev"
mount --bind /dev/pts "$root/dev/pts"
chroot "$root" apt-get update
chroot "$root" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  systemd-sysv systemd-timesyncd udev e2fsprogs openssh-server network-manager wpasupplicant \
  avahi-daemon dnsmasq python3 python3-requests python3-netifaces sudo kmod iproute2 ca-certificates rsync \
  libblas3 liblapack3 libusb-1.0-0 libcrypt1 libexpat1 zlib1g libjpeg62-turbo libjbig0 liblzma5 libzstd1
chroot "$root" useradd -m -u 1000 -s /bin/bash -G sudo,plugdev,netdev mendel
chroot "$root" usermod -p "$(getent shadow mendel | cut -d: -f2)" mendel
chroot "$root" groupadd -f apex
chroot "$root" usermod -aG apex mendel
install -d -m 700 -o 1000 -g 1000 "$root/home/mendel/.ssh"
install -m 600 -o 1000 -g 1000 /home/mendel/.ssh/authorized_keys "$root/home/mendel/.ssh/authorized_keys"
shopt -s nullglob
profiles=(/etc/NetworkManager/system-connections/*.nmconnection)
(( ${#profiles[@]} > 0 )) || { echo 'No NetworkManager profiles found' >&2; exit 1; }
install -m 600 "${profiles[@]}" "$root/etc/NetworkManager/system-connections/"
install -d "$root/lib/firmware/ath10k/QCA6174/hw3.0" "$root/lib/modules"
cp -a /lib/firmware/ath10k/QCA6174/hw3.0/. "$root/lib/firmware/ath10k/QCA6174/hw3.0/"
cp -a "/lib/modules/$(uname -r)" "$root/lib/modules/"
install -m 644 /etc/avahi/services/mdt.service "$root/etc/avahi/services/mdt.service"
install -m 755 /usr/bin/mdt-keymaster /usr/bin/usb-gadget-start.sh /usr/bin/usb-gadget-stop.sh "$root/usr/bin/"
install -m 644 /lib/systemd/system/{mdt-keymaster.path,mdt-keymaster.service,usb-gadget.service,usb-gadget-getty-ttyGS0.service} "$root/lib/systemd/system/"
install -m 644 /etc/dnsmasq.d/{02-usb-gadget,99-no-default-dns,99-no-default-route} "$root/etc/dnsmasq.d/"
printf '%s\n' 'SUBSYSTEM=="apex", MODE="0660", GROUP="apex"' > "$root/etc/udev/rules.d/65-apex.rules"
printf '%s\n' 'purple-horse-debian' > "$root/etc/hostname"
printf '%s\n' '127.0.0.1 localhost' '127.0.1.1 purple-horse-debian' > "$root/etc/hosts"
install -m 755 /usr/bin/python3.7 "$root/usr/bin/python3.7"
cp -a /usr/lib/python3.7 "$root/usr/lib/"
cp -a /usr/lib/aarch64-linux-gnu/libedgetpu.so.1* "$root/usr/lib/aarch64-linux-gnu/"
venv=/home/mendel/.venvs/pycoral
chroot "$root" /usr/bin/python3.7 -m venv --without-pip "$venv"
cp -a /usr/lib/python3/dist-packages/{pycoral,tflite_runtime,numpy,PIL} "$root$venv/lib/python3.7/site-packages/"
cp -a /usr/lib/aarch64-linux-gnu/lib{imagequant.so.0*,tiff.so.5*,webp.so.6*,ffi.so.6*,ssl.so.1.1,crypto.so.1.1} "$root$venv/lib/"
# Make the copied native libraries available when the venv is activated.
chroot "$root" /usr/bin/python3 - "$venv/bin/activate" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text()
text = text.replace('deactivate () {\n', '''deactivate () {
    if [ -n "${_PYCORAL_ACTIVE:-}" ]; then
        if [ -n "${_PYCORAL_OLD_LD_LIBRARY_PATH_SET:-}" ]; then
            export LD_LIBRARY_PATH="$_PYCORAL_OLD_LD_LIBRARY_PATH"
        else
            unset LD_LIBRARY_PATH
        fi
        unset _PYCORAL_ACTIVE _PYCORAL_OLD_LD_LIBRARY_PATH _PYCORAL_OLD_LD_LIBRARY_PATH_SET
    fi
''', 1)
text += '''
_PYCORAL_OLD_LD_LIBRARY_PATH_SET=${LD_LIBRARY_PATH+x}
_PYCORAL_OLD_LD_LIBRARY_PATH=${LD_LIBRARY_PATH-}
export LD_LIBRARY_PATH="$VIRTUAL_ENV/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
_PYCORAL_ACTIVE=1
'''
path.write_text(text)
PY
chroot "$root" /usr/bin/python3 -c 'import urllib.request; urllib.request.urlretrieve("https://bootstrap.pypa.io/pip/3.7/get-pip.py", "/tmp/get-pip.py")'
chroot "$root" /bin/bash -c "source $venv/bin/activate && python /tmp/get-pip.py && python -c 'import ssl, numpy, PIL.Image, pycoral, tflite_runtime; print(\"PyCoral imports OK\")'"
rm "$root/tmp/get-pip.py"
chown -R 1000:1000 "$root$venv"
chroot "$root" systemctl enable NetworkManager ssh avahi-daemon dnsmasq mdt-keymaster usb-gadget usb-gadget-getty-ttyGS0 serial-getty@ttymxc0.service systemd-timesyncd
rm -f "$root/.dockerenv" "$root/usr/sbin/policy-rc.d"
: > "$root/etc/machine-id"
echo "Rootfs prepared: $root"
