#!/usr/bin/env python3
# ruff: noqa: S101
"""
handle.py のテスト
"""
import unittest.mock

import pytest

import amazhist.config
import amazhist.handle


class TestHandleCreation:
    """Handle 作成のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_create_handle(self, mock_config, tmp_path):
        """Handle の作成"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            assert handle is not None
            assert handle.config is not None
            assert handle.ignore_cache is False

            handle.finish()

    def test_create_handle_ignore_cache(self, mock_config, tmp_path):
        """Handle の作成（キャッシュ無視モード）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(
                config=amazhist.config.Config.load(mock_config), ignore_cache=True
            )

            assert handle.ignore_cache is True

            handle.finish()


class TestHandlePaths:
    """Handle のパス取得テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            yield h
            h.finish()

    def test_get_cache_file_path(self, handle, tmp_path):
        """キャッシュファイルパス取得"""
        path = handle.config.cache_file_path
        assert path == tmp_path / "cache" / "order.db"

    def test_get_excel_file_path(self, handle, tmp_path):
        """Excel ファイルパス取得"""
        path = handle.config.excel_file_path
        assert path == tmp_path / "output" / "amazhist.xlsx"

    def test_get_thumb_dir_path(self, handle, tmp_path):
        """サムネイルディレクトリパス取得"""
        path = handle.config.thumb_dir_path
        assert path == tmp_path / "thumb"

    def test_get_debug_dir_path(self, handle, tmp_path):
        """デバッグディレクトリパス取得"""
        path = handle.config.debug_dir_path
        assert path == tmp_path / "debug"

    def test_get_thumb_path(self, handle, tmp_path):
        """サムネイルパス取得"""
        path = handle.get_thumb_path("B0123456789")
        assert path == tmp_path / "thumb" / "B0123456789.png"

    def test_get_thumb_path_no_asin(self, handle):
        """ASIN がない場合は None"""
        path = handle.get_thumb_path(None)
        assert path is None


class TestHandleLogin:
    """Handle のログイン情報テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password123",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            yield h
            h.finish()

    def test_get_login_user(self, handle):
        """ログインユーザー取得"""
        user = handle.get_login_user()
        assert user == "test@example.com"

    def test_get_login_pass(self, handle):
        """ログインパスワード取得"""
        password = handle.get_login_pass()
        assert password == "password123"


class TestHandleProgressBar:
    """Handle のプログレスバーテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            yield h
            h.finish()

    def test_set_progress_bar(self, handle):
        """プログレスバーの設定"""
        handle.set_progress_bar("テスト", 100)

        progress_bar = handle.get_progress_bar("テスト")
        assert progress_bar is not None
        assert progress_bar.total == 100

    def test_progress_bar_update(self, handle):
        """プログレスバーの更新"""
        handle.set_progress_bar("テスト", 100)
        progress_bar = handle.get_progress_bar("テスト")

        progress_bar.update()

        assert progress_bar.count == 1

    def test_progress_bar_update_with_advance(self, handle):
        """プログレスバーを複数進める"""
        handle.set_progress_bar("テスト", 100)
        progress_bar = handle.get_progress_bar("テスト")

        progress_bar.update(advance=5)

        assert progress_bar.count == 5

    def test_get_progress_bar_nonexistent(self, handle):
        """存在しないプログレスバーを取得"""
        with pytest.raises(KeyError):
            handle.get_progress_bar("存在しないキー")


