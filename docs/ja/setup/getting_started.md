# セットアップガイド

Coral Dev Board の初期セットアップ手順です。

## 必要なもの

- Coral Dev Board
- USB-C ケーブル（データ通信対応）
- USB シリアルアダプタ（初回セットアップ時）
- microSD カード（OS 書き込み済み、または書き込み用）
- ホスト PC（Linux / macOS）

## 1. Mendel Linux のフラッシュ

!!! note "出荷時の状態"
    新品の Coral Dev Board には Mendel Linux がプリインストールされています。
    OS の再インストールが必要な場合のみこのステップを実行してください。

公式ドキュメントに従って Mendel Linux をフラッシュします:

[Get started with the Dev Board | Coral](https://coral.ai/docs/dev-board/get-started/)

## 2. MDT のインストール

ホスト PC に Mendel Development Tool (mdt) をインストールします。

```bash
pip install mendel-development-tool
```

## 3. ボードへの接続

USB-C ケーブルでホスト PC と Coral Dev Board を接続します。

```bash
# ボードの検出
mdt devices

# シェルアクセス
mdt shell
```

## 4. ネットワーク設定

Wi-Fi を設定します:

```bash
# mdt shell 内で実行
nmcli dev wifi connect <SSID> password <PASSWORD>

# IP アドレスの確認
ip addr show wlan0
```

## 5. クロスコンパイラのインストール

ホスト PC に aarch64 クロスコンパイラをインストールします。

=== "Ubuntu / Debian"

    ```bash
    sudo apt install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
    ```

=== "Arch Linux"

    ```bash
    sudo pacman -S aarch64-linux-gnu-gcc
    ```

## 6. SSH 鍵の設定

パスワードなしでデプロイできるよう SSH 鍵を設定します。

```bash
# Coral の IP を確認
mdt devices

# SSH 鍵をコピー
ssh-copy-id mendel@<CORAL_IP>
```

## 次のステップ

環境が整ったら、アプリケーションのビルド・デプロイに進みます。

```bash
cmake -B build/<app> -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>
cmake --build build/<app> --target deploy
```
