# /home を SD カードに移行する

## 概要

Coral Dev Board の eMMC（7.3GB）は、デフォルトで / (5.1GB) と /home (2.0GB) に分割されています。
AI モデルなどの大容量ファイルを扱うには /home の容量が不足するため、
eMMC を / 一本に再構成し、SD カードを /home としてマウントします。

### 最終構成

| デバイス | マウント | サイズ | 用途 |
|---|---|---|---|
| mmcblk0p1 (eMMC) | /boot | 128MB | ブートパーティション |
| mmcblk0p2 (eMMC) | / | 約 7.1GB | ルートファイルシステム |
| mmcblk1p1 (SD) | /home | SD カード容量 | ホームディレクトリ |

## 前提条件

- SD カード（16GB 以上推奨）
- USB シリアルアダプタ（U-Boot コンソール用）
- USB-C ケーブル（OTG ポート接続、fastboot 用）
- ホスト PC に `fastboot` がインストール済み

## 1. フラッシュパッケージの入手

Mendel Linux のフラッシュパッケージをダウンロードして展開します。

```bash
curl -O https://dl.google.com/coral/mendel/enterprise/enterprise-eagle-20211117215217.zip
unzip enterprise-eagle-20211117215217.zip
```

パッケージには以下のファイルが含まれています:

| ファイル | 説明 |
|---|---|
| `recovery.img` | U-Boot イメージ（SD カード起動用） |
| `u-boot.imx` | ブートローダー |
| `boot_arm64.img` | カーネル + initramfs |
| `rootfs_arm64.img` | ルートファイルシステム（Android sparse image） |
| `partition-table-8gb.img` | デフォルトの GPT パーティションテーブル |
| `flash.sh` | フラッシュスクリプト |

## 2. カスタムパーティションテーブルの作成

デフォルトの eMMC パーティション構成（boot + misc + home + rootfs）を
boot + rootfs の 2 パーティション構成に変更するカスタム GPT を作成します。

```bash
# eMMC サイズに合わせた仮想ディスクを作成（8GB eMMC = 15269888 セクタ）
truncate -s $((15269888 * 512)) disk-custom.img

# パーティションテーブルを作成
sgdisk -Z disk-custom.img
sgdisk \
  -n 1:16384:278527 -t 1:8300 -c 1:boot \
  -n 2:278528:0 -t 2:8300 -c 2:rootfs \
  disk-custom.img
```

!!! warning "PARTUUID の一致"
    カーネルは PARTUUID でルートパーティションを探します。
    オリジナルの rootfs パーティションの PARTUUID を確認し、カスタム GPT に同じ値を設定する必要があります。

    ```bash
    # オリジナルの PARTUUID を確認（Python で GPT を解析）
    python3 -c "
    import struct
    with open('enterprise-eagle-20211117215217/partition-table-8gb.img', 'rb') as f:
        data = f.read()
    entry = data[1024 + 3 * 128 : 1024 + 4 * 128]  # 4番目のパーティション (rootfs)
    guid = entry[16:32]
    u = struct.unpack_from('<IHH', guid, 0)
    rest = guid[8:16]
    print(f'{u[0]:08x}-{u[1]:04x}-{u[2]:04x}-{rest[0]:02x}{rest[1]:02x}-'
          f'{rest[2]:02x}{rest[3]:02x}{rest[4]:02x}{rest[5]:02x}{rest[6]:02x}{rest[7]:02x}')
    "
    ```

    確認した PARTUUID を `-u 2:<PARTUUID>` オプションで指定してください:

    ```bash
    sgdisk -Z disk-custom.img
    sgdisk \
      -n 1:16384:278527 -t 1:8300 -c 1:boot \
      -u 1:<boot の PARTUUID> \
      -n 2:278528:0 -t 2:8300 -c 2:rootfs \
      -u 2:<rootfs の PARTUUID> \
      disk-custom.img
    ```

GPT イメージを切り出します:

```bash
dd if=disk-custom.img of=partition-table-custom.img bs=512 count=34
dd if=disk-custom.img of=partition-table-custom.img bs=512 \
  skip=$((15269888 - 33)) count=33 seek=34
```

## 3. fstab の修正

rootfs イメージ内の fstab を新しいパーティション構成に合わせて修正します。

`simg2img` / `img2simg`（`android-sdk-libsparse-utils` パッケージ）が必要です:

```bash
sudo apt install android-sdk-libsparse-utils
```

```bash
# sparse image を raw image に変換
simg2img enterprise-eagle-20211117215217/rootfs_arm64.img rootfs_raw.img

# マウントして fstab を修正
sudo mkdir -p /mnt/rootfs
sudo mount -o loop rootfs_raw.img /mnt/rootfs
```

fstab を以下の内容に書き換えます:

