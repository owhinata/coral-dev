# Coral Dev Board を Debian 13 に移行する

初代 Coral Dev Board（i.MX 8MQ / Phanbell）で、Mendel Linux 5 の eMMC から Debian 13 に移行した記録と再作成手順です。先に別の SD カードで試し、eMMC を PC にバックアップしてから書き換えます。最後に元の `/home` 用 SD カードを戻します。

!!! warning "対象の確認"
    以下のスクリプトは今回のボードのパーティション構成と UUID を前提とします。`install-emmc.sh` と `restore-home.sh` は別の構成では停止します。別のボードに流用するときは、シリアルコンソールと `lsblk -f` で実機の構成を調べ、スクリプトを見直してください。

## 確認した構成と制限

| 項目 | 今回の結果 |
|---|---|
| `/` | eMMC `mmcblk0p2`、Debian 13.7 |
| `/boot` | eMMC `mmcblk0p1`、既存 U-Boot と Mainline 7.3.0-imx-coral+ |
| `/home` | 元の SD カード `mmcblk1p1`、UUID `395738a2-5c37-4441-aa21-78126cbb9a0c` |
| Wi-Fi / mdt | Wi-Fi 接続と `mdt devices` / `mdt exec` を確認 |
| Edge TPU / PyCoral | `/dev/apex_0` を一般ユーザーで利用し、推論を確認 |
| 時刻 | RTC が動作しないため `systemd-timesyncd` を使用 |

USB gadget のサービスは起動しましたが、USB 経由の mdt 接続は未検証です。C++ 開発用 TensorFlow Lite とヘッダーは未導入です。PyCoral は Mendel からコピーした Python 3.7 と古いライブラリで動かします。現在のボードでは `source ~/.venvs/pycoral/bin/activate` で venv を有効にして `python` を実行します。Debian のシステム `python3` は 3.13 のままです。Python 3.7 は保守終了済みです。

移行スクリプトは `/home/mendel/.venvs/pycoral` に venv と pip を作成します。Python パッケージとネイティブライブラリを Mendel からコピーし、pip はネットワークから取得します。利用時はボード上で次を実行します。

```bash
source ~/.venvs/pycoral/bin/activate
python -c 'import ssl, numpy, PIL.Image, pycoral, tflite_runtime'
python -m pip --version
```

終了時は `deactivate` を実行します。コピーされたパッケージは pip の管理対象としてインストールされたものではありません。

## 前提

- シリアルコンソール、電源を切って交換できる **試験用 SD カード**（8 GB 以上）と既存の `/home` 用 SD カード。
- Mendel を保存した元の環境で `mendel` の SSH 鍵、Wi-Fi 設定、Python 3.7、PyCoral、Edge TPU ランタイム、`mdt-services`、`usb-gadget` が利用可能なこと。`prepare-rootfs.sh` はこれらをコピーするため、移行済み Debian だけからの新規作成には使えません。
- [Mainline カーネル移植](linux_mainline_port.md)の 7.3.0-imx-coral+ が元のボードで稼働し、`kernel/out/` に Image と DTB があること。ボード固有の Wi-Fi board data と DTB を使います。
- PC に Docker、`sgdisk`、`partprobe`、`mkimage`（u-boot-tools）、`e2fsprogs`、`python3`、SSH、`gzip`、十分なバックアップ空き領域。ボードにネットワーク接続が必要です。
- コマンドはリポジトリのルートから実行します。IP が自動検出できない場合は `export CORAL_IP=<ボードのIP>` を指定します。

## 1. Debian 13 rootfs を準備

PC で arm64 ベースを取得し、元の Mendel ボードに転送します。イメージ取得にネットワークが必要です。

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

ボードに `mdt shell` などでログインし、以下を実行します。出力先は存在しないディレクトリにしてください。失敗時の途中ファイルは自動削除しません。

```bash
sudo bash /home/mendel/debian13-build/prepare-rootfs.sh \
  /home/mendel/debian13-build/base.tar /home/mendel/debian13-build/rootfs
```

ボードのパスワード、SSH 公開鍵、NetworkManager 接続設定、Wi-Fi ファームウェア、カーネルモジュール、mdt サービス、PyCoral 関連ファイルを rootfs にコピーします。接続設定などの秘密情報を含むため、rootfs と次の tar は慎重に扱ってください。

