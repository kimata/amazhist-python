#!/usr/bin/env python3
# ruff: noqa: S101
"""
handle.py のテスト
"""

import unittest.mock

import pytest

import amazhist.config
import amazhist.database
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
        assert password == "password123"  # noqa: S105


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
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config), ignore_cache=True)
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
        mock_errors = [
            amazhist.database.ErrorLog(
                id=1, url="url1", error_type="e", context="c", retry_count=0, resolved=False
            ),
            amazhist.database.ErrorLog(
                id=2, url="url2", error_type="e", context="c", retry_count=0, resolved=False
            ),
        ]
        handle._db.get_unresolved_errors.return_value = mock_errors
        result = handle.get_unresolved_errors()
        assert len(result) == 2

    def test_get_all_errors(self, handle):
        """全エラー一覧を取得"""
        mock_errors = [
            amazhist.database.ErrorLog(
                id=1, url="url1", error_type="e", context="c", retry_count=0, resolved=False
            ),
        ]
        handle._db.get_all_errors.return_value = mock_errors
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


class TestNullProgress:
    """_NullProgress のテスト"""

    def test_null_progress_add_task(self):
        """add_task が TaskID(0) を返す"""
        null_progress = amazhist.handle._NullProgress()
        result = null_progress.add_task("テスト", total=100)
        assert result == 0

    def test_null_progress_update(self):
        """update が何もしない"""
        import rich.progress

        null_progress = amazhist.handle._NullProgress()
        # 例外なく完了
        null_progress.update(rich.progress.TaskID(0), advance=1)

    def test_null_progress_rich(self):
        """__rich__ が空のテキストを返す"""
        null_progress = amazhist.handle._NullProgress()
        result = null_progress.__rich__()
        assert str(result) == ""


class TestNullLive:
    """_NullLive のテスト"""

    def test_null_live_start(self):
        """start が何もしない"""
        null_live = amazhist.handle._NullLive()
        null_live.start()  # 例外なく完了

    def test_null_live_stop(self):
        """stop が何もしない"""
        null_live = amazhist.handle._NullLive()
        null_live.stop()  # 例外なく完了

    def test_null_live_refresh(self):
        """refresh が何もしない"""
        null_live = amazhist.handle._NullLive()
        null_live.refresh()  # 例外なく完了


class TestDisplayRenderable:
    """_DisplayRenderable のテスト"""

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

    def test_display_renderable_rich(self, mock_config, tmp_path):
        """__rich__ が _create_display を呼び出す"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            renderable = amazhist.handle._DisplayRenderable(handle)

            with unittest.mock.patch.object(handle, "_create_display", return_value="test") as mock_create:
                result = renderable.__rich__()

                mock_create.assert_called_once()
                assert result == "test"

            handle.finish()


class TestHandleSelenium:
    """Handle の Selenium テスト"""

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

    def test_get_selenium_driver_initialized(self, mock_config, tmp_path):
        """Selenium 初期化済みの場合"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            handle.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)

            driver, wait = handle.get_selenium_driver()

            assert driver is mock_driver
            assert wait is mock_wait

            handle.finish()


class TestHandleDatabaseProperty:
    """Handle の db プロパティテスト"""

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

    def test_db_property_not_initialized(self, mock_config, tmp_path):
        """db プロパティ未初期化時に例外"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._db = None

            with pytest.raises(RuntimeError, match="Database is not initialized"):
                _ = handle.db

            handle.finish()

    def test_db_property_initialized(self, mock_config, tmp_path):
        """db プロパティ初期化済みの場合"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_db = unittest.mock.MagicMock()
            handle._db = mock_db

            db = handle.db

            assert db is mock_db

            handle.finish()


