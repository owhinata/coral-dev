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
プロジェクトルートで仮想環境を作成し、依存パッケージをインストールしてください。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

!!! tip "PATH の設定"
    `.venv/bin` にパスを通すか、`.venv/bin/mdt` のようにフルパスで実行してください。

## 3. ボードへの接続

USB-C ケーブルでホスト PC と Coral Dev Board を接続します。

```bash
# ボードの検出
mdt devices

# シェルアクセス
mdt shell
```

!!! note "SSH 鍵の自動管理"
    mdt は初回接続時に SSH 鍵を自動生成し、`~/.config/mdt/keys/mdt.key` に保存します。
    デプロイスクリプトもこの鍵を利用するため、手動での SSH 鍵設定は不要です。

## 4. ネットワーク設定

Wi-Fi を設定します:

```bash
# mdt shell 内で実行
nmcli dev wifi connect <SSID> password <PASSWORD>

# IP アドレスの確認
ip addr show wlan0
```

## 5. クロスコンパイラのインストール

Coral Dev Board の Mendel Linux (Debian 10 Buster, glibc 2.28) に合わせた
ARM GNU Toolchain 8.3 をセットアップスクリプトでインストールします。

```bash
./cmake/setup-toolchain.sh
```

ツールチェーンは `toolchain/` ディレクトリにダウンロード・展開されます。

## 次のステップ

環境が整ったら、[Hello World](../development/hello_world.md) でビルド・デプロイを試しましょう。
