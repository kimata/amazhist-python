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
src/amazhist/
├── __init__.py             # パッケージ初期化
├── __main__.py             # エントリーポイント（python -m amazhist）
├── cli.py                  # CLI 引数解析・メイン処理
├── config.py               # 設定管理（dataclass ベース）
├── const.py                # 定数定義（URL、リトライ設定等）
├── crawler.py              # Web スクレイピング（Selenium）
├── database.py             # SQLite データベース層
├── exceptions.py           # カスタム例外クラス
├── handle.py               # 状態管理（Handle クラス）
├── history.py              # Excel 生成ロジック
├── item.py                 # 商品情報パース
├── order.py                # 注文情報パース
├── order_list.py           # 注文リスト管理
└── parser.py               # テキスト解析（日付、価格）

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
uv run amazhist                       # 通常実行
uv run amazhist -e                    # Excel 出力のみ
uv run amazhist -f                    # 全データ強制再収集
uv run amazhist -r                    # エラー項目のみ再取得
uv run amazhist -N                    # サムネイルなし
uv run amazhist -D                    # デバッグモード
uv run amazhist -E                    # 未解決エラーログ表示
uv run amazhist -E -a                 # 全エラーログ表示
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
cli.py (エントリー: uv run amazhist)
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

| テーブル      | 用途                                   |
| ------------- | -------------------------------------- |
| `items`       | 商品情報（order_no + asin でユニーク） |
| `metadata`    | キー値ペア（年リスト、最終更新日時）   |
| `year_status` | 年ごとの注文数と処理完了フラグ         |
| `page_status` | ページごとの処理完了フラグ             |
| `error_log`   | エラーログ（リトライカウント付き）     |

### 外部依存

- **selenium / undetected-chromedriver**: ブラウザ自動化
- **openpyxl**: Excel 生成
- **pillow / imageio**: 画像処理
- **rich**: プログレスバー・ステータス表示
- **my-lib**: 作者の共通ライブラリ（git 経由でインストール）

## 重要な注意事項
### 共通運用ルール

- 変更前に意図と影響範囲を説明し、ユーザー確認を取る
- `pyproject.toml` 等の共通設定は `../py-project` で管理し、各リポジトリで直接編集しない
- `my_lib` の変更は `../my-py-lib` で実施し、各リポジトリのハッシュ更新後に `uv lock && uv sync` を実行
- 依存関係管理は `uv` を標準とし、他の手段はフォールバック扱い
- 構造化データは `@dataclass` を優先し、辞書からの生成は `parse()` 命名で統一
- Union 型が 3 箇所以上で出現する場合は `TypeAlias` を定義
- `except Exception` は避け、具体的な例外型を指定する
- ミラー運用がある場合は primary リポジトリにのみ push する


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

### Protocol の活用

コールバック関数を引数として受け取る場合は、`typing.Protocol` を使用して型を定義する：

```python
from typing import Protocol

class VisitUrlFunc(Protocol):
    def __call__(self, handle: Handle, url: str, caller_name: str) -> None: ...

def fetch_data(visit_url: VisitUrlFunc) -> None:
    ...
```

Protocol は `types.py` に定義されている。新しいコールバック型が必要な場合は同ファイルに追加する。

### dict の返却を避ける

関数から構造化されたデータを返す場合、`dict[str, Any]` ではなく dataclass を使用する：

```python
# 推奨
@dataclass(frozen=True)
class FetchResult:
    success: bool
    data: str | None
    error_message: str | None

def fetch() -> FetchResult:
    ...

# 非推奨
def fetch() -> dict[str, Any]:
    return {"success": True, "data": "...", "error_message": None}
```

frozen dataclass を使用することで、イミュータブルなデータ構造を保証し、属性アクセスによる型安全性を確保できる。

### マジックナンバーの定数化

コード中の数値リテラルは、意図を明確にするために `const.py` で定数として定義する：

```python
# 推奨
handle.set_progress_bar(label, amazhist.const.PROGRESS_STEPS_EXCEL)

# 非推奨
handle.set_progress_bar(label, 6)
```

### 型ヒントの網羅

すべての関数引数に型ヒントを記述する。外部から受け取る設定辞書は `dict[str, Any]` を使用：

```python
# 推奨
def execute(config: dict[str, Any], ...) -> int:
    ...

# 非推奨
def execute(config, ...) -> int:
    ...
```

### 戻り値型の明示

すべての関数に戻り値型アノテーションを記述する（`None` を返す場合も `-> None` を明記）：

```python
# 推奨
def process_data(data: str) -> None:
    ...

# 非推奨
def process_data(data: str):
    ...
```

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

### 共通処理の関数化

3箇所以上で重複するコードパターンは、ヘルパー関数として抽出する：

```python
# 推奨: 共通処理を関数化
def _setup_graceful_shutdown(handle: Handle) -> None:
    my_lib.graceful_shutdown.set_live_display(handle)
    my_lib.graceful_shutdown.setup_signal_handler()
    my_lib.graceful_shutdown.reset_shutdown_flag()

# 非推奨: 同じコードを複数箇所にコピー
```

### デバッグダンプID

ページダンプ時のランダムIDは `amazhist.const.generate_debug_dump_id()` を使用する：

```python
# 推奨
dump_id = amazhist.const.generate_debug_dump_id()
my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)

# 非推奨（直接記述）
dump_id = int(random.random() * amazhist.const.DEBUG_DUMP_ID_MAX)  # noqa: S311
```

### 型チェック

型チェックには `isinstance()` を使用する（PEP 8 推奨）：

```python
# 推奨
if isinstance(year, str):
    ...

# 非推奨
if type(year) is str:
    ...
```