class TestHandleStatusBar:
    """ステータスバー作成のテスト"""

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

    def test_create_status_bar_normal(self, mock_config, tmp_path):
        """通常時のステータスバー"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._status_text = "処理中"
            handle._status_is_error = False

            table = handle._create_status_bar()

            assert table is not None

            handle.finish()

    def test_create_status_bar_error(self, mock_config, tmp_path):
        """エラー時のステータスバー"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._status_text = "エラー"
            handle._status_is_error = True

            table = handle._create_status_bar()

            assert table is not None

            handle.finish()

    def test_create_display_without_tasks(self, mock_config, tmp_path):
        """タスクなしの表示"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._status_text = "テスト"

            display = handle._create_display()

            assert display is not None

            handle.finish()


class TestHandleHasProgressBar:
    """has_progress_bar テスト"""

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

    def test_has_progress_bar_exists(self, mock_config, tmp_path):
        """プログレスバーが存在する場合"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle.set_progress_bar("テスト", 100)

            assert handle.has_progress_bar("テスト") is True

            handle.finish()

    def test_has_progress_bar_not_exists(self, mock_config, tmp_path):
        """プログレスバーが存在しない場合"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            assert handle.has_progress_bar("存在しない") is False

            handle.finish()


class TestInitDatabase:
    """_init_database メソッドのテスト"""

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

    def test_init_database_normal(self, mock_config, tmp_path):
        """_init_database が正常に動作する（target_year なし）"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_db = unittest.mock.MagicMock()
        mock_db.get_last_modified.return_value = datetime.datetime(2024, 5, 1)

        with unittest.mock.patch("amazhist.database.open_database", return_value=mock_db) as mock_open:
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            # open_database が呼ばれたことを確認
            mock_open.assert_called_once()

            # clear_page_status が今年と最終更新年に対して呼ばれたことを確認
            current_year = datetime.datetime.now().year
            calls = mock_db.clear_page_status.call_args_list
            years_cleared = [call[0][0] for call in calls]
            assert current_year in years_cleared
            assert 2024 in years_cleared

            handle.finish()

    def test_init_database_with_target_year(self, mock_config, tmp_path):
        """_init_database が target_year 指定時に動作する"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_db = unittest.mock.MagicMock()
        mock_db.get_last_modified.return_value = datetime.datetime(2024, 5, 1)

        with unittest.mock.patch("amazhist.database.open_database", return_value=mock_db):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config), target_year=2022)

            # clear_page_status が target_year に対しても呼ばれたことを確認
            calls = mock_db.clear_page_status.call_args_list
            years_cleared = [call[0][0] for call in calls]
            assert 2022 in years_cleared

            handle.finish()


class TestInitProgressTTY:
    """_init_progress メソッドの TTY 環境テスト"""

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

    def test_init_progress_tty(self, mock_config, tmp_path):
        """TTY 環境で _init_progress が Rich Progress/Live を初期化する"""
        import rich.console
        import rich.live
        import rich.progress

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        # TTY をシミュレート
        mock_console = unittest.mock.MagicMock(spec=rich.console.Console)
        mock_console.is_terminal = True
        mock_console.width = 80

        mock_live_instance = unittest.mock.MagicMock(spec=rich.live.Live)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("rich.progress.Progress") as mock_progress_cls,
            unittest.mock.patch("rich.live.Live", return_value=mock_live_instance) as mock_live_cls,
        ):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._console = mock_console
            # _init_progress を再呼び出し（fixture で既に呼ばれているが再初期化）
            handle._init_progress()

            # Progress と Live が初期化されたことを確認
            mock_progress_cls.assert_called()
            mock_live_cls.assert_called()
            mock_live_instance.start.assert_called()

            handle.finish()


class TestStatusBarTmux:
    """TMUX 環境でのステータスバーテスト"""

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

    def test_create_status_bar_tmux(self, mock_config, tmp_path):
        """TMUX 環境ではターミナル幅から 2 を引く"""
        import os

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._console.width = 100

            # TMUX 環境をシミュレート
            with unittest.mock.patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):  # noqa: S108
                table = handle._create_status_bar()

                # table.width が 98 (100 - 2) であることを確認
                assert table.width == 98

            handle.finish()


class TestCreateDisplayWithTasks:
    """_create_display でタスクがある場合のテスト"""

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

    def test_create_display_with_tasks(self, mock_config, tmp_path):
        """タスクがある場合は Group を返す"""
        import rich.console
        import rich.progress

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            # タスクをモック
            mock_task = unittest.mock.MagicMock(spec=rich.progress.Task)
            handle._progress = unittest.mock.MagicMock()
            handle._progress.tasks = [mock_task]

            display = handle._create_display()

            # Group が返されることを確認
            assert isinstance(display, rich.console.Group)

            handle.finish()


class TestPauseResumeLive:
    """pause_live と resume_live メソッドのテスト"""

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

    def test_pause_live(self, mock_config, tmp_path):
        """pause_live が _live.stop を呼ぶ"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            mock_live = unittest.mock.MagicMock()
            handle._live = mock_live

            handle.pause_live()

            mock_live.stop.assert_called_once()

            handle.finish()

    def test_resume_live(self, mock_config, tmp_path):
        """resume_live が _live.start を呼ぶ"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            mock_live = unittest.mock.MagicMock()
            handle._live = mock_live

            handle.resume_live()

            mock_live.start.assert_called_once()

            handle.finish()


class TestGetSeleniumDriverCreation:
    """get_selenium_driver の新規作成とエラーハンドリングのテスト"""

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

    def test_get_selenium_driver_create_new(self, mock_config, tmp_path):
        """Selenium ドライバーを新規作成"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
            unittest.mock.patch("selenium.webdriver.support.wait.WebDriverWait"),
        ):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            assert handle.selenium is None

            driver, wait = handle.get_selenium_driver()

            assert driver is mock_driver
            assert handle.selenium is not None
            assert handle.selenium.driver is mock_driver

            handle.finish()

    def test_get_selenium_driver_error_without_clear_profile(self, mock_config, tmp_path):
        """Selenium 起動失敗時にエラーを投げる（プロファイル削除なし）"""
        import my_lib.selenium_util

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("my_lib.selenium_util.create_driver", side_effect=Exception("起動失敗")),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete_profile,
        ):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            with pytest.raises(my_lib.selenium_util.SeleniumError, match="Selenium の起動に失敗しました"):
                handle.get_selenium_driver()

            # clear_profile_on_browser_error=False なのでプロファイル削除されない
            mock_delete_profile.assert_not_called()

            handle.finish()

    def test_get_selenium_driver_error_with_clear_profile(self, mock_config, tmp_path):
        """Selenium 起動失敗時にプロファイルを削除"""
        import my_lib.selenium_util

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("my_lib.selenium_util.create_driver", side_effect=Exception("起動失敗")),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete_profile,
        ):
            handle = amazhist.handle.Handle(
                config=amazhist.config.Config.load(mock_config), clear_profile_on_browser_error=True
            )

            with pytest.raises(my_lib.selenium_util.SeleniumError, match="Selenium の起動に失敗しました"):
                handle.get_selenium_driver()

            # clear_profile_on_browser_error=True なのでプロファイル削除される
            mock_delete_profile.assert_called_once_with("Amazhist", handle.config.selenium_data_dir_path)

            handle.finish()


