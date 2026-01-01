#!/usr/bin/env python3
# ruff: noqa: S101
"""
crawler.py のテスト
"""
import unittest.mock

import pytest

import amazhist.config
import amazhist.crawler
import amazhist.handle


class TestGenOrderUrl:
    """gen_order_url のテスト"""

    def test_gen_order_url(self):
        """注文URLの生成"""
        result = amazhist.crawler.gen_order_url("503-1234567-8901234")

        assert "503-1234567-8901234" in result
        assert "order-details" in result


class TestGenHistUrl:
    """gen_hist_url のテスト"""

    def test_gen_hist_url_year(self):
        """年指定の履歴URL"""
        result = amazhist.crawler.gen_hist_url(2025, 1)

        assert "2025" in result
        assert "startIndex=0" in result

    def test_gen_hist_url_page2(self):
        """2ページ目"""
        result = amazhist.crawler.gen_hist_url(2025, 2)

        assert "startIndex=10" in result

    def test_gen_hist_url_archive(self):
        """アーカイブ（文字列）"""
        result = amazhist.crawler.gen_hist_url("archived", 1)

        assert "archived" in result


class TestShutdownFlag:
    """シャットダウンフラグのテスト"""

    def test_is_shutdown_requested_default(self):
        """デフォルトは False"""
        amazhist.crawler.reset_shutdown_flag()
        assert amazhist.crawler.is_shutdown_requested() is False

    def test_reset_shutdown_flag(self):
        """シャットダウンフラグのリセット"""
        amazhist.crawler.reset_shutdown_flag()
        assert amazhist.crawler.is_shutdown_requested() is False


class TestSignalHandler:
    """シグナルハンドラのテスト"""

    def test_setup_signal_handler(self):
        """シグナルハンドラの設定"""
        # 例外が発生しないことを確認
        amazhist.crawler.setup_signal_handler()


class TestConstants:
    """定数のテスト"""

    def test_order_count_per_page(self):
        """ページあたりの注文数"""
        import amazhist.const

        assert amazhist.const.ORDER_COUNT_PER_PAGE == 10

    def test_hist_url(self):
        """履歴URL"""
        import amazhist.const

        assert "amazon.co.jp" in amazhist.const.HIST_URL


class TestFetchOrderList:
    """fetch_order_list のテスト"""

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
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            yield h
            h.finish()

    def test_fetch_order_list_shutdown_requested(self, handle):
        """シャットダウンリクエスト時は即座に終了"""
        with (
            unittest.mock.patch(
                "amazhist.crawler._fetch_order_list_all_year"
            ) as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
        ):
            amazhist.crawler.fetch_order_list(handle)

            # シャットダウンリクエスト時もフェッチは呼ばれる
            mock_fetch.assert_called_once()

    def test_fetch_order_list_normal(self, handle):
        """正常系のテスト"""
        amazhist.crawler.reset_shutdown_flag()

        with unittest.mock.patch(
            "amazhist.crawler._fetch_order_list_all_year"
        ) as mock_fetch:
            amazhist.crawler.fetch_order_list(handle)

            mock_fetch.assert_called_once_with(handle)

    def test_fetch_order_list_exception(self, handle):
        """例外発生時のテスト"""
        amazhist.crawler.reset_shutdown_flag()

        with (
            unittest.mock.patch(
                "amazhist.crawler._fetch_order_list_all_year",
                side_effect=Exception("テストエラー"),
            ),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="テストエラー"),
        ):
            amazhist.crawler.fetch_order_list(handle)

        mock_dump.assert_called_once()


class TestVisitUrl:
    """visit_url のテスト"""

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
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            yield h
            h.finish()

    def test_visit_url_success(self, handle):
        """URLアクセス成功"""
        driver, _ = handle.get_selenium_driver()

        with unittest.mock.patch("amazhist.crawler._wait_for_loading"):
            amazhist.crawler.visit_url(handle, "https://example.com", "test")

        driver.get.assert_called_once_with("https://example.com")

    def test_visit_url_timeout_retry(self, handle):
        """タイムアウト時のリトライ"""
        from selenium.common.exceptions import TimeoutException

        driver, _ = handle.get_selenium_driver()
        call_count = 0

        def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutException("タイムアウト")

        driver.get.side_effect = side_effect

        with unittest.mock.patch("amazhist.crawler._wait_for_loading"):
            amazhist.crawler.visit_url(handle, "https://example.com", "test")

        assert call_count == 3

    def test_visit_url_timeout_max_retry(self, handle):
        """最大リトライ超過"""
        from selenium.common.exceptions import TimeoutException

        driver, _ = handle.get_selenium_driver()
        driver.get.side_effect = TimeoutException("タイムアウト")

        with (
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            pytest.raises(TimeoutException),
        ):
            amazhist.crawler.visit_url(handle, "https://example.com", "test")


class TestKeepLoggedOn:
    """_keep_logged_on のテスト"""

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
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            yield h
            h.finish()

    def test_keep_logged_on_not_login_page(self, handle):
        """ログインページでない場合は何もしない"""
        driver, _ = handle.get_selenium_driver()
        driver.title = "Amazon.co.jp 購入履歴"

        amazhist.crawler._keep_logged_on(handle)

        # find_element が呼ばれないことを確認
        driver.find_element.assert_not_called()

    def test_keep_logged_on_login_page(self, handle):
        """ログインページの場合"""
        driver, _ = handle.get_selenium_driver()
        driver.title = "Amazonサインイン"

        # ログイン成功をシミュレート
        def change_title(*args, **kwargs):
            driver.title = "Amazon.co.jp"

        mock_submit = unittest.mock.MagicMock()
        mock_submit.click.side_effect = change_title
        driver.find_element.return_value = mock_submit

        # CAPTCHA入力フォームがないことをシミュレート
        driver.find_elements.return_value = []

        with unittest.mock.patch("amazhist.crawler._wait_for_loading"):
            amazhist.crawler._keep_logged_on(handle)


