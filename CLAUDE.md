# CLAUDE.md — coral-dev

## Git / PR ワークフロー

タスク完了時、指示があればPR作成・更新まで一気通貫で実行する。

- **ブランチ**: `feat/`, `docs/`, `style/`, `fix/`, `build/`, `refactor/`, `chore/` prefix。ベースは常に `main`
- **コミット**: conventional commits 形式 `type: short description`

### PR作成

```bash
gh pr create --title "type: short description" --body "$(cat <<'EOF'
## Summary
- 変更点を箇条書き

## Test plan
- [x] テスト項目

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### PR更新

追加コミット & push 後、**必ずPRにコメントを残す**:

```
## type: short description (commit-hash)

変更内容の説明。
```

ドキュメント (`docs/`) に変更がある場合は、PR プレビューの該当ページへのリンクをコメントに含める:

```
変更後のドキュメント:
- [ページ名](https://owhinata.github.io/coral-dev/pr-preview/pr-<PR番号>/path/to/page/)
```

### PRマージ

```bash
gh pr merge <PR番号> --merge --delete-branch
git remote prune origin
```

## ドキュメント

MkDocs + Material + mkdocs-static-i18n。設定は `mkdocs.yml` 参照。

### 作成手順

1. `docs/ja/` と `docs/en/` に同名 `.md` を作成（日英必須）
2. `mkdocs.yml` の `nav` にエントリ追加（新セクション時は `nav_translations` も）
3. `mkdocs build` で確認

### カテゴリ

- `setup/` — 初期設定、環境構築
- `development/` — サンプルアプリのビルド・実行ガイド
- `technical/` — アーキテクチャ、調査結果

### ソースコード参照

GitHub パーマリンク（コミットハッシュ + 行番号）を使用。ソース変更時はリンクを更新する。

## apps ディレクトリ

各アプリは `apps/<app_name>/` に `CMakeLists.txt` + `src/` で構成。CMake out-of-tree ビルド。

- C: `.c`/`.h`、C++: `.cc`/`.h`
- 新規作成時は既存アプリの `CMakeLists.txt` をテンプレートにする
- コーディングスタイル: Google Style (`clang-format -style=google`)
- cpplint でチェック。フィルタ:
  ```
  cpplint --filter=-legal/copyright,-build/include_subdir,-build/namespaces,-build/c++11,-runtime/references,-build/include_order <files>
  ```
  - 上記フィルタ適用後のエラーは **0 件** にすること
  - ヘッダーガードは `APPS_<APP>_SRC_<FILE>_H_` 形式
  - 単一引数コンストラクタには `explicit` を付ける
- `build/` は `.gitignore` で除外済み

### ツールチェーン (`cmake/`)

| ファイル | ターゲット |
|---------|-----------|
| `toolchain-coral-aarch64.cmake` | Coral Dev Board (Mendel Linux, aarch64) |

### ビルド

```bash
cmake -B build/<app> -S apps/<app> -DCMAKE_TOOLCHAIN_FILE=$(pwd)/cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>
```

### デプロイ・実行

mdt (Mendel Development Tool) 経由でデプロイ・実行する。SSH 鍵の設定は不要。

```bash
# デプロイ（mdt でボードへ転送）
cmake --build build/<app> --target deploy

# リモート実行
cmake --build build/<app> --target run
```

## ボードへのアクセス (`cmake/scripts/`)

ボード上でのコマンド実行やファイル転送には `cmake/scripts/` のスクリプトを使用する。
`mdt exec` や生の `ssh` / `scp` は使わない。

```bash
# ボード上でコマンド実行
cmake/scripts/run.sh '<command>'

# ファイル転送（CMake deploy ターゲット経由）
cmake --build build/<app> --target deploy
```

## Coral Dev Board 固有の注意点

### Edge TPU ランタイム

Coral Dev Board は Edge TPU を搭載。TensorFlow Lite + Edge TPU Delegate で推論を実行する。

- ランタイムは Mendel Linux に Debian パッケージとしてプリインストール
- パッケージ: `libedgetpu1-std`（標準クロック）, `libedgetpu1-max`（最大クロック）
- ヘッダー: `/usr/include/edgetpu.h`
- ライブラリ: `/usr/lib/aarch64-linux-gnu/libedgetpu.so.1`

### mdt (Mendel Development Tool)

`mdt` は Coral Dev Board の管理ツール。USB OTG 経由でボードに接続する。

```bash
# ボード検出
mdt devices

# シェルアクセス
mdt shell

# ファイル転送
mdt push <local_file> <remote_path>
```

### SSH 接続

mdt 経由または IP 直接指定で SSH 接続可能。

```bash
# IP 確認
mdt devices

# SSH 接続
ssh mendel@<ip>
```

デフォルトユーザー: `mendel`
