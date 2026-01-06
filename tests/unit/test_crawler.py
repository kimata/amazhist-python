#!/usr/bin/env python3
# ruff: noqa: S101
"""
crawler.py のテスト
"""

import unittest.mock

import my_lib.graceful_shutdown
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


class TestShutdownFlag:
    """シャットダウンフラグのテスト"""

    def test_is_shutdown_requested_default(self):
        """デフォルトは False"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        assert amazhist.crawler.is_shutdown_requested() is False

    def test_reset_shutdown_flag(self):
        """シャットダウンフラグのリセット"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        assert my_lib.graceful_shutdown.is_shutdown_requested() is False


class TestSignalHandler:
    """シグナルハンドラのテスト"""

    def test_setup_signal_handler(self):
        """シグナルハンドラの設定"""
        # 例外が発生しないことを確認
        my_lib.graceful_shutdown.setup_signal_handler()


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
            unittest.mock.patch("amazhist.crawler._fetch_order_list_all_year") as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
        ):
            amazhist.crawler.fetch_order_list(handle)

            # シャットダウンリクエスト時もフェッチは呼ばれる
            mock_fetch.assert_called_once()

    def test_fetch_order_list_normal(self, handle):
        """正常系のテスト"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        with unittest.mock.patch("amazhist.crawler._fetch_order_list_all_year") as mock_fetch:
            amazhist.crawler.fetch_order_list(handle)

            mock_fetch.assert_called_once_with(handle)

    def test_fetch_order_list_exception(self, handle):
        """例外発生時のテスト"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

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
    """_fetch_year_list のテスト"""

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
            year_list = amazhist.crawler._fetch_year_list(handle)

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
        handle._db.get_failed_orders.return_value = []

        success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_orders_success(self, handle):
        """リトライ成功"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        handle._db.get_failed_orders.return_value = [
            {
                "error_id": 1,
                "order_no": "ORDER-001",
                "order_year": None,
                "order_page": None,
                "order_index": None,
            }
        ]

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
        my_lib.graceful_shutdown.reset_shutdown_flag()
        handle._db.get_failed_orders.return_value = [
            {
                "error_id": 1,
                "order_no": "ORDER-001",
                "order_year": None,
                "order_page": None,
                "order_index": None,
            }
        ]

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
        my_lib.graceful_shutdown.reset_shutdown_flag()
        handle._db.get_failed_orders.return_value = [
            {
                "error_id": 1,
                "order_no": "ORDER-001",
                "order_year": None,
                "order_page": None,
                "order_index": None,
            }
        ]

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
        my_lib.graceful_shutdown.reset_shutdown_flag()
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
        my_lib.graceful_shutdown.reset_shutdown_flag()
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
        my_lib.graceful_shutdown.reset_shutdown_flag()
        handle._db.get_failed_thumbnail_items.return_value = [
            {"thumb_url": "https://example.com/thumb.jpg", "name": "テスト", "error_id": 1}
        ]

        success, fail = amazhist.crawler._retry_failed_thumbnails(handle)

        assert success == 0
        assert fail == 1

    def test_retry_failed_thumbnails_success(self, handle):
        """サムネイルリトライ成功"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
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
        my_lib.graceful_shutdown.reset_shutdown_flag()
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


class TestGetCallerName:
    """_get_caller_name のテスト"""

    def test_get_caller_name_normal(self):
        """呼び出し元の関数名を取得"""
        result = amazhist.crawler._get_caller_name()
        assert result == "test_get_caller_name_normal"

    def test_get_caller_name_with_none_frame(self):
        """フレームが None の場合"""
        import inspect

        with unittest.mock.patch.object(inspect, "currentframe", return_value=None):
            result = amazhist.crawler._get_caller_name()
            assert result == "unknown"


class TestWaitForLoading:
    """_wait_for_loading のテスト"""

    def test_wait_for_loading(self):
        """待機関数のテスト"""
        mock_handle = unittest.mock.MagicMock()

        with unittest.mock.patch("time.sleep") as mock_sleep:
            amazhist.crawler._wait_for_loading(mock_handle, sec=3)
            mock_sleep.assert_called_once_with(3)

    def test_wait_for_loading_default(self):
        """デフォルト待機時間のテスト"""
        mock_handle = unittest.mock.MagicMock()

        with unittest.mock.patch("time.sleep") as mock_sleep:
            amazhist.crawler._wait_for_loading(mock_handle)
            mock_sleep.assert_called_once_with(2)


