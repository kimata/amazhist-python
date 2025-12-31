# CLAUDE.md - プロジェクトガイドライン

このファイルは Claude Code がこのリポジトリで作業する際のガイドラインです。

## プロジェクト概要

**amazhist-python** は、Amazon.co.jp の購入履歴を自動収集し、サムネイル付き Excel ファイルとして出力する Python ツールです。

### 主な機能

- 購入履歴の自動収集（Selenium によるブラウザ自動化）
- Amazon 認証（メール/パスワード、画像認証対応）
- 商品画像のサムネイル付き Excel 出力（openpyxl）
- SQLite によるキャッシュ管理（中断しても途中から再開可能）
- エラー管理と自動リトライ機能
- Rich によるリアルタイムプログレス表示
- クロスプラットフォーム対応（Linux / Windows）

## ディレクトリ構成

```
src/
├── app.py                  # エントリーポイント（CLI）
└── amazhist/
    ├── config.py           # 設定管理（dataclass ベース）
    ├── const.py            # 定数定義（URL、リトライ設定等）
    ├── crawler.py          # Web スクレイピング（Selenium）
    ├── database.py         # SQLite データベース層
    ├── handle.py           # 状態管理（Handle クラス）
    ├── history.py          # Excel 生成ロジック
    ├── item.py             # 商品情報パース
    ├── order.py            # 注文情報パース
    └── parser.py           # テキスト解析（日付、価格）

tests/
├── conftest.py             # pytest 設定
└── unit/
    ├── test_app.py
    ├── test_crawler.py
    ├── test_database.py
    ├── test_handle.py
    ├── test_history.py
    └── test_parser.py

schema/
├── sqlite.schema           # SQLite スキーマ定義
└── config.schema           # 設定ファイルスキーマ

config.yaml                 # 設定ファイル（要作成）
config.example.yaml         # 設定ファイルのサンプル
```

## 開発コマンド

### 依存関係のインストール

```bash
uv sync
```

### アプリケーション実行

```bash
uv run python src/app.py              # 通常実行
uv run python src/app.py -e           # Excel 出力のみ
uv run python src/app.py -f           # 全データ強制再収集
uv run python src/app.py -r           # エラー項目のみ再取得
uv run python src/app.py -N           # サムネイルなし
uv run python src/app.py -D           # デバッグモード
uv run python src/app.py -E           # 未解決エラーログ表示
uv run python src/app.py -E -a        # 全エラーログ表示
```

### テスト実行

```bash
uv run pytest                         # テスト実行（並列、E2E除外）
uv run pytest tests/e2e/              # E2E テスト
```

### 型チェック

```bash
uv run mypy src/amazhist/             # mypy による型チェック
uv run pyright                        # pyright による型チェック
```

### リント・フォーマット

```bash
uv run ruff check src/                # リントチェック
uv run ruff format src/               # フォーマット
```

## コーディング規約

### Python バージョン

- Python 3.11 以上（推奨: 3.12）

### スタイル

- 最大行長: 110 文字（ruff 設定）
- ruff lint ルール: E, F, W, I, B, UP
- dataclass を積極的に使用（frozen dataclass 推奨）
- 型ヒントを必ず記述

### 型チェック

- mypy と pyright の両方でチェック

## アーキテクチャ

### 実行フロー

```
app.py (エントリー)
    ↓
Config.load() で設定読み込み
    ↓
Handle インスタンス生成（DB 初期化、プログレス UI 初期化）
    ↓
[非 export モード時]
    crawler._keep_logged_on() → Amazon ログイン
    crawler.fetch_order_item_list() → 履歴収集
        ├── fetch_year_list() → 年リスト取得
        ├── _fetch_order_count() → 各年の注文数取得
        └── _fetch_order_item_list_all_year() → 全年巡回
            └── order.parse_order() → 注文パース
                └── item.parse_item() → 商品パース
    ↓
[retry モード時]
    crawler.retry_failed_items() → エラー項目再取得
    ↓
history.generate_table_excel() → Excel 生成
    ↓
handle.finish() → リソース解放
```

### 主要クラス

- **Config** (`config.py`): 設定を保持する frozen dataclass（階層構造）
- **Handle** (`handle.py`): アプリケーション状態を管理（Selenium、DB、プログレス UI）
- **Database** (`database.py`): SQLite データベース操作（商品、年ステータス、エラーログ）
- **ProgressTask** (`handle.py`): Rich Progress のタスク管理

### データベーステーブル

| テーブル | 用途 |
|----------|------|
| `items` | 商品情報（order_no + asin でユニーク） |
| `metadata` | キー値ペア（年リスト、最終更新日時） |
| `year_status` | 年ごとの注文数と処理完了フラグ |
| `page_status` | ページごとの処理完了フラグ |
| `error_log` | エラーログ（リトライカウント付き） |

### 外部依存

- **selenium / undetected-chromedriver**: ブラウザ自動化
- **openpyxl**: Excel 生成
- **pillow / imageio**: 画像処理
- **rich**: プログレスバー・ステータス表示
- **my-lib**: 作者の共通ライブラリ（git 経由でインストール）

## 重要な注意事項

