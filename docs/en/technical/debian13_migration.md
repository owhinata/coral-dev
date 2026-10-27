# Migrating the Coral Dev Board to Debian 13

This records the migration of an original i.MX 8MQ / Phanbell Coral Dev Board from Mendel Linux 5 to Debian 13. First boot a separate trial SD card, back up the eMMC to the PC, install the new root filesystem, and restore the original `/home` SD card.

!!! warning "Device-specific scripts"
    The eMMC and home scripts check the partition layout and UUIDs of the board used for this migration. They stop on other layouts. Before adapting them to another board, inspect its devices with `lsblk -f` and keep a serial console connected.

## Verified setup and limitations

| Component | Result |
|---|---|
| `/` | eMMC `mmcblk0p2`, Debian 13.7 |
| `/boot` | eMMC `mmcblk0p1`, existing U-Boot and mainline 7.3.0-imx-coral+ |
| `/home` | Original SD `mmcblk1p1`, UUID `395738a2-5c37-4441-aa21-78126cbb9a0c` |
| Wi-Fi / mdt | Wi-Fi, `mdt devices`, and `mdt exec` verified |
| Edge TPU / PyCoral | Inference as a normal user through `/dev/apex_0` verified |
| Time | `systemd-timesyncd` used because the RTC does not work |

USB gadget services started, but mdt over USB was not tested. C++ TensorFlow Lite development libraries and headers are not installed. PyCoral uses Python 3.7 and older libraries copied from Mendel. On the current board, run `source ~/.venvs/pycoral/bin/activate` and use `python`; Debian's system `python3` remains at version 3.13. Python 3.7 is end-of-life.

The migration script creates the venv and pip in `/home/mendel/.venvs/pycoral`. It copies Python packages and native libraries from Mendel and downloads pip over the network. To use it on the board:

```bash
source ~/.venvs/pycoral/bin/activate
python -c 'import ssl, numpy, PIL.Image, pycoral, tflite_runtime'
python -m pip --version
```

Run `deactivate` when finished. The copied packages were not installed through pip and are not managed by it.

## Prerequisites

- A serial console, a separate expendable SD card of at least 8 GB, and the original `/home` SD card.
- The original Mendel environment with the `mendel` SSH key, Wi-Fi configuration, Python 3.7, PyCoral, Edge TPU runtime, `mdt-services`, and `usb-gadget`. The rootfs preparation script copies these files; it cannot prepare a fresh rootfs from Debian alone.
- The patched [mainline kernel](linux_mainline_port.md), version 7.3.0-imx-coral+, running on the board, with its Image and DTB in `kernel/out/`. The Wi-Fi board data and DTB are specific to the board.
- Docker, `sgdisk`, `partprobe`, `mkimage` (u-boot-tools), `e2fsprogs`, `python3`, SSH, `gzip`, and enough backup space on the PC. The board needs network access.
- Run host commands from the repository root. Set `export CORAL_IP=<board-ip>` if automatic detection fails.

## 1. Prepare the rootfs

On the PC, export the arm64 Debian base image and transfer it to the original Mendel system:

```bash
mkdir -p build
docker pull --platform linux/arm64 debian:13
docker create --platform linux/arm64 --name coral-debian13-base debian:13
docker export -o build/debian13-arm64-base.tar coral-debian13-base
docker rm coral-debian13-base
CORAL_DEPLOY_DIR=/home/mendel/debian13-build scripts/deploy.sh \
  build/debian13-arm64-base.tar:base.tar \
  kernel/debian13/prepare-rootfs.sh:prepare-rootfs.sh
```

Log into the board, for example with `mdt shell`, and run the following. The output directory must not exist; partial files are not automatically removed on failure.

```bash
sudo bash /home/mendel/debian13-build/prepare-rootfs.sh \
  /home/mendel/debian13-build/base.tar /home/mendel/debian13-build/rootfs
```

The result includes the existing account password hash, SSH public keys, NetworkManager profiles, board Wi-Fi firmware, kernel modules, mdt services, and PyCoral files. The rootfs and archive contain private configuration.

On the PC, export the prepared rootfs; the board's sudo password is entered at the terminal and is not saved:

```bash
kernel/debian13/export-rootfs.sh /home/mendel/debian13-build/rootfs build/debian13-rootfs.tar
```

## 2. Create and boot a trial SD card

Extract `recovery.img` from the [official Coral flash package](https://coral.ai/docs/dev-board/reflash/). On the PC, identify the expendable card with `lsblk` and unmount all its partitions. `<sd-device>` is the **whole disk to erase**, for example `/dev/sda`:

```bash
sudo kernel/debian13/write-sd.sh --write <sd-device> <recovery.img> \
  build/debian13-rootfs.tar kernel/out/arch/arm64/boot/Image \
  kernel/out/arch/arm64/boot/dts/freescale/imx8mq-phanbell.dtb
```

This command erases the selected disk. Power off, insert the trial card, set the switches to SD mode (1 ON, 2 OFF, 3 ON, 4 ON), and monitor the serial console during boot. Verify Wi-Fi, SSH, `mdt devices`, and inference with a real model using `python` in the activated venv. APT signature checks may fail until the clock synchronizes.

## 3. Back up eMMC to the PC

While the board runs from the trial SD, run the following on the PC with a new backup directory:

```bash
kernel/debian13/backup-emmc.sh backups/emmc-before-debian13
```

The script prompts for the board's sudo password, compresses the eMMC user area and boot areas 0 and 1, and checks decompressed sizes and checksums. Backups contain private data. The backup from this migration is in `backups/emmc-before-debian13/`; `SHA256SUMS` can be used to recheck it. The separate `/home` SD card is **not** included. Restoration requires booting from a different device and checking the target and boot-area write protection.

## 4. Install to eMMC

After verifying both the backup and trial boot, transfer the installer:

```bash
CORAL_DEPLOY_DIR=/home/mendel/debian13-build scripts/deploy.sh \
  kernel/debian13/install-emmc.sh:install-emmc.sh
```

Log into the board while it is running from the trial SD and run the following. It formats the eMMC root partition. It checks the existing eMMC `/boot` read-only and proceeds only if its kernel and DTB match the trial SD. It does not change the partition table or eMMC U-Boot.

```bash
sudo bash /home/mendel/debian13-build/install-emmc.sh --write-emmc
sudo poweroff
```

Disconnect power, set eMMC mode (1 ON, 2 OFF, 3 OFF, 4 OFF), and boot. Verify `findmnt /`, `findmnt /boot`, `mdt devices`, and PyCoral inference. Keep the trial SD for recovery.

## 5. Restore the original `/home` SD

Shut down, disconnect power, replace the trial card with the original home card, and boot in eMMC mode. Verify the UUID with `lsblk -f` and transfer the script from the PC:

```bash
CORAL_DEPLOY_DIR=/home/mendel/debian13-build scripts/deploy.sh \
  kernel/debian13/restore-home.sh:restore-home.sh
```

Log into the board and run the commands below. Existing SD files are not overwritten; new files from the eMMC `/home` are copied. If a PyCoral venv already exists on the SD, it is preserved without merging. If the SSH keys differ, the script stops so they can be reviewed and merged manually.

```bash
sudo bash /home/mendel/debian13-build/restore-home.sh --mount-home
sudo reboot
```

After reboot, verify `findmnt /home`, the original files, SSH, and inference. The previous `fstab` is saved as `/etc/fstab.before-home-sd`.

Equivalent steps were tested on the board during this migration. The cleaned-up reusable scripts have not been rerun end to end from a fresh Mendel installation.
