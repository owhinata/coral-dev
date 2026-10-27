# Porting Mainline Linux 7.3

This page records how mainline Linux 7.3 was brought up on the Coral Dev Board (first generation, i.MX 8MQ / Phanbell) with the on-board Edge TPU and Wi-Fi working.
The Mendel Linux 5.3 (Eagle) rootfs and U-Boot are kept as they are; only the kernel, DTB and modules are replaced.

## Results

| Item | Mendel (4.14.98-imx) | Mainline 7.3.0-imx-coral+ |
|---|---|---|
| Boot (eMMC rootfs, systemd, login) | OK | OK |
| Edge TPU (PCIe 1ac1:089a) | Gen2 x1, apex/gasket | Gen2 x1, apex/gasket (out-of-tree) |
| PyCoral classify_image.py (parrot.jpg) | Scarlet Macaw 0.75781, 2nd 3.37 ms | Scarlet Macaw 0.75781, 2nd 2.85 ms |
| mobilenet_v2, 1000 consecutive inferences | - | 3.15 ms each, 0 output mismatches, identical after two reboots |
| Wi-Fi (QCA6174) | Qualcomm proprietary driver | ath10k, associates, mdt/SSH reachable |
| USB OTG gadget (mdt) | OK | OK (super-speed, detected by mdt; patch required) |
| eMMC | HS400 | HS200 (HS400 tuning is intermittent, so pinned) |
| Reboot (`reboot`) | OK | OK (via WDOG, patch required) |
| GPU / VPU / HDMI | OK | Not supported yet (Weston fails) |

## Working Directory

Everything lives in `kernel/` in this repository. The source trees (`kernel/linux`, `kernel/gasket-driver`) and build output are ignored by git.

| File | Purpose |
|---|---|
| `kernel/docker/Dockerfile` | Cross-build environment (Ubuntu 24.04 + gcc-aarch64-linux-gnu); the ARM GNU 8.3 toolchain used for Mendel cannot build Linux 7.x |
| `kernel/coral.config` | Kconfig fragment merged on top of the arm64 defconfig |
| `kernel/build.sh` | Runs `config` / `kernel` / `gasket` / `install` inside the container |
| `kernel/deploy.sh` | Copies Image, DTBs and modules to the board without touching existing files |
| `kernel/uboot-boot.py` | Drives U-Boot over the serial console to boot the new kernel once and record the log |
| `kernel/boot/boot.cmd`, `kernel/install-bootscr.sh` | U-Boot script that makes mainline the default (with Mendel fallback) and its installer |
| `kernel/patches/` | Patches against mainline and gasket-driver |

## Procedure

### 1. Build

```bash
git clone --depth 1 --branch v7.3 \
  https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git kernel/linux
git clone --depth 1 https://github.com/google/gasket-driver.git kernel/gasket-driver
(cd kernel/linux && git am ../patches/00*.patch)
(cd kernel/gasket-driver && git apply ../patches/gasket-driver-linux-7.3.patch)

kernel/build.sh image     # build the Docker image
kernel/build.sh all       # config + Image/modules/dtbs + gasket + module staging
```

`CONFIG_LOCALVERSION="-imx-coral"` is deliberate: Mendel's `/usr/bin/usb-gadget-start.sh` identifies the board by checking that `uname -r` contains `imx`.

### 2. Deploy

```bash
kernel/deploy.sh
```

Files are installed as `/boot/Image-<ver>`, `/boot/imx8mq-phanbell-<ver>.dtb` and `/lib/modules/<ver>/`.
The `/boot/Image` symlink (Mendel kernel) and the Mendel DTBs are left in place.

### 3. Make 7.3 the default kernel

```bash
kernel/install-bootscr.sh
```

This compiles `kernel/boot/boot.cmd` with `mkimage` and replaces `/boot/boot.scr` (the original is kept as `/boot/boot.scr.mendel-orig`).
The new script boots mainline when `Image-7.3.0-imx-coral+` and its DTB can be loaded, and otherwise falls back to the original Mendel flow (DTB selection by baseboardid, overlays.txt, M4).
To go back to Mendel, copy `/boot/boot.scr.mendel-orig` over `/boot/boot.scr` or rename `Image-7.3.0-imx-coral+`.