class TestHandleStatus:
    """Handle のステータステスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            yield h
            h.finish()

    def test_set_status(self, handle):
        """ステータスの設定"""
        handle.set_status("処理中...")

        assert handle._status_text == "処理中..."
        assert handle._status_is_error is False

    def test_set_status_error(self, handle):
        """エラーステータスの設定"""
        handle.set_status("エラー発生", is_error=True)

        assert handle._status_text == "エラー発生"
        assert handle._status_is_error is True


class TestHandleIgnoreCache:
    """Handle の ignore_cache テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle_ignore_cache(self, mock_config, tmp_path):
        """ignore_cache=True の Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(
                config=amazhist.config.Config.load(mock_config), ignore_cache=True
            )
            # モック DB を設定
            h._db = unittest.mock.MagicMock()
            h._db.exists_order.return_value = True
            h._db.is_page_checked.return_value = True
            h._db.is_year_checked.return_value = True
            yield h
            h.finish()

    def test_get_order_stat_ignore_cache(self, handle_ignore_cache):
        """ignore_cache 時は常に False"""
        result = handle_ignore_cache.get_order_stat("ORDER-001")
        assert result is False
        # DB が True を返しても ignore_cache では False
        handle_ignore_cache._db.exists_order.assert_not_called()

    def test_get_page_checked_ignore_cache(self, handle_ignore_cache):
        """ignore_cache 時は常に False"""
        result = handle_ignore_cache.get_page_checked(2025, 1)
        assert result is False
        handle_ignore_cache._db.is_page_checked.assert_not_called()

    def test_get_year_checked_ignore_cache(self, handle_ignore_cache):
        """ignore_cache 時は常に False"""
        result = handle_ignore_cache.get_year_checked(2025)
        assert result is False
        handle_ignore_cache._db.is_year_checked.assert_not_called()


class TestHandleDatabase:
    """Handle のデータベース操作テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_record_item(self, handle):
        """商品を記録"""
        item = {"no": "ORDER-001", "name": "テスト商品"}
        handle.record_item(item)
        handle._db.upsert_item.assert_called_once_with(item)

    def test_get_item_list(self, handle):
        """商品リストを取得"""
        handle._db.get_item_list.return_value = [{"name": "商品1"}, {"name": "商品2"}]
        result = handle.get_item_list()
        assert len(result) == 2
        handle._db.get_item_list.assert_called_once()

    def test_get_last_item(self, handle):
        """最後の商品を取得"""
        handle._db.get_last_item_by_filter.return_value = {"name": "最後の商品"}
        result = handle.get_last_item(2025)
        assert result["name"] == "最後の商品"
        handle._db.get_last_item_by_filter.assert_called_once_with(2025)

    def test_set_year_list(self, handle):
        """年リストを設定"""
        handle.set_year_list([2023, 2024, 2025])
        handle._db.set_year_list.assert_called_once_with([2023, 2024, 2025])

    def test_get_year_list(self, handle):
        """年リストを取得"""
        handle._db.get_year_list.return_value = [2023, 2024, 2025]
        result = handle.get_year_list()
        assert result == [2023, 2024, 2025]

    def test_set_order_count(self, handle):
        """年の注文数を設定"""
        handle.set_order_count(2025, 100)
        handle._db.set_year_status.assert_called_once_with(2025, order_count=100)

    def test_get_order_count(self, handle):
        """年の注文数を取得"""
        handle._db.get_year_order_count.return_value = 100
        result = handle.get_order_count(2025)
        assert result == 100

    def test_get_total_order_count(self, handle):
        """全注文数を取得"""
        handle._db.get_total_order_count.return_value = 500
        result = handle.get_total_order_count()
        assert result == 500

    def test_set_page_checked(self, handle):
        """ページの処理完了フラグを設定"""
        handle.set_page_checked(2025, 1)
        handle._db.set_page_checked.assert_called_once_with(2025, 1, True)

    def test_set_year_checked(self, handle):
        """年の処理完了フラグを設定"""
        handle.set_year_checked(2025)
        handle._db.set_year_status.assert_called_once_with(2025, checked=True)
        handle._db.set_last_modified.assert_called_once()

    def test_store_order_info(self, handle):
        """注文情報を保存"""
        handle.store_order_info()
        handle._db.set_last_modified.assert_called_once()


class TestHandleErrorLog:
    """Handle のエラーログテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_record_error(self, handle):
        """エラーを記録"""
        handle._db.record_error.return_value = 1
        result = handle.record_error(
            url="https://example.com",
            error_type="timeout",
            context="order",
            message="エラーメッセージ",
        )
        assert result == 1
        handle._db.record_error.assert_called_once()

    def test_record_or_update_error(self, handle):
        """エラーを記録または更新"""
        handle._db.record_or_update_error.return_value = 1
        result = handle.record_or_update_error(
            url="https://example.com",
            error_type="timeout",
            context="order",
        )
        assert result == 1
        handle._db.record_or_update_error.assert_called_once()

    def test_get_unresolved_errors(self, handle):
        """未解決のエラー一覧を取得"""
        handle._db.get_unresolved_errors.return_value = [{"id": 1}, {"id": 2}]
        result = handle.get_unresolved_errors()
        assert len(result) == 2

    def test_get_all_errors(self, handle):
        """全エラー一覧を取得"""
        handle._db.get_all_errors.return_value = [{"id": 1}]
        result = handle.get_all_errors(limit=50)
        handle._db.get_all_errors.assert_called_once_with(50)
        assert len(result) == 1

    def test_get_error_count(self, handle):
        """エラー件数を取得"""
        handle._db.get_error_count.return_value = 5
        result = handle.get_error_count(resolved=False)
        assert result == 5
        handle._db.get_error_count.assert_called_once_with(False)

    def test_mark_error_resolved(self, handle):
        """エラーを解決済みにする"""
        handle.mark_error_resolved(1)
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_clear_old_errors(self, handle):
        """古いエラーを削除"""
        handle._db.clear_old_errors.return_value = 10
        result = handle.clear_old_errors(days=60)
        assert result == 10
        handle._db.clear_old_errors.assert_called_once_with(60)

    def test_get_failed_order_numbers(self, handle):
        """エラーが発生した注文番号を取得"""
        handle._db.get_failed_order_numbers.return_value = ["ORDER-001", "ORDER-002"]
        result = handle.get_failed_order_numbers()
        assert len(result) == 2

    def test_get_failed_category_items(self, handle):
        """カテゴリ取得に失敗したアイテムを取得"""
        handle._db.get_failed_category_items.return_value = [{"url": "url1"}]
        result = handle.get_failed_category_items()
        assert len(result) == 1

    def test_update_item_category(self, handle):
        """アイテムのカテゴリを更新"""
        handle._db.update_item_category.return_value = 1
        result = handle.update_item_category("url1", ["カテゴリ1"])
        assert result == 1

    def test_get_failed_thumbnail_items(self, handle):
        """サムネイル取得に失敗したアイテムを取得"""
        handle._db.get_failed_thumbnail_items.return_value = [{"name": "商品1"}]
        result = handle.get_failed_thumbnail_items()
        assert len(result) == 1

    def test_mark_errors_resolved_by_order_no(self, handle):
        """注文番号でエラーを一括解決済みにする"""
        handle._db.mark_errors_resolved_by_order_no.return_value = 2
        result = handle.mark_errors_resolved_by_order_no("ORDER-001")
        assert result == 2