class TestResolveCaptcha:
    """_resolve_captcha のテスト"""

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

    def test_resolve_captcha_success(self, handle, tmp_path):
        """CAPTCHA解決成功"""
        driver, _ = handle.get_selenium_driver()

        # CAPTCHA画像要素のモック
        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b"fake_png_data"

        # Track CAPTCHA status - starts True (present), becomes False after submit
        captcha_present = [True]

        def find_element_side_effect(by, xpath):
            if "captcha" in xpath and "img" in xpath:
                return mock_img
            elif "cvf_captcha_input" in xpath:
                return unittest.mock.MagicMock()
            elif "submit" in xpath:
                # After submit click, CAPTCHA is resolved
                def click_side_effect():
                    captcha_present[0] = False

                mock_btn = unittest.mock.MagicMock()
                mock_btn.click.side_effect = click_side_effect
                return mock_btn
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if "cvf_captcha_input" in xpath:
                if captcha_present[0]:
                    return [unittest.mock.MagicMock()]
                return []
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        with (
            unittest.mock.patch("builtins.input", return_value="ABC123"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            amazhist.crawler._resolve_captcha(handle)

        # Just verify no exception was raised

    def test_resolve_captcha_retry_then_success(self, handle, tmp_path):
        """CAPTCHA解決リトライ後成功"""
        driver, _ = handle.get_selenium_driver()

        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b"fake_png_data"

        # Track retry count - success on 2nd attempt
        attempt_count = [0]

        def find_element_side_effect(by, xpath):
            if "captcha" in xpath and "img" in xpath:
                return mock_img
            elif "cvf_captcha_input" in xpath:
                return unittest.mock.MagicMock()
            elif "submit" in xpath:

                def click_side_effect():
                    attempt_count[0] += 1

                mock_btn = unittest.mock.MagicMock()
                mock_btn.click.side_effect = click_side_effect
                return mock_btn
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if "cvf_captcha_input" in xpath:
                # First attempt fails (captcha still present), second succeeds
                if attempt_count[0] < 2:
                    return [unittest.mock.MagicMock()]
                return []
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        with (
            unittest.mock.patch("builtins.input", return_value="ABC123"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            amazhist.crawler._resolve_captcha(handle)

    def test_resolve_captcha_failure(self, handle):
        """CAPTCHA解決失敗"""
        driver, _ = handle.get_selenium_driver()

        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b"fake_png_data"

        mock_input = unittest.mock.MagicMock()
        mock_submit = unittest.mock.MagicMock()

        def find_element_side_effect(by, xpath):
            if "captcha" in xpath and "img" in xpath:
                return mock_img
            elif "cvf_captcha_input" in xpath:
                return mock_input
            elif "submit" in xpath:
                return mock_submit
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        # 常に CAPTCHA が残る
        driver.find_elements.return_value = [mock_input]

        with (
            unittest.mock.patch("builtins.input", return_value="WRONG"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
            pytest.raises(Exception, match="画像認証を解決できませんでした"),
        ):
            amazhist.crawler._resolve_captcha(handle)


class TestExecuteLogin:
    """_execute_login のテスト"""

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

    def test_execute_login_with_email_and_continue(self, handle):
        """メールアドレス入力と続行ボタンがある場合"""
        driver, _ = handle.get_selenium_driver()

        mock_email = unittest.mock.MagicMock()
        mock_continue = unittest.mock.MagicMock()
        mock_password = unittest.mock.MagicMock()
        mock_remember = unittest.mock.MagicMock()
        mock_remember.get_attribute.return_value = None
        mock_submit = unittest.mock.MagicMock()

        def find_element_side_effect(by, xpath):
            if "ap_email" in xpath:
                return mock_email
            elif "continue" in xpath:
                return mock_continue
            elif "ap_password" in xpath:
                return mock_password
            elif "rememberMe" in xpath:
                return mock_remember
            elif "signInSubmit" in xpath:
                return mock_submit
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if 'ap_email" and @type!="hidden"' in xpath:
                return [mock_email]
            elif "continue" in xpath:
                return [mock_continue]
            elif "ap_password" in xpath:
                return [mock_password]
            elif "rememberMe" in xpath:
                return [mock_remember]
            elif "cvf_captcha_input" in xpath:
                return []
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        with (
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
        ):
            amazhist.crawler._execute_login(handle)

        mock_email.clear.assert_called_once()
        mock_email.send_keys.assert_called_once_with("test@example.com")
        mock_continue.click.assert_called_once()
        mock_password.clear.assert_called_once()
        mock_password.send_keys.assert_called_once_with("password")
        mock_remember.click.assert_called_once()
        mock_submit.click.assert_called_once()

    def test_execute_login_with_captcha(self, handle):
        """CAPTCHAがある場合"""
        driver, _ = handle.get_selenium_driver()

        mock_submit = unittest.mock.MagicMock()
        mock_captcha = unittest.mock.MagicMock()

        def find_element_side_effect(by, xpath):
            if "signInSubmit" in xpath:
                return mock_submit
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if "cvf_captcha_input" in xpath:
                return [mock_captcha]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        with (
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("amazhist.crawler._resolve_captcha") as mock_resolve,
        ):
            amazhist.crawler._execute_login(handle)

        mock_resolve.assert_called_once_with(handle)


class TestKeepLoggedOnFailure:
    """_keep_logged_on ログイン失敗のテスト"""

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

    def test_keep_logged_on_login_failure(self, handle):
        """ログイン失敗時は例外を発生"""
        driver, _ = handle.get_selenium_driver()
        driver.title = "Amazonサインイン"

        # ログインしてもタイトルが変わらない
        driver.find_elements.return_value = []

        mock_submit = unittest.mock.MagicMock()
        driver.find_element.return_value = mock_submit

        with (
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
            pytest.raises(Exception, match="ログインに失敗しました"),
        ):
            amazhist.crawler._keep_logged_on(handle)


class TestFetchOrderCount:
    """_fetch_order_count 関連のテスト"""

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

    def test_fetch_order_count_by_year(self, handle):
        """年ごとの注文数取得"""
        with unittest.mock.patch("amazhist.order.parse_order_count", return_value=15):
            result = amazhist.crawler._fetch_order_count_by_year(handle, 2024)

        assert result == 15

    def test_fetch_order_count(self, handle):
        """全年の注文数取得"""
        import datetime

        handle._db.get_year_list.return_value = [2022, 2023, 2024]
        handle._db.get_last_modified.return_value = datetime.datetime(2023, 6, 1)
        handle._db.get_year_order_count.return_value = 10

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with unittest.mock.patch("amazhist.order.parse_order_count", return_value=20):
            amazhist.crawler._fetch_order_count(handle)

        # 2023年以降は新しく取得、2022年はキャッシュ
        assert handle._db.set_year_status.call_count == 2


class TestFetchOrderListAllYear:
    """_fetch_order_list_all_year のテスト"""

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

    def test_fetch_order_list_all_year_target_year_not_found(self, handle):
        """年指定モードで指定年が存在しない場合"""
        handle.target_year = 2020

        with (
            unittest.mock.patch("amazhist.crawler._fetch_year_list", return_value=[2023, 2024]),
            unittest.mock.patch("amazhist.crawler._fetch_order_count"),
        ):
            amazhist.crawler._fetch_order_list_all_year(handle)

        # 何も処理されないことを確認

    def test_fetch_order_list_all_year_target_year(self, handle):
        """年指定モードで正常処理"""
        handle.target_year = 2024
        handle._db.get_year_order_count.return_value = 10

        with (
            unittest.mock.patch("amazhist.crawler._fetch_year_list", return_value=[2023, 2024]),
            unittest.mock.patch("amazhist.crawler._fetch_order_count"),
            unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year") as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            amazhist.crawler._fetch_order_list_all_year(handle)

        # 2024年のみ処理される
        mock_fetch.assert_called_once_with(handle, 2024)

    def test_fetch_order_list_all_year_debug_mode(self, handle):
        """デバッグモードでは1年だけ処理"""
        import datetime

        handle.debug_mode = True
        handle._db.get_last_modified.return_value = datetime.datetime(2023, 1, 1)
        handle._db.get_total_order_count.return_value = 100
        handle._db.is_year_checked.return_value = False

        with (
            unittest.mock.patch("amazhist.crawler._fetch_year_list", return_value=[2022, 2023, 2024]),
            unittest.mock.patch("amazhist.crawler._fetch_order_count"),
            unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year") as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            amazhist.crawler._fetch_order_list_all_year(handle)

        # 1年だけ処理される
        assert mock_fetch.call_count == 1

    def test_fetch_order_list_all_year_cached_year(self, handle):
        """キャッシュ済みの年はスキップ"""
        import datetime

        handle._db.get_last_modified.return_value = datetime.datetime(2020, 1, 1)
        handle._db.get_total_order_count.return_value = 100
        handle._db.is_year_checked.return_value = True
        handle._db.get_year_order_count.return_value = 10

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with (
            unittest.mock.patch("amazhist.crawler._fetch_year_list", return_value=[2019]),
            unittest.mock.patch("amazhist.crawler._fetch_order_count"),
            unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year") as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            amazhist.crawler._fetch_order_list_all_year(handle)

        # キャッシュ済みなのでスキップ
        mock_fetch.assert_not_called()

    def test_fetch_order_list_all_year_shutdown_requested(self, handle):
        """シャットダウンリクエスト時は終了"""
        import datetime

        handle._db.get_last_modified.return_value = datetime.datetime(2024, 1, 1)
        handle._db.get_total_order_count.return_value = 100

        with (
            unittest.mock.patch("amazhist.crawler._fetch_year_list", return_value=[2022, 2023, 2024]),
            unittest.mock.patch("amazhist.crawler._fetch_order_count"),
            unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year") as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
        ):
            amazhist.crawler._fetch_order_list_all_year(handle)

        mock_fetch.assert_not_called()


class TestRetryOrderFromListPage:
    """_retry_order_from_list_page のテスト"""

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

    def test_retry_order_from_list_page_index_exceeded(self, handle):
        """インデックスが注文数を超えている場合"""
        driver, _ = handle.get_selenium_driver()

        def find_elements_side_effect(by, xpath):
            if "order-card js-order-card" in xpath:
                return []  # No orders found
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": 5,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is False

    def test_retry_order_from_list_page_no_order_no_element(self, handle):
        """注文番号要素が見つからない場合"""
        driver, _ = handle.get_selenium_driver()

        mock_order = unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "order-card js-order-card" in xpath:
                return [mock_order]
            # yohtmlc-order-id not found -> empty list
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.parser.parse_date"),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is False

    def test_retry_order_from_list_page_order_not_found_by_no(self, handle):
        """注文番号で注文が見つからない場合"""
        driver, _ = handle.get_selenium_driver()

        mock_order = unittest.mock.MagicMock()
        mock_no_elem = unittest.mock.MagicMock()
        mock_no_elem.text = "DIFFERENT-ORDER-NO"

        def find_elements_side_effect(by, xpath):
            if "order-card js-order-card" in xpath and "[" not in xpath:
                return [mock_order]
            elif "yohtmlc-order-id" in xpath:
                return [mock_no_elem]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": None,
            "order_no": "TARGET-ORDER-NO",
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is False

    def test_retry_order_from_list_page_success_with_detail_link(self, handle):
        """詳細リンクがある場合の成功"""
        driver, _ = handle.get_selenium_driver()

        mock_order = unittest.mock.MagicMock()
        mock_no_elem = unittest.mock.MagicMock()
        mock_no_elem.text = "ORDER-001"
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2024年1月15日"
        mock_detail_link = unittest.mock.MagicMock()
        mock_detail_link.get_attribute.return_value = "https://example.com/order-details"

        def find_element_side_effect(by, xpath):
            if "a-color-secondary" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH matches first, then indexed versions
            if "order-card js-order-card" in xpath:
                if "[" in xpath:
                    # This is an indexed query like ORDER_XPATH + "[1]"
                    return [mock_order]
                return [mock_order]
            elif "yohtmlc-order-id" in xpath:
                return [mock_no_elem]
            elif "order-details" in xpath:
                return [mock_detail_link]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.parser.parse_date") as mock_parse_date,
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            import datetime

            mock_parse_date.return_value = datetime.datetime(2024, 1, 15)
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is True

    def test_retry_order_from_list_page_no_detail_link(self, handle):
        """詳細リンクがない場合はURLを構築"""
        driver, _ = handle.get_selenium_driver()

        mock_order = unittest.mock.MagicMock()
        mock_no_elem = unittest.mock.MagicMock()
        mock_no_elem.text = "ORDER-001"
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2024年1月15日"

        def find_element_side_effect(by, xpath):
            if "a-color-secondary" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if "order-card js-order-card" in xpath:
                return [mock_order]
            elif "yohtmlc-order-id" in xpath:
                return [mock_no_elem]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.parser.parse_date") as mock_parse_date,
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            import datetime

            mock_parse_date.return_value = datetime.datetime(2024, 1, 15)
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is True

    def test_retry_order_from_list_page_detail_link_no_href(self, handle):
        """詳細リンクにhrefがない場合"""
        driver, _ = handle.get_selenium_driver()

        mock_order = unittest.mock.MagicMock()
        mock_no_elem = unittest.mock.MagicMock()
        mock_no_elem.text = "ORDER-001"
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2024年1月15日"
        mock_detail_link = unittest.mock.MagicMock()
        mock_detail_link.get_attribute.return_value = None

        def find_element_side_effect(by, xpath):
            if "a-color-secondary" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if "order-card js-order-card" in xpath:
                return [mock_order]
            elif "yohtmlc-order-id" in xpath:
                return [mock_no_elem]
            elif "order-details" in xpath:
                return [mock_detail_link]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.parser.parse_date") as mock_parse_date,
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            import datetime

            mock_parse_date.return_value = datetime.datetime(2024, 1, 15)
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is True

    def test_retry_order_from_list_page_find_by_order_no_success(self, handle):
        """注文番号で注文を見つけて成功"""
        driver, _ = handle.get_selenium_driver()

        mock_order = unittest.mock.MagicMock()
        mock_no_elem = unittest.mock.MagicMock()
        mock_no_elem.text = "TARGET-ORDER-NO"
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2024年1月15日"
        mock_detail_link = unittest.mock.MagicMock()
        mock_detail_link.get_attribute.return_value = "https://example.com/order-details"

        def find_element_side_effect(by, xpath):
            if "a-color-secondary" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        # Track which xpath we're searching in
        def find_elements_side_effect(by, xpath):
            # When looking for order cards (without index)
            if "order-card js-order-card" in xpath and "][" not in xpath:
                return [mock_order]
            # When looking for order id within indexed xpath (ORDER_XPATH + "[1]")
            elif "yohtmlc-order-id" in xpath:
                return [mock_no_elem]
            # When looking for details link
            elif "order-details" in xpath:
                return [mock_detail_link]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2024,
            "order_page": 1,
            "order_index": None,  # No index, find by order_no
            "order_no": "TARGET-ORDER-NO",
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.parser.parse_date") as mock_parse_date,
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            import datetime

            mock_parse_date.return_value = datetime.datetime(2024, 1, 15)
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is True


class TestRetryFailedYears:
    """_retry_failed_years のテスト"""

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

    def test_retry_failed_years_empty(self, handle):
        """再巡回対象なし"""
        handle._db.get_failed_years.return_value = []

        success, fail = amazhist.crawler._retry_failed_years(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_years_no_valid_years(self, handle):
        """有効な年がない場合"""
        import amazhist.database

        error = amazhist.database.ErrorLog(
            id=1,
            url="",
            error_type="order_count_fallback",
            context="order",
            retry_count=0,
            resolved=False,
            order_year=None,
        )
        handle._db.get_failed_years.return_value = [error]

        success, fail = amazhist.crawler._retry_failed_years(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_years_success(self, handle):
        """年の再巡回成功"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="",
            error_type="order_count_fallback",
            context="order",
            retry_count=0,
            resolved=False,
            order_year=2024,
        )
        handle._db.get_failed_years.return_value = [error]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with (
            unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year"),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            success, fail = amazhist.crawler._retry_failed_years(handle)

        assert success == 1
        assert fail == 0
        handle._db.reset_year_status.assert_called_once_with(2024)
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_retry_failed_years_failure(self, handle):
        """年の再巡回失敗"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="",
            error_type="order_count_fallback",
            context="order",
            retry_count=0,
            resolved=False,
            order_year=2024,
        )
        handle._db.get_failed_years.return_value = [error]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with (
            unittest.mock.patch(
                "amazhist.crawler._fetch_order_list_by_year",
                side_effect=Exception("エラー"),
            ),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            success, fail = amazhist.crawler._retry_failed_years(handle)

        assert success == 0
        assert fail == 1

    def test_retry_failed_years_shutdown(self, handle):
        """シャットダウン時は処理を中断"""
        import amazhist.database

        error = amazhist.database.ErrorLog(
            id=1,
            url="",
            error_type="order_count_fallback",
            context="order",
            retry_count=0,
            resolved=False,
            order_year=2024,
        )
        handle._db.get_failed_years.return_value = [error]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            success, fail = amazhist.crawler._retry_failed_years(handle)

        assert success == 0
        assert fail == 0


class TestRetrySingleOrder:
    """_retry_single_order のテスト"""

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

    def test_retry_single_order_page_only(self, handle):
        """ページ全体を再巡回"""
        error_info = {
            "order_no": None,
            "order_year": 2024,
            "order_page": 1,
            "order_index": None,
        }

        with unittest.mock.patch(
            "amazhist.crawler._fetch_order_list_by_year_page",
            return_value=(False, False, 5, 0),
        ):
            result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is True
        handle._db.set_page_checked.assert_called_once_with(2024, 1, True)

    def test_retry_single_order_page_skipped(self, handle):
        """ページがスキップされた場合"""
        error_info = {
            "order_no": None,
            "order_year": 2024,
            "order_page": 1,
            "order_index": None,
        }

        with unittest.mock.patch(
            "amazhist.crawler._fetch_order_list_by_year_page",
            return_value=(True, False, 5, 0),
        ):
            result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is True
        handle._db.set_page_checked.assert_not_called()

    def test_retry_single_order_page_empty(self, handle):
        """ページに注文がない場合"""
        error_info = {
            "order_no": None,
            "order_year": 2024,
            "order_page": 1,
            "order_index": None,
        }

        with unittest.mock.patch(
            "amazhist.crawler._fetch_order_list_by_year_page",
            return_value=(False, False, 0, 0),
        ):
            result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is False

    def test_retry_single_order_past_year(self, handle):
        """過去の年の注文"""
        error_info = {
            "order_no": "ORDER-001",
            "order_year": 2020,
            "order_page": 1,
            "order_index": None,
        }

        with unittest.mock.patch(
            "amazhist.crawler._retry_order_from_list_page",
            return_value=True,
        ):
            result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is True

    def test_retry_single_order_current_year_with_order_no(self, handle):
        """現在の年で注文番号がある場合"""
        import datetime

        error_info = {
            "order_no": "ORDER-001",
            "order_year": datetime.datetime.now().year,
            "order_page": 1,
            "order_index": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is True

    def test_retry_single_order_current_year_no_order_no(self, handle):
        """現在の年で注文番号がない場合"""
        import datetime

        error_info = {
            "order_no": None,
            "order_year": datetime.datetime.now().year,
            "order_page": 1,
            "order_index": 0,
        }

        with unittest.mock.patch(
            "amazhist.crawler._retry_order_from_list_page",
            return_value=True,
        ):
            result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is True

    def test_retry_single_order_no_year_no_order_no(self, handle):
        """年情報も注文番号もない場合"""
        error_info = {
            "order_no": None,
            "order_year": None,
            "order_page": None,
            "order_index": None,
        }

        result = amazhist.crawler._retry_single_order(handle, error_info)

        assert result is False


class TestRetryErrorById:
    """retry_error_by_id のテスト"""

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

    def test_retry_error_by_id_not_found(self, handle):
        """エラーが見つからない場合"""
        handle._db.get_error_by_id.return_value = None

        result = amazhist.crawler.retry_error_by_id(handle, 999)

        assert result is False

    def test_retry_error_by_id_already_resolved(self, handle):
        """既に解決済みの場合"""
        import amazhist.database

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com",
            error_type="parse_error",
            context="order",
            retry_count=0,
            resolved=True,
        )
        handle._db.get_error_by_id.return_value = error

        result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is True

    def test_retry_error_by_id_order_success(self, handle):
        """注文エラーの再取得成功"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com",
            error_type="parse_error",
            context="order",
            retry_count=0,
            resolved=False,
            order_no="ORDER-001",
            order_year=2024,
            order_page=1,
        )
        handle._db.get_error_by_id.return_value = error

        with unittest.mock.patch(
            "amazhist.crawler._retry_single_order",
            return_value=True,
        ):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is True
        handle._db.mark_error_resolved.assert_called_once_with(1)
        handle._db.mark_errors_resolved_by_order_no.assert_called_once_with("ORDER-001")

    def test_retry_error_by_id_order_failure(self, handle):
        """注文エラーの再取得失敗"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com",
            error_type="parse_error",
            context="order",
            retry_count=0,
            resolved=False,
            order_no="ORDER-001",
        )
        handle._db.get_error_by_id.return_value = error

        with unittest.mock.patch(
            "amazhist.crawler._retry_single_order",
            return_value=False,
        ):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is False

    def test_retry_error_by_id_category_success(self, handle):
        """カテゴリエラーの再取得成功"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com/item",
            error_type="fetch_error",
            context="category",
            retry_count=0,
            resolved=False,
        )
        handle._db.get_error_by_id.return_value = error

        with unittest.mock.patch(
            "amazhist.item.fetch_item_category",
            return_value=["カテゴリ1"],
        ):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is True
        handle._db.update_item_category.assert_called_once()
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_retry_error_by_id_category_empty(self, handle):
        """カテゴリが空の場合"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com/item",
            error_type="fetch_error",
            context="category",
            retry_count=0,
            resolved=False,
        )
        handle._db.get_error_by_id.return_value = error

        with unittest.mock.patch(
            "amazhist.item.fetch_item_category",
            return_value=[],
        ):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is False

    def test_retry_error_by_id_thumbnail_success(self, handle):
        """サムネイルエラーの再取得成功"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com/thumb.jpg",
            error_type="fetch_error",
            context="thumbnail",
            retry_count=0,
            resolved=False,
        )
        handle._db.get_error_by_id.return_value = error
        handle._db.get_thumbnail_asin_by_error_id.return_value = "B012345678"

        with unittest.mock.patch("amazhist.item._save_thumbnail"):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is True
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_retry_error_by_id_thumbnail_no_asin(self, handle):
        """サムネイルエラーでASINがない場合"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com/thumb.jpg",
            error_type="fetch_error",
            context="thumbnail",
            retry_count=0,
            resolved=False,
        )
        handle._db.get_error_by_id.return_value = error
        handle._db.get_thumbnail_asin_by_error_id.return_value = None

        result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is False

    def test_retry_error_by_id_order_count_fallback(self, handle):
        """order_count_fallback エラーの再巡回"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        # order_count_fallback uses a context that's not "order", "category", or "thumbnail"
        # to trigger the elif branch at line 814
        error = amazhist.database.ErrorLog(
            id=1,
            url="",
            error_type="order_count_fallback",
            context="year",  # Use a different context to trigger the elif branch
            retry_count=0,
            resolved=False,
            order_year=2024,
            order_page=None,
        )
        handle._db.get_error_by_id.return_value = error

        with unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year"):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is True
        handle._db.reset_year_status.assert_called_once_with(2024)
        handle._db.mark_error_resolved.assert_called_once_with(1)

    def test_retry_error_by_id_exception(self, handle):
        """再取得中に例外が発生した場合"""
        import amazhist.database

        my_lib.graceful_shutdown.reset_shutdown_flag()

        error = amazhist.database.ErrorLog(
            id=1,
            url="https://example.com",
            error_type="parse_error",
            context="order",
            retry_count=0,
            resolved=False,
            order_no="ORDER-001",
        )
        handle._db.get_error_by_id.return_value = error

        with (
            unittest.mock.patch(
                "amazhist.crawler._retry_single_order",
                side_effect=Exception("エラー"),
            ),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = amazhist.crawler.retry_error_by_id(handle, 1)

        assert result is False


class TestRetryFailedItemsException:
    """retry_failed_items の例外処理テスト"""

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

    def test_retry_failed_items_exception(self, handle):
        """例外発生時のダンプ処理"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        with (
            unittest.mock.patch(
                "amazhist.crawler._retry_failed_years",
                side_effect=Exception("テストエラー"),
            ),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="テストエラー"),
        ):
            amazhist.crawler.retry_failed_items(handle)

        mock_dump.assert_called_once()

    def test_retry_failed_items_shutdown(self, handle):
        """シャットダウン時はダンプしない"""
        handle._db.get_failed_years.return_value = []
        handle._db.get_failed_orders.return_value = []
        handle._db.get_failed_category_items.return_value = []
        handle._db.get_failed_thumbnail_items.return_value = []

        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            amazhist.crawler.retry_failed_items(handle)


class TestRetryFailedOrdersShutdown:
    """_retry_failed_orders のシャットダウンテスト"""

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

    def test_retry_failed_orders_shutdown(self, handle):
        """シャットダウン時は処理を中断"""
        handle._db.get_failed_orders.return_value = [
            {
                "error_id": 1,
                "order_no": "ORDER-001",
                "order_year": None,
                "order_page": None,
                "order_index": None,
            }
        ]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 0
        assert fail == 0


class TestRetryFailedCategoriesShutdown:
    """_retry_failed_categories のシャットダウンテスト"""

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

    def test_retry_failed_categories_shutdown(self, handle):
        """シャットダウン時は処理を中断"""
        handle._db.get_failed_category_items.return_value = [
            {"url": "https://example.com/item", "name": "テスト商品", "error_id": 1}
        ]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            success, fail = amazhist.crawler._retry_failed_categories(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_categories_exception(self, handle):
        """例外発生時"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        handle._db.get_failed_category_items.return_value = [
            {"url": "https://example.com/item", "name": "テスト商品", "error_id": 1}
        ]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with (
            unittest.mock.patch(
                "amazhist.item.fetch_item_category",
                side_effect=Exception("エラー"),
            ),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            success, fail = amazhist.crawler._retry_failed_categories(handle)

        assert success == 0
        assert fail == 1


class TestRetryFailedThumbnailsShutdown:
    """_retry_failed_thumbnails のシャットダウンテスト"""

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

    def test_retry_failed_thumbnails_shutdown(self, handle):
        """シャットダウン時は処理を中断"""
        handle._db.get_failed_thumbnail_items.return_value = [
            {
                "thumb_url": "https://example.com/thumb.jpg",
                "name": "テスト",
                "asin": "B012345678",
                "error_id": 1,
            }
        ]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            success, fail = amazhist.crawler._retry_failed_thumbnails(handle)

        assert success == 0
        assert fail == 0

    def test_retry_failed_thumbnails_exception(self, handle):
        """例外発生時"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        handle._db.get_failed_thumbnail_items.return_value = [
            {
                "thumb_url": "https://example.com/thumb.jpg",
                "name": "テスト",
                "asin": "B012345678",
                "error_id": 1,
            }
        ]

        mock_progress = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_progress)

        with (
            unittest.mock.patch(
                "amazhist.item._save_thumbnail",
                side_effect=Exception("エラー"),
            ),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
        ):
            success, fail = amazhist.crawler._retry_failed_thumbnails(handle)

        assert success == 0
        assert fail == 1


class TestFetchOrderListExceptionWithShutdown:
    """fetch_order_list の例外処理（シャットダウン時）"""

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

    def test_fetch_order_list_exception_with_shutdown(self, handle):
        """シャットダウン中の例外ではダンプしない"""
        with (
            unittest.mock.patch(
                "amazhist.crawler._fetch_order_list_all_year",
                side_effect=Exception("テストエラー"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="テストエラー"),
        ):
            amazhist.crawler.fetch_order_list(handle)

        mock_dump.assert_not_called()


class TestExecuteLoginWithoutContinue:
    """_execute_login のテスト（continueボタンがない場合）"""

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

    def test_execute_login_without_continue_button(self, handle):
        """メールアドレス入力欄はあるが続行ボタンがない場合（113->117）"""
        driver, _ = handle.get_selenium_driver()

        mock_email = unittest.mock.MagicMock()
        mock_password = unittest.mock.MagicMock()
        mock_remember = unittest.mock.MagicMock()
        mock_remember.get_attribute.return_value = None
        mock_submit = unittest.mock.MagicMock()

        def find_element_side_effect(by, xpath):
            if "ap_email" in xpath:
                return mock_email
            elif "ap_password" in xpath:
                return mock_password
            elif "rememberMe" in xpath:
                return mock_remember
            elif "signInSubmit" in xpath:
                return mock_submit
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect

        def find_elements_side_effect(by, xpath):
            if 'ap_email" and @type!="hidden"' in xpath:
                return [mock_email]  # メールアドレス欄はある
            elif "continue" in xpath:
                return []  # 続行ボタンはない
            elif "ap_password" in xpath:
                return [mock_password]
            elif "rememberMe" in xpath:
                return [mock_remember]
            elif "cvf_captcha_input" in xpath:
                return []
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        with (
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
        ):
            amazhist.crawler._execute_login(handle)

        mock_email.clear.assert_called_once()
        mock_email.send_keys.assert_called_once_with("test@example.com")
        mock_password.clear.assert_called_once()
        mock_password.send_keys.assert_called_once_with("password")
        mock_submit.click.assert_called_once()


class TestRetryOrderFromListPageEdgeCases:
    """_retry_order_from_list_page のエッジケーステスト"""

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

    def test_retry_order_from_list_page_order_no_not_found(self, handle):
        """注文番号で検索時に見つからない場合（423->417）"""
        driver, _ = handle.get_selenium_driver()

        mock_order_elem = unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "order-card" in xpath and "[" not in xpath:
                return [mock_order_elem, mock_order_elem]
            elif "yohtmlc-order-id" in xpath:
                mock_no_elem = unittest.mock.MagicMock()
                mock_no_elem.text = "999-9999999-9999999"
                return [mock_no_elem]
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2025,
            "order_page": 1,
            "order_index": None,
            "order_no": "123-4567890-1234567",
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is False

    def test_retry_order_from_list_page_no_order_id_element(self, handle):
        """注文番号要素が取得できない場合（410-411）"""
        driver, _ = handle.get_selenium_driver()
        mock_order_elem = unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "order-card" in xpath and "[" not in xpath:
                return [mock_order_elem]
            elif "yohtmlc-order-id" in xpath:
                return []
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        error_info = {
            "order_year": 2025,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is False

    def test_retry_order_from_list_page_url_attr_none(self, handle):
        """詳細リンクの href が None の場合（455-459）"""
        driver, _ = handle.get_selenium_driver()

        mock_order_elem = unittest.mock.MagicMock()
        mock_order_no_elem = unittest.mock.MagicMock()
        mock_order_no_elem.text = "123-4567890-1234567"
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2025年1月1日"
        mock_details_elem = unittest.mock.MagicMock()
        mock_details_elem.get_attribute.return_value = None  # href が None

        def find_elements_side_effect(by, xpath):
            if "order-card" in xpath:
                return [mock_order_elem]  # 常に1つの注文カード
            elif "yohtmlc-order-id" in xpath:
                return [mock_order_no_elem]
            elif "order-details" in xpath:
                return [mock_details_elem]
            return []

        def find_element_side_effect(by, xpath):
            if "a-color-secondary" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        error_info = {
            "order_year": 2025,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is True

    def test_retry_order_from_list_page_no_details_link(self, handle):
        """詳細リンクがない場合（457-459）"""
        driver, _ = handle.get_selenium_driver()

        mock_order_elem = unittest.mock.MagicMock()
        mock_order_no_elem = unittest.mock.MagicMock()
        mock_order_no_elem.text = "123-4567890-1234567"
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2025年1月1日"

        def find_elements_side_effect(by, xpath):
            if "order-card" in xpath:
                return [mock_order_elem]  # 常に1つの注文カード
            elif "yohtmlc-order-id" in xpath:
                return [mock_order_no_elem]
            elif "order-details" in xpath:
                return []  # 詳細リンクがない
            return []

        def find_element_side_effect(by, xpath):
            if "a-color-secondary" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        error_info = {
            "order_year": 2025,
            "order_page": 1,
            "order_index": 0,
            "order_no": None,
        }

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("amazhist.crawler._keep_logged_on"),
            unittest.mock.patch("amazhist.crawler._wait_for_loading"),
            unittest.mock.patch("amazhist.order.parse_order", return_value=True),
        ):
            result = amazhist.crawler._retry_order_from_list_page(handle, error_info)

        assert result is True


class TestRetryFailedYearsLoopBranch:
    """_retry_failed_years のループ内分岐テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {"cache": {"order": "cache/order.db", "thumb": "thumb"}},
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {"table": "output/amazhist.xlsx", "font": {"name": "Arial", "size": 10}},
                "captcha": "captcha.png",
            },
            "login": {"amazon": {"user": "test@example.com", "pass": "password"}},
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

    def test_retry_failed_years_with_matching_error_year(self, handle):
        """エラー年が一致する場合のエラー解決（520->519）"""
        mock_error = unittest.mock.MagicMock()
        mock_error.id = 1
        mock_error.order_year = 2025

        mock_progress = unittest.mock.MagicMock()

        with (
            unittest.mock.patch.object(handle.db, "get_failed_years", return_value=[mock_error]),
            unittest.mock.patch.object(handle.db, "reset_year_status"),
            unittest.mock.patch("amazhist.crawler._fetch_order_list_by_year"),
            unittest.mock.patch.object(handle, "mark_error_resolved") as mock_resolve,
            unittest.mock.patch.object(handle, "set_progress_bar"),
            unittest.mock.patch.object(handle, "get_progress_bar", return_value=mock_progress),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_years(handle)

        assert success == 1
        assert fail == 0
        mock_resolve.assert_called_once_with(1)


class TestRetryFailedOrdersWithOrderNo:
    """_retry_failed_orders の order_no ありテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {"cache": {"order": "cache/order.db", "thumb": "thumb"}},
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {"table": "output/amazhist.xlsx", "font": {"name": "Arial", "size": 10}},
                "captcha": "captcha.png",
            },
            "login": {"amazon": {"user": "test@example.com", "pass": "password"}},
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

    def test_retry_failed_orders_with_order_no_success(self, handle):
        """order_no が存在する場合の成功時処理（631->633）"""
        error_info = {
            "error_id": 1,
            "order_no": "123-4567890-1234567",
            "order_year": 2025,
            "order_page": 1,
            "order_index": 0,
            "url": "https://example.com",
        }

        mock_progress = unittest.mock.MagicMock()

        with (
            unittest.mock.patch.object(handle.db, "get_failed_orders", return_value=[error_info]),
            unittest.mock.patch("amazhist.crawler._retry_single_order", return_value=True),
            unittest.mock.patch.object(handle, "mark_error_resolved") as mock_resolve,
            unittest.mock.patch.object(handle, "mark_errors_resolved_by_order_no") as mock_resolve_by_no,
            unittest.mock.patch.object(handle, "set_status"),
            unittest.mock.patch.object(handle, "set_progress_bar"),
            unittest.mock.patch.object(handle, "get_progress_bar", return_value=mock_progress),
            unittest.mock.patch("time.sleep"),
        ):
            success, fail = amazhist.crawler._retry_failed_orders(handle)

        assert success == 1
        assert fail == 0
        mock_resolve.assert_called_once_with(1)
        mock_resolve_by_no.assert_called_once_with("123-4567890-1234567")


class TestRetryFailedItemsExceptionWithoutShutdown:
    """retry_failed_items の例外時ダンプテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {"cache": {"order": "cache/order.db", "thumb": "thumb"}},
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {"table": "output/amazhist.xlsx", "font": {"name": "Arial", "size": 10}},
                "captcha": "captcha.png",
            },
            "login": {"amazon": {"user": "test@example.com", "pass": "password"}},
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

    def test_retry_failed_items_exception_without_shutdown(self, handle):
        """シャットダウン要求なしで例外時にダンプ（875->877）"""
        with (
            unittest.mock.patch(
                "amazhist.crawler._retry_failed_years",
                side_effect=Exception("テストエラー"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            unittest.mock.patch.object(handle, "set_status"),
            unittest.mock.patch.object(handle, "set_progress_bar"),
            pytest.raises(Exception, match="テストエラー"),
        ):
            amazhist.crawler.retry_failed_items(handle)

        mock_dump.assert_called_once()