class TestDatabaseProxyMethodsCoverage:
    """データベースプロキシメソッドのカバレッジテスト"""

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
        """Handle インスタンス（ignore_cache=False）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_get_item_count_by_year(self, handle):
        """get_item_count_by_year が db を呼び出す"""
        handle._db.get_item_count_by_year.return_value = 50
        result = handle.get_item_count_by_year(2024)
        assert result == 50
        handle._db.get_item_count_by_year.assert_called_once_with(2024)

    def test_get_order_stat_no_ignore_cache(self, handle):
        """ignore_cache=False の場合 DB を呼び出す"""
        handle._db.exists_order.return_value = True
        result = handle.get_order_stat("ORDER-123")
        assert result is True
        handle._db.exists_order.assert_called_once_with("ORDER-123")

    def test_get_cache_last_modified(self, handle):
        """get_cache_last_modified が db を呼び出す"""
        import datetime

        expected = datetime.datetime(2024, 6, 15, 10, 30, 0)
        handle._db.get_last_modified.return_value = expected
        result = handle.get_cache_last_modified()
        assert result == expected
        handle._db.get_last_modified.assert_called_once()

    def test_get_page_checked_no_ignore_cache(self, handle):
        """ignore_cache=False の場合 DB を呼び出す"""
        handle._db.is_page_checked.return_value = True
        result = handle.get_page_checked(2024, 3)
        assert result is True
        handle._db.is_page_checked.assert_called_once_with(2024, 3)

    def test_get_year_checked_no_ignore_cache(self, handle):
        """ignore_cache=False の場合 DB を呼び出す"""
        handle._db.is_year_checked.return_value = True
        result = handle.get_year_checked(2024)
        assert result is True
        handle._db.is_year_checked.assert_called_once_with(2024)

    def test_get_unresolved_error_count_by_year(self, handle):
        """get_unresolved_error_count_by_year が db を呼び出す"""
        handle._db.get_unresolved_error_count_by_year.return_value = 5
        result = handle.get_unresolved_error_count_by_year(2024)
        assert result == 5
        handle._db.get_unresolved_error_count_by_year.assert_called_once_with(2024)

    def test_get_error_by_id(self, handle):
        """get_error_by_id が db を呼び出す"""
        mock_error = amazhist.database.ErrorLog(
            id=1, url="url1", error_type="e", context="c", retry_count=0, resolved=False
        )
        handle._db.get_error_by_id.return_value = mock_error
        result = handle.get_error_by_id(1)
        assert result is mock_error
        handle._db.get_error_by_id.assert_called_once_with(1)

    def test_get_thumbnail_asin_by_error_id(self, handle):
        """get_thumbnail_asin_by_error_id が db を呼び出す"""
        handle._db.get_thumbnail_asin_by_error_id.return_value = "B0123456789"
        result = handle.get_thumbnail_asin_by_error_id(123)
        assert result == "B0123456789"
        handle._db.get_thumbnail_asin_by_error_id.assert_called_once_with(123)


class TestSetStatusTTY:
    """set_status の TTY 環境テスト"""

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

    def test_set_status_tty_refresh_display(self, mock_config, tmp_path):
        """TTY 環境で set_status が _refresh_display を呼ぶ"""
        import rich.console

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            # TTY をシミュレート
            mock_console = unittest.mock.MagicMock(spec=rich.console.Console)
            mock_console.is_terminal = True
            handle._console = mock_console

            with unittest.mock.patch.object(handle, "_refresh_display") as mock_refresh:
                handle.set_status("処理中...")

                mock_refresh.assert_called_once()

            handle.finish()


class TestGetFailedOrders:
    """get_failed_orders メソッドのテスト"""

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

    def test_get_failed_orders(self, mock_config, tmp_path):
        """get_failed_orders が db を呼び出す"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._db = unittest.mock.MagicMock()
            handle._db.get_failed_orders.return_value = [{"order_no": "ORDER-001", "year": 2024, "page": 1}]

            result = handle.get_failed_orders()

            assert len(result) == 1
            assert result[0]["order_no"] == "ORDER-001"
            handle._db.get_failed_orders.assert_called_once()

            handle.finish()

    def test_get_failed_years(self, mock_config, tmp_path):
        """get_failed_years が db を呼び出す"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            handle._db = unittest.mock.MagicMock()
            mock_error = amazhist.database.ErrorLog(
                id=1,
                url="url",
                error_type="order_count_fallback",
                context="year",
                retry_count=0,
                resolved=False,
            )
            handle._db.get_failed_years.return_value = [mock_error]

            result = handle.get_failed_years()

            assert len(result) == 1
            handle._db.get_failed_years.assert_called_once()

            handle.finish()