### プロジェクト設定ファイルの編集禁止

`pyproject.toml` をはじめとする一般的なプロジェクト管理ファイルは、`../py-project` で一元管理しています。

- **直接編集しないでください**
- 修正が必要な場合は `../py-project` を使って更新してください
- 変更を行う前に、何を変更したいのかを説明し、確認を取ってください

対象ファイル例:
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.gitlab-ci.yml`
- その他の共通設定ファイル

### ドキュメント更新の検討

コードを更新した際は、以下のドキュメントを更新する必要がないか検討してください：

- `README.md`: ユーザー向けの使用方法、機能説明
- `CLAUDE.md`: 開発ガイドライン、アーキテクチャ説明

特に以下の変更時は更新を検討：
- 新しいコマンドラインオプションの追加
- 新機能の追加
- アーキテクチャの変更
- 依存関係の大きな変更

### セキュリティ考慮事項

- `config.yaml` には Amazon のログイン情報が含まれるため、リポジトリにコミットしないこと
- `.gitignore` で `config.yaml` が除外されていることを確認
- 認証情報やトークンをコードにハードコードしない

## テスト

### テスト構成

- `tests/unit/`: ユニットテスト（Selenium 非依存部分）
- E2E テストは `tests/e2e/` に配置（デフォルトで除外）

### テスト設定

- タイムアウト: 300 秒
- 並列実行: auto
- カバレッジレポート: `reports/coverage/`
- HTML レポート: `reports/pytest.html`

## コードパターン

### インポートスタイル

`from xxx import yyy` は基本的に使用せず、`import xxx` としてモジュールをインポートし、参照時は `xxx.yyy` と完全修飾名で記述する：

```python
# 推奨
import my_lib.selenium_util

driver = my_lib.selenium_util.create_driver(...)

# 非推奨
from my_lib.selenium_util import create_driver

driver = create_driver(...)
```

これにより、関数やクラスがどのモジュールに属しているかが明確になり、コードの可読性と保守性が向上する。

### 型アノテーションと型情報のないライブラリ

型情報を持たないライブラリを使用する場合、大量の `# type: ignore[union-attr]` を記載する代わりに、変数に `Any` 型を明示的に指定する：

```python
from typing import Any

# 推奨: Any 型を明示して type: ignore を不要にする
result: Any = some_untyped_lib.call()
result.method1()
result.method2()

# 非推奨: 大量の type: ignore コメント
result = some_untyped_lib.call()  # type: ignore[union-attr]
result.method1()  # type: ignore[union-attr]
result.method2()  # type: ignore[union-attr]
```

これにより、コードの可読性を維持しつつ型チェッカーのエラーを抑制できる。

### pyright エラーへの対処方針

pyright のエラー対策として、各行に `# type: ignore` コメントを記載して回避するのは**最後の手段**とする。

**優先順位：**
1. **型推論できるようにコードを修正する** - 変数の初期化時に型が明確になるようにする
2. **型アノテーションを追加する** - 関数の引数や戻り値、変数に適切な型を指定する
3. **Any 型を使用する** - 型情報のないライブラリの場合（上記セクション参照）
4. **`# type: ignore` コメント** - 上記で解決できない場合の最終手段

```python
# 推奨: 型推論可能なコード
items: list[str] = []
items.append("value")

# 非推奨: type: ignore の多用
items = []  # type: ignore[var-annotated]
items.append("value")  # type: ignore[union-attr]
```

**例外：** テストコードでは、モックやフィクスチャの都合上 `# type: ignore` の使用を許容する。

### グレースフルシャットダウン

`crawler.py` では Ctrl+C によるグレースフルシャットダウンを実装：

```python
# グローバルフラグで状態管理
_shutdown_requested = False

def is_shutdown_requested() -> bool:
    """シャットダウン要求があるか確認"""
    return _shutdown_requested

# 各処理ループでチェック
if is_shutdown_requested():
    break
```

### エラー管理パターン

```python
# エラー記録
handle.record_or_update_error(
    url=url,
    error_type=amazhist.const.ERROR_TYPE_TIMEOUT,
    context="order",  # "order", "category", "thumbnail"
    message=str(e),
    order_no=order_no,
)

# エラー解決
handle.mark_error_resolved(error_id)
handle.mark_errors_resolved_by_order_no(order_no)

# 再取得
crawler.retry_failed_items(handle)
```

### リトライ設定

`const.py` で定義：

```python
RETRY_URL_ACCESS = 3        # URL アクセス
RETRY_LOGIN = 2             # ログイン
RETRY_CAPTCHA = 2           # 画像認証
RETRY_FETCH = 2             # データ取得
RETRY_THUMBNAIL = 3         # サムネイル
RETRY_CATEGORY = 2          # カテゴリ
```

### Rich UI パターン

```python
# ステータスバー更新
handle.set_status("ログイン中...")
handle.set_status("エラー発生", is_error=True)

# プログレスバー作成・更新
handle.set_progress_bar("[収集] 2024年", total=10)
progress = handle.get_progress_bar("[収集] 2024年")
progress.update(advance=1)
```

## ライセンス

Apache License Version 2.0
