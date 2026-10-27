# kernel/ — Mainline Linux 7.3 for Coral Dev Board

Build, deploy and one-shot boot of a mainline kernel (with Edge TPU and Wi-Fi) on the
Coral Dev Board while keeping the Mendel rootfs and U-Boot untouched.
Full write-up: `docs/ja/technical/linux_mainline_port.md` / `docs/en/technical/linux_mainline_port.md`.
The Debian 13 rootfs migration, including scripts and backup procedures, is documented in
`docs/ja/technical/debian13_migration.md` / `docs/en/technical/debian13_migration.md`.

```bash
git clone --depth 1 --branch v7.3 https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git kernel/linux
git clone --depth 1 https://github.com/google/gasket-driver.git kernel/gasket-driver
(cd kernel/linux && git am ../patches/00*.patch)
(cd kernel/gasket-driver && git apply ../patches/gasket-driver-linux-7.3.patch)
kernel/build.sh image && kernel/build.sh all
kernel/deploy.sh
kernel/uboot-boot.py --version 7.3.0-imx-coral+ --port /dev/ttyUSB0 --reboot --linger 60   # one-shot test boot
kernel/install-bootscr.sh                                                                # make mainline the default
```

- `build.sh`, `coral.config`, `docker/` — cross build inside Docker (`coral-kernel-builder`)
- `deploy.sh` — installs `/boot/Image-<ver>`, `/boot/imx8mq-phanbell*-<ver>.dtb`, `/lib/modules/<ver>/`
- `uboot-boot.py` — serial-console U-Boot automation (`--dtb`, `--extra-bootargs`, `--linger`, `--reboot-sysrq`)
- `serial-run.py` — run commands over the serial console (needs a login)
- `boot/boot.cmd`, `install-bootscr.sh` — default-boot U-Boot script (mainline, Mendel fallback)
- `patches/` — kernel (0001–0007) and gasket-driver patches
