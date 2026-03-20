# Move /home to SD Card

## Overview

The Coral Dev Board's eMMC (7.3GB) is partitioned by default into / (5.1GB) and /home (2.0GB).
The /home partition is insufficient for large files such as AI models.
This guide reconfigures the eMMC as a single / partition and mounts an SD card as /home.

### Final Configuration

| Device | Mount | Size | Purpose |
|---|---|---|---|
| mmcblk0p1 (eMMC) | /boot | 128MB | Boot partition |
| mmcblk0p2 (eMMC) | / | ~7.1GB | Root filesystem |
| mmcblk1p1 (SD) | /home | SD card capacity | Home directory |

## Prerequisites

- SD card (16GB or larger recommended)
- USB serial adapter (for U-Boot console)
- USB-C cable (OTG port connection, for fastboot)
- `fastboot` installed on host PC

## 1. Obtain the Flash Package

Download and extract the Mendel Linux flash package:

```bash
curl -O https://dl.google.com/coral/mendel/enterprise/enterprise-eagle-20211117215217.zip
unzip enterprise-eagle-20211117215217.zip
```

The package contains the following files:

| File | Description |
|---|---|
| `recovery.img` | U-Boot image (for SD card boot) |
| `u-boot.imx` | Bootloader |
| `boot_arm64.img` | Kernel + initramfs |
| `rootfs_arm64.img` | Root filesystem (Android sparse image) |
| `partition-table-8gb.img` | Default GPT partition table |
| `flash.sh` | Flash script |

## 2. Create a Custom Partition Table

Create a custom GPT that changes the default eMMC layout (boot + misc + home + rootfs)
to a 2-partition layout (boot + rootfs).

```bash
# Create a virtual disk matching eMMC size (8GB eMMC = 15269888 sectors)
truncate -s $((15269888 * 512)) disk-custom.img

# Create partition table
sgdisk -Z disk-custom.img
sgdisk \
  -n 1:16384:278527 -t 1:8300 -c 1:boot \
  -n 2:278528:0 -t 2:8300 -c 2:rootfs \
  disk-custom.img
```

!!! warning "PARTUUID Must Match"
    The kernel locates the root partition by PARTUUID.
    You must check the original rootfs partition's PARTUUID and set the same value in the custom GPT.

    ```bash
    # Check the original PARTUUID (parse GPT with Python)
    python3 -c "
    import struct
    with open('enterprise-eagle-20211117215217/partition-table-8gb.img', 'rb') as f:
        data = f.read()
    entry = data[1024 + 3 * 128 : 1024 + 4 * 128]  # 4th partition (rootfs)
    guid = entry[16:32]
    u = struct.unpack_from('<IHH', guid, 0)
    rest = guid[8:16]
    print(f'{u[0]:08x}-{u[1]:04x}-{u[2]:04x}-{rest[0]:02x}{rest[1]:02x}-'
          f'{rest[2]:02x}{rest[3]:02x}{rest[4]:02x}{rest[5]:02x}{rest[6]:02x}{rest[7]:02x}')
    "
    ```

    Then specify the PARTUUID with the `-u 2:<PARTUUID>` option:

    ```bash
    sgdisk -Z disk-custom.img
    sgdisk \
      -n 1:16384:278527 -t 1:8300 -c 1:boot \
      -u 1:<boot PARTUUID> \
      -n 2:278528:0 -t 2:8300 -c 2:rootfs \
      -u 2:<rootfs PARTUUID> \
      disk-custom.img
    ```

Extract the GPT image:

```bash
dd if=disk-custom.img of=partition-table-custom.img bs=512 count=34
dd if=disk-custom.img of=partition-table-custom.img bs=512 \
  skip=$((15269888 - 33)) count=33 seek=34
```

## 3. Modify fstab

Modify fstab in the rootfs image to match the new partition layout.

`simg2img` / `img2simg` (from the `android-sdk-libsparse-utils` package) are required:

```bash
sudo apt install android-sdk-libsparse-utils
```

```bash
# Convert sparse image to raw image
simg2img enterprise-eagle-20211117215217/rootfs_arm64.img rootfs_raw.img

# Mount and modify fstab
sudo mkdir -p /mnt/rootfs
sudo mount -o loop rootfs_raw.img /mnt/rootfs
```

Replace fstab with the following:

```bash
sudo tee /mnt/rootfs/etc/fstab << 'EOF'
/dev/mmcblk0p2 / ext4 noatime,defaults 0 1
/dev/mmcblk0p1 /boot ext2 noatime,defaults 0 2
tmpfs /var/log tmpfs defaults 0 0
EOF
```

```bash
sudo umount /mnt/rootfs

# Convert raw image back to sparse image
img2simg rootfs_raw.img rootfs_custom.img
```

## 4. Boot from SD Card

Write recovery.img to the SD card:

```bash
# Replace <device> with your SD card device path (e.g., /dev/sda)
sudo dd if=enterprise-eagle-20211117215217/recovery.img of=<device> bs=4M status=progress
sync
```

Board setup:

1. Power off the board
2. Set boot switches to SD mode

    | Switch | 1 | 2 | 3 | 4 |
    |---|---|---|---|---|
    | SD mode | ON | OFF | ON | ON |

3. Insert the SD card
4. Connect USB serial adapter
5. Connect USB-C to OTG port
6. Power on

At the U-Boot prompt (`=>`) on the serial console (115200bps):

```
fastboot 0
```

## 5. Flash the eMMC

Flash from the host PC via fastboot. Serial console interaction is required between steps.

```bash
# Step 1: Write bootloader
sudo fastboot flash bootloader0 enterprise-eagle-20211117215217/u-boot.imx
sudo fastboot reboot-bootloader
# → Run fastboot 0 on serial console

# Step 2: Write custom partition table
sudo fastboot flash gpt partition-table-custom.img
sudo fastboot reboot-bootloader
# → Run fastboot 0 on serial console

# Step 3: Write kernel and rootfs
sudo fastboot flash boot enterprise-eagle-20211117215217/boot_arm64.img
sudo fastboot flash rootfs rootfs_custom.img
sudo fastboot reboot
```

## 6. Boot from eMMC

1. Power off the board
2. Remove the SD card
3. Set boot switches back to eMMC mode

    | Switch | 1 | 2 | 3 | 4 |
    |---|---|---|---|---|
    | eMMC mode | ON | OFF | OFF | OFF |

4. Power on

Verify after boot:

```bash
df -h
```

Expected output:

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       7.1G  1.5G  5.3G  22% /
...
/dev/mmcblk0p1  124M   30M   88M  26% /boot
```

## 7. Mount SD Card as /home

Insert the SD card into the board and set it up as /home:

```bash
# Create partition
sudo fdisk /dev/mmcblk1 << 'EOF'
n
p
1


w
EOF

# Format as ext4
sudo mkfs.ext4 -L home /dev/mmcblk1p1

# Copy current /home
sudo mkdir -p /mnt/sd
sudo mount /dev/mmcblk1p1 /mnt/sd
sudo rsync -aAX /home/ /mnt/sd/

# Add to fstab
echo '/dev/mmcblk1p1 /home ext4 noatime,nosuid,nodev,defaults 0 3' | sudo tee -a /etc/fstab

# Mount
sudo umount /mnt/sd
sudo mount /home
```

Verify:

```bash
df -h
```

Expected output:

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       7.1G  1.5G  5.3G  22% /
...
/dev/mmcblk0p1  124M   30M   88M  26% /boot
/dev/mmcblk1p1  234G   61M  222G   1% /home
```

## Verification

Verify mdt connectivity and app deploy/run from the host PC:

```bash
mdt devices
cmake --build build/<app> --target deploy
cmake --build build/<app> --target run
```

!!! note "Hostname Change"
    Re-flashing the eMMC changes the board's hostname.
    Use `mdt devices` to check the new hostname.

## Troubleshooting

### Boot hangs at "Waiting for root device PARTUUID=..."

The rootfs partition PARTUUID in the custom GPT does not match the original.
Review "2. Create a Custom Partition Table" and set the correct PARTUUID.

### Boot times out with "A start job is running for /dev/mmcblk0p3"

The fstab still references an old partition (/dev/mmcblk0p3).
Follow "3. Modify fstab" to fix fstab in the rootfs image.

### Device names mmcblk0 / mmcblk1 are swapped

When booting from SD card, device numbers may be swapped.
Use `lsblk` to identify the correct device by size:

- eMMC: approximately 7.3GB
- SD card: depends on card capacity

### /home permissions are broken

Always use the `-aAX` options with rsync when copying.
If permissions are corrupted:

```bash
sudo chown -R mendel:mendel /home/mendel
sudo chmod 755 /home/mendel
```
