# Mainline Linux 7.3 への移植

Coral Dev Board（初代、i.MX 8MQ / Phanbell）で Mainline Linux 7.3 を起動し、内蔵 Edge TPU と Wi-Fi を動作させた記録です。
Mendel Linux 5.3 (Eagle) の rootfs と U-Boot はそのまま使い、カーネル・DTB・モジュールだけを差し替えています。

## 結果

| 項目 | Mendel (4.14.98-imx) | Mainline 7.3.0-imx-coral+ |
|---|---|---|
| 起動（eMMC rootfs、systemd、ログイン） | OK | OK |
| Edge TPU (PCIe 1ac1:089a) | Gen2 x1、apex/gasket | Gen2 x1、apex/gasket（外部モジュール） |
| PyCoral classify_image.py (parrot.jpg) | Scarlet Macaw 0.75781、2nd 3.37 ms | Scarlet Macaw 0.75781、2nd 2.85 ms |
| mobilenet_v2 1000 回連続推論 | - | 3.15 ms/回、出力不一致 0、2 回の再起動後も同一 |
| Wi-Fi (QCA6174) | Qualcomm 独自ドライバ | ath10k、AP 接続、mdt/SSH 到達 |
| USB OTG ガジェット (mdt) | OK | OK（super-speed、mdt 検出。要パッチ） |
| eMMC | HS400 | HS200（HS400 チューニングが不安定なため固定） |
| 再起動 (`reboot`) | OK | OK（WDOG 経由。要パッチ） |
| GPU / VPU / HDMI | OK | 未対応（Weston 起動失敗） |

## 作業ディレクトリ

リポジトリの `kernel/` に一式があります。ソースツリー（`kernel/linux`、`kernel/gasket-driver`）とビルド出力は `.gitignore` 対象です。

| ファイル | 役割 |
|---|---|
| `kernel/docker/Dockerfile` | クロスビルド環境（Ubuntu 24.04 + gcc-aarch64-linux-gnu）。Mendel 向け ARM GNU 8.3 は Linux 7.x をビルドできない |
| `kernel/coral.config` | arm64 defconfig にマージする Kconfig フラグメント |
| `kernel/build.sh` | `config` / `kernel` / `gasket` / `install` をコンテナ内で実行 |
| `kernel/deploy.sh` | Image・DTB・モジュールをボードへ配置（既存ファイルは変更しない） |
| `kernel/uboot-boot.py` | シリアル経由で U-Boot を操作し、新カーネルを 1 回だけ起動して起動ログを記録 |
| `kernel/boot/boot.cmd`、`kernel/install-bootscr.sh` | 既定起動を Mainline にする U-Boot スクリプト（Mendel フォールバック付き）とその導入 |
| `kernel/patches/` | Mainline と gasket-driver への差分 |

## 手順

### 1. ビルド

```bash
git clone --depth 1 --branch v7.3 \
  https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git kernel/linux
git clone --depth 1 https://github.com/google/gasket-driver.git kernel/gasket-driver
(cd kernel/linux && git am ../patches/00*.patch)
(cd kernel/gasket-driver && git apply ../patches/gasket-driver-linux-7.3.patch)

kernel/build.sh image     # Docker イメージ作成
kernel/build.sh all       # config + Image/modules/dtbs + gasket + モジュールステージング
```

`CONFIG_LOCALVERSION="-imx-coral"` にしているのは、Mendel の `/usr/bin/usb-gadget-start.sh` が `uname -r` に `imx` を含むかで機種判定しているためです。

### 2. デプロイ

```bash
kernel/deploy.sh
```

`/boot/Image-<ver>`、`/boot/imx8mq-phanbell-<ver>.dtb`、`/lib/modules/<ver>/` に配置します。
`/boot/Image` のシンボリックリンク（Mendel カーネル）と Mendel の DTB はそのまま残します。

### 3. 既定のカーネルを 7.3 にする

```bash
kernel/install-bootscr.sh
```

`kernel/boot/boot.cmd` を `mkimage` で `boot.scr` にして `/boot/boot.scr` を置き換えます（元の boot.scr は `/boot/boot.scr.mendel-orig` に保存）。
新しいスクリプトは `Image-7.3.0-imx-coral+` と対応する DTB を読み込めれば Mainline を、読み込めなければ従来の Mendel の起動手順（baseboardid による DTB 選択、overlays.txt、M4）にフォールバックします。
Mendel に戻すには `/boot/boot.scr.mendel-orig` を `/boot/boot.scr` にコピーするか、`Image-7.3.0-imx-coral+` をリネームします。