class TestFetchYearList:
    """fetch_year_list のテスト"""

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
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_fetch_year_list(self, handle):
        """年リストの取得"""
        driver, _ = handle.get_selenium_driver()

        # ドロップダウンの年要素をシミュレート
        year_elements = []
        for year in ["過去3か月", "2024年", "2023年", "2022年"]:
            elem = unittest.mock.MagicMock()
            elem.text = year
            year_elements.append(elem)

        driver.find_elements.return_value = year_elements

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
        ):
            year_list = amazhist.crawler.fetch_year_list(handle)

        assert year_list == [2022, 2023, 2024]
        handle._db.set_year_list.assert_called_once_with([2022, 2023, 2024])


class TestRetryFailedItems:
    """リトライ機能のテスト"""

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
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_retry_failed_orders_empty(self, handle):
        """リトライ対象なし"""
        handle._db.get_failed_order_numbers.return_value = []

        success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_orders_success(self, handle):
        """リトライ成功"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_order_numbers.return_value = ["ORDER-001"]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 1
        assert fail == 0
        handle._db.mark_errors_resolved_by_order_no.assert_called_once_with("ORDER-001")

    def test_retry_failed_orders_failure(self, handle):
        """リトライ失敗"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_order_numbers.return_value = ["ORDER-001"]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.order.parse_order", return_value=False),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 0
        assert fail == 1

    def test_retry_failed_orders_exception(self, handle):
        """リトライ中に例外発生"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_order_numbers.return_value = ["ORDER-001"]

        with (
            unittest.mock.patch(
                "amazhist.crawler.visit_url",
                side_effect=Exception("接続エラー"),
            ),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 0
        assert fail == 1

    def test_retry_failed_categories_empty(self, handle):
        """カテゴリリトライ対象なし"""
        handle._db.get_failed_category_items.return_value = []

        success, fail = amazhist.crawler._retry_failed_categories(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_categories_success(self, handle):
        """カテゴリリトライ成功"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_category_items.return_value = [
            {"url": "https://example.com/item", "name": "テスト商品", "error_id": 1}
        ]

        with (
            unittest.mock.patch(
                "amazhist.item.fetch_item_category",
                return_value=["カテゴリ1", "カテゴリ2"],
            ),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_categories(handle)

        assert success == 1
        assert fail == 0
        handle._db.update_item_category.assert_called_once()
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_retry_failed_categories_empty_category(self, handle):
        """カテゴリが空で返される場合"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_category_items.return_value = [
            {"url": "https://example.com/item", "name": "テスト商品", "error_id": 1}
        ]

        with (
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=[]),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_categories(handle)

        assert success == 0
        assert fail == 1

    def test_retry_failed_thumbnails_empty(self, handle):
        """サムネイルリトライ対象なし"""
        handle._db.get_failed_thumbnail_items.return_value = []

        success, fail = amazhist.crawler._retry_failed_thumbnails(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_thumbnails_no_asin(self, handle):
        """ASINなしの場合はスキップ"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_thumbnail_items.return_value = [
            {"thumb_url": "https://example.com/thumb.jpg", "name": "テスト", "error_id": 1}
        ]

        success, fail = amazhist.crawler._retry_failed_thumbnails(handle)

        assert success == 0
        assert fail == 1

    def test_retry_failed_thumbnails_success(self, handle):
        """サムネイルリトライ成功"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_thumbnail_items.return_value = [
            {
                "thumb_url": "https://example.com/thumb.jpg",
                "name": "テスト",
                "asin": "B012345678",
                "error_id": 1,
            }
        ]

        with (
            unittest.mock.patch("amazhist.item._save_thumbnail"),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_thumbnails(handle)

        assert success == 1
        assert fail == 0
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_retry_failed_items_main_flow(self, handle):
        """retry_failed_items のメインフロー"""
        amazhist.crawler.reset_shutdown_flag()
        handle._db.get_failed_order_numbers.return_value = []
        handle._db.get_failed_category_items.return_value = []
        handle._db.get_failed_thumbnail_items.return_value = []

        amazhist.crawler.retry_failed_items(handle)

        # 例外が発生しないことを確認


class TestDebugMode:
    """デバッグモードのテスト"""

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
    def handle_debug(self, mock_config, tmp_path):
        """デバッグモードの Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(
                config=amazhist.config.Config.load(mock_config),
                debug_mode=True,
            )
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_debug_mode_enabled(self, handle_debug):
        """デバッグモードが有効"""
        assert handle_debug.debug_mode is True

    def test_debug_mode_ignore_cache(self, mock_config, tmp_path):
        """デバッグモードでは ignore_cache も True"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            # ignore_cache は app.py で設定されるので、ここでは別々にテスト
            h = amazhist.handle.Handle(
                config=amazhist.config.Config.load(mock_config),
                debug_mode=True,
                ignore_cache=True,
            )
            assert h.debug_mode is True
            assert h.ignore_cache is True
            h.finish()