PC 側で rootfs を取得します。sudo のパスワードは端末から入力し、保存しません。

```bash
kernel/debian13/export-rootfs.sh /home/mendel/debian13-build/rootfs build/debian13-rootfs.tar
```

## 2. 試験用 SD カードを作成して起動

[Coral の公式フラッシュパッケージ](https://coral.ai/docs/dev-board/reflash/)から `recovery.img` を取り出します。PC で `lsblk` を使って試験用 SD のデバイスを特定し、全パーティションをアンマウントしてください。以下の `<sd-device>` は**消去してよいカード全体**（例: `/dev/sda`）です。

```bash
sudo kernel/debian13/write-sd.sh --write <sd-device> <recovery.img> \
  build/debian13-rootfs.tar kernel/out/arch/arm64/boot/Image \
  kernel/out/arch/arm64/boot/dts/freescale/imx8mq-phanbell.dtb
```

このコマンドは指定ディスクを消去します。書き込み後に電源を切り、試験用 SD を挿入してスイッチを SD モード（1 ON・2 OFF・3 ON・4 ON）にし、シリアルログを監視しながら起動します。Wi-Fi、SSH、`mdt devices`、venv を有効にした `python` と実際のモデルでの推論を確認してください。時刻同期が完了するまでは APT の署名確認に失敗することがあります。

## 3. eMMC を PC にバックアップ

試験用 SD から起動中に PC で実行します。保存先は存在しないディレクトリを指定します。sudo パスワードを入力すると、eMMC 本体とブート領域 0・1 をそれぞれ圧縮し、展開後のバイト数とチェックサムを検証します。バックアップには個人情報が含まれます。

```bash
kernel/debian13/backup-emmc.sh backups/emmc-before-debian13
```

今回のバックアップは `backups/emmc-before-debian13/` にあり、`SHA256SUMS` で再検査できます。これは eMMC のバックアップです。別の `/home` 用 SD カードのデータは含みません。復元には試験用 SD などで起動し、対象デバイスとブート領域の書き込み保護を確認する必要があります。

## 4. eMMC に移行

バックアップの成功と試験起動を確認したうえで、PC からスクリプトを転送します。

```bash
CORAL_DEPLOY_DIR=/home/mendel/debian13-build scripts/deploy.sh \
  kernel/debian13/install-emmc.sh:install-emmc.sh
```

試験用 SD で起動中のボードにログインし、実行します。この操作は eMMC の rootfs を初期化します。既存の eMMC `/boot` を読み取り専用で確認し、カーネル・DTB が試験用 SD と一致する場合のみ進みます。パーティションテーブルと eMMC の U-Boot は書き換えません。

```bash
sudo bash /home/mendel/debian13-build/install-emmc.sh --write-emmc
sudo poweroff
```

電源を外し、eMMC モード（1 ON・2 OFF・3 OFF・4 OFF）に戻して起動します。`findmnt /`、`findmnt /boot`、`mdt devices` と PyCoral 推論を確認します。試験用 SD は切り戻し用に保管できます。

## 5. 元の `/home` 用 SD を戻す

安全に電源を切って元の SD カードに交換し、eMMC モードで起動します。`lsblk -f` で UUID を確認し、PC から転送します。

```bash
CORAL_DEPLOY_DIR=/home/mendel/debian13-build scripts/deploy.sh \
  kernel/debian13/restore-home.sh:restore-home.sh
```

ボードにログインして実行します。既存のファイルは上書きせず、eMMC `/home` の新規ファイルだけを SD に追加します。SD に PyCoral venv が既にある場合は統合せず、そのまま残します。SSH 鍵が異なる場合は停止するので、内容を確認してから手動で統合してください。

```bash
sudo bash /home/mendel/debian13-build/restore-home.sh --mount-home
sudo reboot
```

再起動後に `findmnt /home` と元のデータ、SSH、推論を確認します。元の `fstab` は `/etc/fstab.before-home-sd` に保存されます。

今回の実機作業では同等の手順を検証しましたが、ここに残した再実行用スクリプトは整理後に最初からの移行を再実行していません。