The board boots from eMMC (`/` = mmcblk0p2, `/boot` = mmcblk0p1); the SD card (mmcblk1) is used for `/home` only.

### 4. One-shot manual boot (for testing)

```bash
kernel/uboot-boot.py --version 7.3.0-imx-coral+ --port /dev/ttyUSB0 --reboot --linger 60
```

The script interrupts U-Boot autoboot and runs the commands below. The Mendel U-Boot environment has a bad CRC and falls back to defaults, where `fdt_addr` is undefined, so addresses are given explicitly.
A mainline Image is about 51 MB and would overlap Mendel's DTB address 0x43000000, so the DTB goes to 0x48000000.

```
ext2load mmc 0:1 0x40480000 Image-7.3.0-imx-coral+
ext2load mmc 0:1 0x48000000 imx8mq-phanbell-7.3.0-imx-coral+.dtb
setenv bootargs console=ttymxc0,115200 earlycon=ec_imx6q,0x30860000,115200 root=PARTUUID=<rootfs> rootfstype=ext4 rw rootwait net.ifnames=0 sysrq_always_enabled panic=10
booti 0x40480000 - 0x48000000
```

## Findings

### Device Tree: no PCIe at all

Mainline `arch/arm64/boot/dts/freescale/imx8mq-phanbell.dts` has no PCIe nodes, so neither the Edge TPU nor Wi-Fi is enabled.
The following was added based on the Google DT (`fsl-imx8mq-som.dtsi`) (`patches/0001`, `0002`, `0003`).

| Item | Google DT | Mainline implementation |
|---|---|---|
| Edge TPU (PCIe1 @33c00000) | `ext_osc = <1>`, `reset-gpio` gpio3 18, `vph-supply` LDO7 | `pcie_bus` clock is a 100 MHz `fixed-clock`; `reset-gpio`/`vph-supply` unchanged |
| Edge TPU power | `reg_apex` (gpio3 15, always-on, 500 ms) | Same as a `regulator-fixed` |
| Wi-Fi (PCIe0 @33800000) | `ext_osc = <0>`, `disable-gpio` gpio3 11 (WL_REG_ON), `reset-gpio` gpio3 10 | See "internal refclk" below; WL_REG_ON is a `regulator-fixed` used as `vpcie-supply` |

### Internal reference clock for the Wi-Fi PCIe port

With `ext_osc = 0` the Google driver runs the PHY from the internal CCM 100 MHz clock (GPR14 `REF_USE_PAD = 0`) and feeds the Wi-Fi module's REFCLK from the ANAMIX PLLOUT (SYS_PLL1 800 MHz / 8) on the GPIO1_IO00 pad.
Mainline `imx8mq_pcie_init_phy()` assumes an external oscillator and always sets `REF_USE_PAD`, leaving the PHY without a clock; the next register access stalls the AXI bus and the whole system hangs (the boot log stops right after iATU detection).

Fix (`patches/0003`):

- `pci-imx6.c`: read `fsl,refclk-pad-mode`, the same property the i.MX8MM/8MP PCIe PHY binding uses, and clear `REF_USE_PAD` for `IMX8_PCIE_REFCLK_PAD_UNUSED`. The default keeps the old behaviour.
- DTS: use the existing clock `IMX8MQ_CLK_MON_CLK2_OUT` as `pcie_bus`, with `assigned-clocks` selecting `IMX8MQ_CLK_MON_SEL` → `IMX8MQ_CLK_MON_SYS_PLL1_DIV` at 100 MHz, and add `MX8MQ_IOMUXC_GPIO1_IO00_ANAMIX_REF_CLK_32K` to the pinmux.

### ath10k board data and MAC address