### 型の統一

Union 型（`str | int` など）は、実際に複数の型が必要な場合にのみ使用する。呼び出し元が常に同じ型を渡す場合は、その型に統一する：

```python
# 推奨: 呼び出し元が常に int を渡す場合
def set_year_status(self, year: int, ...) -> None:
    year_str = str(year)  # 内部で変換

# 非推奨: 不要な Union 型
def set_year_status(self, year: str | int, ...) -> None:
    year_str = str(year)
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

### リファクタリング時の判断基準

以下の場合はリファクタリングを見送る：

- 影響範囲が複数ファイル・テストコードに跨る場合
- 外部ライブラリとのインターフェース変更が必要な場合
- 安全弁として機能している後方互換性コードの場合
- コード量削減が5行未満の場合

### スキーマファイルのパス指定

スキーマファイルのパスは各モジュールで `pathlib.Path(__file__)` ベースで解決する。
ファイル数が増えてきた場合は `const.py` への集約を検討するが、現状では分散管理を許容する：

```python
# 許容: 各モジュールで個別に定義
_SQLITE_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"
```

### ディレクトリ作成パターン

複数ディレクトリを作成する場合、現在の明示的な記述を維持する（ループ化は可読性向上に寄与しない）：

```python
# 許容: 明示的な記述
self.config.dir_a.mkdir(parents=True, exist_ok=True)
self.config.dir_b.mkdir(parents=True, exist_ok=True)
self.config.dir_c.mkdir(parents=True, exist_ok=True)
```

### DB 互換性コード

古いスキーマとの互換性を維持するコードは、ユーザー影響がなくなるまで保持する。
削除は major バージョンアップ時に検討する：

```python
# 許容: 古いカラムがない場合のフォールバック
row_keys = row.keys()
order_year = row["order_year"] if "order_year" in row_keys else None
```

### 例外の使い分け

汎用 `Exception` ではなく、`exceptions.py` で定義されたカスタム例外を使用する：

- `CaptchaError`: 画像認証失敗
- `LoginError`: ログイン失敗
- `ThumbnailError`: サムネイル画像エラー（基底クラス）
- `ThumbnailEmptyError`: サムネイル画像データが空
- `ThumbnailSizeError`: サムネイル画像のサイズが0
- `ThumbnailCorruptError`: サムネイル画像が破損

```python
# 推奨
raise amazhist.exceptions.LoginError("ログインに失敗しました．")

# 非推奨
raise Exception("ログインに失敗しました．")
```

### 文字列フォーマット

f-string に統一する（`.format()` や `%` フォーマットは使用しない）：

```python
# 推奨
logging.info(f"{year}年: {count:4,} 件")

# 非推奨
logging.info("{}年: {:4,} 件".format(year, count))
logging.info("%s年: %4d 件" % (year, count))
```

### メッセージ言語

ログメッセージ、エラーメッセージは日本語に統一する。

```python
# 推奨
logging.exception(f"データの収集中にエラーが発生しました: {url}")

# 非推奨
logging.exception("Failed to fetch data: %s", url)
```

### 関数の引数が多い場合の検討

関数の引数が5個以上になる場合は、関連する引数を dataclass にまとめることを検討する。
ただし、影響範囲が複数ファイル・テストコードに跨る場合は見送る。

### 3要素以上のタプル戻り値の検討

関数の戻り値が3要素以上のタプルになる場合は、dataclass を使用して意味を明確にすることを検討する。
ただし、影響範囲が複数ファイル・テストコードに跨る場合は見送る。

### URL テンプレート定数

URL テンプレート定数は `.format()` を使用する（f-string ではなく）：

```python
# 推奨: 定数として定義し .format() で展開
HIST_URL_BY_YEAR = "https://example.com/orders?year={year}&start={start}"
url = HIST_URL_BY_YEAR.format(year=2024, start=0)

# 非推奨: f-string は定数として定義できない
def gen_hist_url(year: int, start: int) -> str:
    return f"https://example.com/orders?year={year}&start={start}"
```

## ライセンス

Apache License Version 2.0

## 開発ワークフロー規約

### リポジトリ構成

- **プライマリリポジトリ**: GitLab (`gitlab.green-rabbit.net`)
- **ミラーリポジトリ**: GitHub (`github.com/kimata/amazhist-python`)

GitLab にプッシュすると、自動的に GitHub にミラーリングされます。GitHub への直接プッシュは不要です。

### コミット時の注意

- 今回のセッションで作成し、プロジェクトが機能するのに必要なファイル以外は git add しないこと
- 気になる点がある場合は追加して良いか質問すること

### バグ修正の原則

- 憶測に基づいて修正しないこと
- 必ず原因を論理的に確定させた上で修正すること
- 「念のため」の修正でコードを複雑化させないこと

### コード修正時の確認事項

- 関連するテストも修正すること
- 関連するドキュメントも更新すること
- mypy, pyright, ty がパスすることを確認すること

### リリース（タグ作成）時

リリースタグを作成する際は、以下の手順に従うこと：

1. **CHANGELOG.md を更新する**
    - 新しいバージョンのセクションを追加
    - 含まれる変更を以下のカテゴリで記載：
        - `Added`: 新機能
        - `Changed`: 既存機能の変更
        - `Fixed`: バグ修正
        - `Removed`: 削除された機能
        - `Security`: セキュリティ関連の修正
    - [Keep a Changelog](https://keepachangelog.com/) 形式を参考にする

2. **タグを作成する**
    ```bash
    git tag -a v1.x.x -m "バージョン説明"
    git push origin v1.x.x
    ```
