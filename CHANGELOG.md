# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-01-24

### Added

- 年を指定して再取得する `-y` オプションを追加
- 今年の巡回で5件連続キャッシュヒット時に早期終了する機能を追加
- エラー詳細表示と特定 ID リトライ機能を追加
- InvalidSessionIdException 発生時のリトライ機能を追加
- URL 取得失敗と価格パース失敗のエラー記録を追加
- 詳細リンクがない注文をエラーログに記録
- CHANGELOG.md を追加

### Changed

- 例外クラスを exceptions.py に分離
- my_lib.browser_manager を使用するよう Handle を変更
- 進捗表示を my_lib.cui_progress に移行
- Order と Item に dataclass を導入
- Null Object パターンで Rich 関連の None チェックを削除
- 注文リスト処理を order_list.py に分離
- グレースフルシャットダウン処理を my_lib に移行
- エントリポイントを `[project.scripts]` パターンに統一

### Fixed

- 注文件数が表示されない年の件数取得を修正
- 詳細リンクがない注文でエラーが発生する問題を修正
- エラーログ表示にエラーメッセージを追加
- 注文処理でエラーが発生してもプログレスバーを更新するように修正
- Selenium 起動エラー時に不要なドライバー作成とダンプを行わないよう修正

### Documentation

- README.md にトラブルシューティングセクションを追加
- README.md に `-y` オプションの説明を追加
- README.md にエラー管理と再取得オプションの詳細説明を追加

### Tests

- ユニットテストを大幅に拡充（カバレッジ 99% 達成）

### CI

- 型チェッカー ty を CI に追加
- GitHub Actions のアクションバージョンを更新

## [0.2.0] - 2025-12-31

### Added

- デバッグモード (`-D`) とプロファイル削除 (`-R`) オプションを追加
- プログレスバーに推定残り時間を表示
- エラーが発生した注文・カテゴリ・サムネイルの再取得機能を追加
- エラーログ機能を追加
- 強制収集モードを追加
- Ctrl+C による graceful shutdown を実装
- Selenium をモックした統合テストを追加

### Changed

- pickle から SQLite へのデータベース移行を実装
- enlighten から Rich に移行
- poetry から uv に移行
- src レイアウトに移行
- Handle を dataclass に変更し、タイムアウト処理を改善
- crawler.py を分割してモジュール構成を整理
- GitHub Actions ワークフローを uv ベースに更新
- Docker Compose 設定をモダン化
- README.md を全面改善

### Fixed

- Amazon の注文詳細ページ構造変更に対応
- サムネイル画像取得時のタイムアウトエラーをハンドリング
- サムネイル取得失敗後にブラウザの状態を回復
- visit_url に TimeoutException のリトライ処理を追加
- pyright エラーを修正

### Removed

- archive 機能を削除
- lib/local_lib を削除

## [0.1.9] - 2024-03-29

### Fixed

- typo 修正

## [0.1.8] - 2024-03-29

### Added

- Mac OS 用の実行ファイル生成を追加

### Changed

- ビルドに必要なツールを自動的にダウンロードするように変更

## [0.1.7] - 2024-03-28

### Fixed

- ドキュメントの日本語を整理

## [0.1.6] - 2024-03-28

### Added

- データ収集の様子をドキュメントに追記
- Windows で実行する方法についてドキュメントに追記

## [0.1.5] - 2024-03-28

### Fixed

- 終了メッセージを表示するように修正

### Added

- 設定ファイルで生成する Excel ファイルのフォントを指定できるように追加

## [0.1.4] - 2024-03-28

### Fixed

- Windows で Enlighten が意図通り動くように必要なパッケージを明示的に追加
- Windows でエラーが出ないように修正
- 文字コードを明示的に指定

## [0.1.3] - 2024-03-28

### Fixed

- 圧縮時にディレクトリを含めないように修正

## [0.1.2] - 2024-03-27

### Added

- Windows 用の実行ファイルに署名するように追加

## [0.1.1] - 2024-03-27

### Added

- 実行ファイルを生成するための GitHub Action を追加

### Changed

- ディレクトリ構成を大幅見直し
- Nuitka でビルドするためのコマンドを作成

## [0.1.0] - 2024-03-26

### Added

- 初回リリース
- Amazon.co.jp の購入履歴を自動収集
- サムネイル付き Excel ファイルの出力
- SQLite によるキャッシュ管理
- Rich によるリアルタイムプログレス表示

[Unreleased]: https://github.com/kimata/amazhist-python/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/kimata/amazhist-python/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/kimata/amazhist-python/compare/v0.1.9...v0.2.0
[0.1.9]: https://github.com/kimata/amazhist-python/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/kimata/amazhist-python/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/kimata/amazhist-python/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/kimata/amazhist-python/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/kimata/amazhist-python/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/kimata/amazhist-python/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/kimata/amazhist-python/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/kimata/amazhist-python/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/kimata/amazhist-python/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kimata/amazhist-python/releases/tag/v0.1.0