- The linux-firmware `board-2.bin` has no entry for this module's subsystem ID (0000:0000). Falling back to the generic `board.bin` gives continuous `wmi command timeout` right after initialisation.
  Copying Mendel's Qualcomm board data `/lib/firmware/bdwlan30.bin` to `/lib/firmware/ath10k/QCA6174/hw3.0/board.bin` fixes it (the original is kept as `board.bin.mendel-orig`; Mendel itself does not use this file).
- ath10k uses the OTP MAC (`e8:e8:b7:…`), while the NetworkManager profile on the Mendel rootfs is bound to the Google-provisioned MAC (`7c:d9:5c:…`).
  A `wifi@0,0` node under the PCIe0 root port with `local-mac-address` makes the connection come up automatically (`patches/0005`, board-specific value).

### gasket / apex driver

Three changes are needed to build google/gasket-driver (as of 2024-04) as an out-of-tree module for Linux 7.3 (`patches/gasket-driver-linux-7.3.patch`).

| Change | Kernel |
|---|---|
| Drop `.llseek = no_llseek` | `no_llseek` removed in 6.12 |
| `MODULE_IMPORT_NS("DMA_BUF")` (string literal) | 6.13 |
| `zap_vma_ptes()` → `zap_special_vma_range()` | Renamed in 7.1 (same arguments) |

### USB OTG port (gadget for mdt)

Three problems stacked up (`patches/0004`, `0005`, `0007`).

1. **Board detection in Mendel's gadget script**: `usb-gadget-start.sh` checks that `uname -r` contains `imx`, hence `CONFIG_LOCALVERSION="-imx-coral"`.
2. **Type-C role**: the PTN5150 CC logic is strapped as DFP (host) and the mainline driver never writes the CONTROL register, so the PC ended up as the device and supplied no VBUS. The Google driver programs DRP and then UFP at start-up.
   `extcon-ptn5150.c` now programs the port mode from the `connector` child node's `power-role` (`sink` → UFP, `source` → DFP, `dual` → DRP), and the DTS carries `connector { power-role = "sink"; data-role = "device"; }`. dwc3 is pinned to `dr_mode = "peripheral"`.
3. **dwc3 USB3 PHY suspend**: even with the above, dwc3 received no events at all (GEVNTCOUNT = 0, link state SS.Disabled) and the host never saw a pull-up. Register comparison with Mendel showed only minor differences, but `snps,dis_u3_susphy_quirk` (keep GUSB3PIPECTL.SUSPHY clear) makes the connection work. `snps,dis_u2_susphy_quirk` alone does not.

### Reboot hangs

Mainline stops right after `reboot: Restarting system` because PSCI SYSTEM_RESET never returns.
The Mendel kernel also uses PSCI, but there imx2-wdt is still running at shutdown (`Device shutdown: Expect reboot!`) and the WDOG resets the board one second later, which hides the problem.
The imx2-wdt restart handler priority was raised to 192, above PSCI (129), so the WDOG performs the reset (`patches/0006`).

### eMMC HS400

HS400 tuning succeeds or fails depending on the boot (`mmc_select_hs400 failed, error -84`); on failure the rootfs is never found and boot stalls in `rootwait`. `usdhc1` carries `no-mmc-hs400` to pin HS200.

## Open Issues

- GPU (etnaviv), VPU and HDMI output (Weston)
- snvs RTC probe failure (-110)
- eMMC HS400
- Upstream-ready form of `fsl,refclk-pad-mode`, the PTN5150 port-mode setting and the WDOG priority change

## References

- Google kernel: [coral/linux-imx](https://coral.googlesource.com/linux-imx/) (`arch/arm64/boot/dts/freescale/fsl-imx8mq-som.dtsi`, `drivers/pci/dwc/pci-imx6.c`)
- Mainline: [imx8mq-phanbell.dts (v7.3)](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/arch/arm64/boot/dts/freescale/imx8mq-phanbell.dts?h=v7.3), [pci-imx6.c (v7.3)](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/pci/controller/dwc/pci-imx6.c?h=v7.3)
- [google/gasket-driver](https://github.com/google/gasket-driver)