ボードは eMMC ブート（`/` = mmcblk0p2、`/boot` = mmcblk0p1）で、SD カード（mmcblk1）は `/home` にのみ使われています。

### 4. 手動での 1 回限りの起動（検証用）

```bash
kernel/uboot-boot.py --version 7.3.0-imx-coral+ --port /dev/ttyUSB0 --reboot --linger 60
```

U-Boot の autoboot を中断し、以下を実行します。Mendel の U-Boot 環境は CRC エラーでデフォルト値になっており `fdt_addr` が未定義なため、アドレスは明示します。
Mainline の Image は約 51 MB あり、Mendel が使う DTB アドレス 0x43000000 と重なるので DTB は 0x48000000 に置きます。

```
ext2load mmc 0:1 0x40480000 Image-7.3.0-imx-coral+
ext2load mmc 0:1 0x48000000 imx8mq-phanbell-7.3.0-imx-coral+.dtb
setenv bootargs console=ttymxc0,115200 earlycon=ec_imx6q,0x30860000,115200 root=PARTUUID=<rootfs> rootfstype=ext4 rw rootwait net.ifnames=0 sysrq_always_enabled panic=10
booti 0x40480000 - 0x48000000
```

## 調査結果

### Device Tree: PCIe が存在しない

Mainline の `arch/arm64/boot/dts/freescale/imx8mq-phanbell.dts` には PCIe ノードが一切なく、Edge TPU も Wi-Fi も有効になりません。
Google 版 DT（`fsl-imx8mq-som.dtsi`）との差分から以下を追加しました（`patches/0001`、`0002`、`0003`）。

| 項目 | Google 版 | Mainline 向け実装 |
|---|---|---|
| Edge TPU (PCIe1 @33c00000) | `ext_osc = <1>`、`reset-gpio` gpio3 18、`vph-supply` LDO7 | `pcie_bus` クロックを 100 MHz `fixed-clock` に、`reset-gpio`/`vph-supply` は同じ |
| Edge TPU 電源 | `reg_apex` (gpio3 15、always-on、500 ms) | `regulator-fixed` として同内容を移植 |
| Wi-Fi (PCIe0 @33800000) | `ext_osc = <0>`、`disable-gpio` gpio3 11 (WL_REG_ON)、`reset-gpio` gpio3 10 | 下記「内部 refclk」参照。WL_REG_ON は `regulator-fixed` + `vpcie-supply` |

### Wi-Fi PCIe の内部リファレンスクロック

Google 版ドライバは `ext_osc = 0` のとき、PHY を CCM 内部の 100 MHz で駆動し（GPR14 `REF_USE_PAD = 0`）、Wi-Fi モジュール向けの REFCLK を ANAMIX PLLOUT（SYS_PLL1 800 MHz ÷ 8）から GPIO1_IO00 ピンに出力します。
Mainline の `imx8mq_pcie_init_phy()` は外部オシレータ前提で `REF_USE_PAD` を無条件に立てるため、PHY が無クロックになり、レジスタアクセスで AXI バスが停止してシステム全体がハングしました（起動ログは iATU 検出直後で停止）。

対策（`patches/0003`）:

- `pci-imx6.c`: i.MX8MM/8MP の PHY バインディングと同じ `fsl,refclk-pad-mode` を読み、`IMX8_PCIE_REFCLK_PAD_UNUSED` なら `REF_USE_PAD` を 0 にする。未指定時は従来動作。
- DTS: `pcie_bus` に Mainline 既存のクロック `IMX8MQ_CLK_MON_CLK2_OUT` を指定し、`assigned-clocks` で `IMX8MQ_CLK_MON_SEL` → `IMX8MQ_CLK_MON_SYS_PLL1_DIV` (100 MHz) を設定。ピンマルチプレクサに `MX8MQ_IOMUXC_GPIO1_IO00_ANAMIX_REF_CLK_32K` を追加。

### ath10k のボードデータと MAC アドレス

- linux-firmware の `board-2.bin` には本機のサブシステム ID (0000:0000) のエントリが無く、汎用 `board.bin` にフォールバックすると初期化直後から `wmi command timeout` が連続します。
  Mendel 同梱の Qualcomm 用ボードデータ `/lib/firmware/bdwlan30.bin` を `/lib/firmware/ath10k/QCA6174/hw3.0/board.bin` にコピーすると解消しました（元ファイルは `board.bin.mendel-orig` として保存。Mendel 自身は使用しません）。