```bash
sudo tee /mnt/rootfs/etc/fstab << 'EOF'
/dev/mmcblk0p2 / ext4 noatime,defaults 0 1
/dev/mmcblk0p1 /boot ext2 noatime,defaults 0 2
tmpfs /var/log tmpfs defaults 0 0
EOF
```

```bash
sudo umount /mnt/rootfs

# raw image を sparse image に変換
img2simg rootfs_raw.img rootfs_custom.img
```

## 4. SD カードから起動

recovery.img を SD カードに書き込みます:

```bash
# <device> は SD カードのデバイスパス（例: /dev/sda）
sudo dd if=enterprise-eagle-20211117215217/recovery.img of=<device> bs=4M status=progress
sync
```

ボードの設定:

1. 電源を切る
2. ブートスイッチを SD モードに変更

    | スイッチ | 1 | 2 | 3 | 4 |
    |---|---|---|---|---|
    | SD モード | ON | OFF | ON | ON |

3. SD カードを挿入
4. USB シリアルアダプタを接続
5. USB-C を OTG ポートに接続
6. 電源投入

シリアルコンソール（115200bps）で U-Boot プロンプト (`=>`) が表示されたら:

```
fastboot 0
```

## 5. eMMC のフラッシュ

ホスト PC から fastboot でフラッシュします。各ステップの間でシリアルコンソールでの操作が必要です。

```bash
# ステップ 1: ブートローダー書き込み
sudo fastboot flash bootloader0 enterprise-eagle-20211117215217/u-boot.imx
sudo fastboot reboot-bootloader
# → シリアルコンソールで fastboot 0

# ステップ 2: カスタムパーティションテーブル書き込み
sudo fastboot flash gpt partition-table-custom.img
sudo fastboot reboot-bootloader
# → シリアルコンソールで fastboot 0

# ステップ 3: カーネルと rootfs 書き込み
sudo fastboot flash boot enterprise-eagle-20211117215217/boot_arm64.img
sudo fastboot flash rootfs rootfs_custom.img
sudo fastboot reboot
```

## 6. eMMC から起動

1. 電源を切る
2. SD カードを抜く
3. ブートスイッチを eMMC モードに戻す

    | スイッチ | 1 | 2 | 3 | 4 |
    |---|---|---|---|---|
    | eMMC モード | ON | OFF | OFF | OFF |

4. 電源投入

起動後に確認:

```bash
df -h
```

期待される出力:

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       7.1G  1.5G  5.3G  22% /
...
/dev/mmcblk0p1  124M   30M   88M  26% /boot
```

## 7. SD カードを /home にマウント

SD カードをボードに挿入し、/home 用にセットアップします:

```bash
# パーティション作成
sudo fdisk /dev/mmcblk1 << 'EOF'
n
p
1


w
EOF

# ext4 でフォーマット
sudo mkfs.ext4 -L home /dev/mmcblk1p1

# 現在の /home をコピー
sudo mkdir -p /mnt/sd
sudo mount /dev/mmcblk1p1 /mnt/sd
sudo rsync -aAX /home/ /mnt/sd/

# fstab に追加
echo '/dev/mmcblk1p1 /home ext4 noatime,nosuid,nodev,defaults 0 3' | sudo tee -a /etc/fstab

# マウント
sudo umount /mnt/sd
sudo mount /home
```

確認:

```bash
df -h
```

期待される出力:

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       7.1G  1.5G  5.3G  22% /
...
/dev/mmcblk0p1  124M   30M   88M  26% /boot
/dev/mmcblk1p1  234G   61M  222G   1% /home
```

## 確認

mdt 接続とアプリのデプロイ・実行を確認します:

```bash
# ホスト PC から
mdt devices
cmake --build build/<app> --target deploy
cmake --build build/<app> --target run
```

!!! note "ホスト名の変更"
    eMMC を再フラッシュするとボードのホスト名が変わります。
    `mdt devices` で新しいホスト名を確認してください。

## トラブルシューティング

### 起動時に "Waiting for root device PARTUUID=..." で停止する

カスタム GPT の rootfs パーティション PARTUUID がオリジナルと一致していません。
「2. カスタムパーティションテーブルの作成」を確認し、正しい PARTUUID を設定してください。

### 起動時に "A start job is running for /dev/mmcblk0p3" でタイムアウトする

fstab に古いパーティション（/dev/mmcblk0p3）への参照が残っています。
「3. fstab の修正」の手順で rootfs イメージ内の fstab を修正してください。

### デバイス名が mmcblk0 / mmcblk1 で逆になる

SD カードから起動した場合、デバイス番号が入れ替わることがあります。
`lsblk` でサイズを確認し、正しいデバイスを特定してください:

- eMMC: 約 7.3GB
- SD カード: カードの容量に依存

### /home の権限がおかしい

rsync でコピーする際は `-aAX` オプションを使用してください。
権限が崩れた場合:

```bash
sudo chown -R mendel:mendel /home/mendel
sudo chmod 755 /home/mendel
```