- ath10k は OTP の MAC (`e8:e8:b7:…`) を使いますが、Mendel の NetworkManager プロファイルは Google 割当の MAC (`7c:d9:5c:…`) に紐づいています。
  DTS の PCIe0 ルートポート配下に `wifi@0,0` ノードを置き `local-mac-address` で渡すことで自動接続するようになりました（`patches/0005`、ボード固有値）。

### gasket / apex ドライバ

google/gasket-driver（2024-04 時点）を Linux 7.3 向け外部モジュールとしてビルドするには 3 点の修正が必要です（`patches/gasket-driver-linux-7.3.patch`）。

| 変更 | カーネル |
|---|---|
| `.llseek = no_llseek` の削除 | 6.12 で `no_llseek` 廃止 |
| `MODULE_IMPORT_NS("DMA_BUF")` （文字列化） | 6.13 |
| `zap_vma_ptes()` → `zap_special_vma_range()` | 7.1 で改名（同じ引数） |

### USB OTG ポート（mdt 用ガジェット）

3 つの問題が重なっていました（`patches/0004`、`0005`、`0007`）。

1. **Mendel のガジェットスクリプトの機種判定**: `usb-gadget-start.sh` は `uname -r` に `imx` を含むかで判定するため、`CONFIG_LOCALVERSION="-imx-coral"` にしました。
2. **Type-C のロール**: PTN5150（CC ロジック）はストラップで DFP（ホスト）になっており、Mainline ドライバは CONTROL レジスタを書き換えないため、PC 側がデバイスになって VBUS も供給されませんでした。Google ドライバは起動時に DRP → UFP を設定しています。
   Mainline の `extcon-ptn5150.c` に、`connector` 子ノードの `power-role`（`sink` → UFP、`source` → DFP、`dual` → DRP）からポートモードを設定する処理を追加し、DTS に `connector { power-role = "sink"; data-role = "device"; }` を置きました。dwc3 は `dr_mode = "peripheral"` に固定しています。
3. **dwc3 の USB3 PHY サスペンド**: 上記を直しても dwc3 がイベントを一切受け取らず（GEVNTCOUNT = 0、リンク状態 SS.Disabled）、ホストはプルアップを検出しませんでした。Mendel と dwc3/PHY のレジスタを比較しても差は僅かでしたが、`snps,dis_u3_susphy_quirk`（GUSB3PIPECTL.SUSPHY を立てない）で接続するようになりました。`snps,dis_u2_susphy_quirk` 単独では接続しません。

### 再起動が固まる

Mainline では `reboot: Restarting system` の直後で停止します。PSCI SYSTEM_RESET が戻ってこないためです。
Mendel カーネルでも PSCI を使いますが、シャットダウン時に imx2-wdt が稼働中（`Device shutdown: Expect reboot!`）で 1 秒後に WDOG がリセットするため問題が見えません。
imx2-wdt の restart ハンドラ優先度を PSCI (129) より高い 192 にして WDOG で再起動するようにしました（`patches/0006`）。

### eMMC HS400

HS400 のチューニングが起動ごとに成功・失敗（`mmc_select_hs400 failed, error -84`）し、失敗時は rootfs が見つからず `rootwait` で止まります。`usdhc1` に `no-mmc-hs400` を付けて HS200 に固定しています。

## 未解決の課題

- GPU (etnaviv)・VPU・HDMI 出力（Weston）
- snvs RTC の probe 失敗 (-110)
- eMMC HS400
- `fsl,refclk-pad-mode`、PTN5150 のポートモード設定、WDOG 優先度変更の upstream 向け整理

## 参考

- Google 版カーネル: [coral/linux-imx](https://coral.googlesource.com/linux-imx/)（`arch/arm64/boot/dts/freescale/fsl-imx8mq-som.dtsi`、`drivers/pci/dwc/pci-imx6.c`）
- Mainline: [imx8mq-phanbell.dts (v7.3)](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/arch/arm64/boot/dts/freescale/imx8mq-phanbell.dts?h=v7.3)、[pci-imx6.c (v7.3)](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/pci/controller/dwc/pci-imx6.c?h=v7.3)
- [google/gasket-driver](https://github.com/google/gasket-driver)
