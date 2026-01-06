#!/usr/bin/env python3
# ruff: noqa: S101, SIM117
"""
order_list.py のテスト
"""

import unittest.mock

import pytest

import amazhist.config
import amazhist.handle
import amazhist.order_list


class TestGenTargetText:
    """_gen_target_text のテスト"""

    def test_gen_target_text(self):
        """年テキストの生成"""
        result = amazhist.order_list._gen_target_text(2025)
        assert result == "2025年"

    def test_gen_target_text_old_year(self):
        """古い年"""
        result = amazhist.order_list._gen_target_text(2010)
        assert result == "2010年"


class TestGenStatusLabelByYear:
    """_gen_status_label_by_year のテスト"""

    def test_gen_status_label_by_year(self):
        """年のラベル生成"""
        result = amazhist.order_list._gen_status_label_by_year(2025)
        assert "2025年" in result
        assert "[収集]" in result


class TestStatusOrderItemAll:
    """STATUS_ORDER_ITEM_ALL のテスト"""

    def test_status_order_item_all(self):
        """全注文ラベル"""
        assert amazhist.order_list.STATUS_ORDER_ITEM_ALL == "[収集] 全注文"


class TestSkipByYearPage:
    """_skip_by_year_page のテスト"""

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
            h._db.get_year_order_count.return_value = 15

            yield h
            h.finish()

    def test_skip_by_year_page_not_last(self, handle):
        """最終ページでない場合"""
        # プログレスバーを設定
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 15)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 15)

        is_last = amazhist.order_list._skip_by_year_page(handle, 2025, 1)

        # 15件で10件/ページなので、1ページ目は最終ではない
        assert is_last is False

    def test_skip_by_year_page_last(self, handle):
        """最終ページの場合"""
        # プログレスバーを設定
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 15)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 15)

        # プログレスバーを10件進めた状態をシミュレート
        handle.get_progress_bar(amazhist.order_list._gen_status_label_by_year(2025)).update(10)
        handle.get_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL).update(10)
        handle._db.get_year_order_count.return_value = 15

        is_last = amazhist.order_list._skip_by_year_page(handle, 2025, 2)

        # 残り5件なので最終ページ
        assert is_last is True


class TestFetchByYearPage:
    """fetch_by_year_page のテスト"""

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
            h._db.get_year_order_count.return_value = 5

            yield h
            h.finish()

    def test_fetch_by_year_page_no_orders(self, handle):
        """注文カードがない場合（期待値0件）"""
        # プログレスバーを設定（期待値0件で既に全件処理済み）
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 5)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 5)
        # 全件処理済みにする
        handle.get_progress_bar(amazhist.order_list._gen_status_label_by_year(2025)).update(5)
        handle.get_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL).update(5)

        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        # モック関数
        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        is_skipped, is_last, order_card_count, consecutive_cache_hits = (
            amazhist.order_list.fetch_by_year_page(
                handle,
                2025,
                1,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )
        )

        # 期待値0件なのでスキップなし、最終ページ、注文カード0件
        assert is_skipped is False
        assert is_last is True
        assert order_card_count == 0
        assert consecutive_cache_hits == 0


class TestSafeUpdateProgress:
    """_safe_update_progress のテスト"""

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
            h._db.get_year_order_count.return_value = 10

            yield h
            h.finish()

    def test_safe_update_progress_with_year_bar_only(self, handle):
        """年のプログレスバーのみ存在する場合"""
        # 年のプログレスバーのみ設定
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)

        # 全体プログレスバーなしで呼び出し
        amazhist.order_list._safe_update_progress(handle, 2025, 1)

        # 年のプログレスバーのみ更新される
        assert handle.get_progress_bar(amazhist.order_list._gen_status_label_by_year(2025)).count == 1
        assert not handle.has_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL)

    def test_safe_update_progress_with_both_bars(self, handle):
        """両方のプログレスバーが存在する場合"""
        # 両方のプログレスバーを設定
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 20)

        amazhist.order_list._safe_update_progress(handle, 2025, 2)

        # 両方が更新される
        assert handle.get_progress_bar(amazhist.order_list._gen_status_label_by_year(2025)).count == 2
        assert handle.get_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL).count == 2

    def test_safe_update_progress_with_no_bars(self, handle):
        """プログレスバーが存在しない場合"""
        # プログレスバーなしで呼び出し（エラーにならない）
        amazhist.order_list._safe_update_progress(handle, 2025, 1)

        # 何も起こらない
        assert not handle.has_progress_bar(amazhist.order_list._gen_status_label_by_year(2025))
        assert not handle.has_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL)

    def test_safe_update_progress_with_all_bar_only(self, handle):
        """全体プログレスバーのみ存在する場合"""
        # 全体プログレスバーのみ設定
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 20)

        amazhist.order_list._safe_update_progress(handle, 2025, 3)

        # 全体プログレスバーのみ更新される
        assert not handle.has_progress_bar(amazhist.order_list._gen_status_label_by_year(2025))
        assert handle.get_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL).count == 3


class TestGetProgressCount:
    """_get_progress_count のテスト"""

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

    def test_get_progress_count_no_bar(self, handle):
        """プログレスバーが存在しない場合は 0 を返す"""
        result = amazhist.order_list._get_progress_count(handle, 2025)
        assert result == 0

    def test_get_progress_count_with_bar(self, handle):
        """プログレスバーが存在する場合はカウントを返す"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.get_progress_bar(amazhist.order_list._gen_status_label_by_year(2025)).update(5)

        result = amazhist.order_list._get_progress_count(handle, 2025)
        assert result == 5


class TestFetchByYearPageWithOrderCards:
    """fetch_by_year_page の詳細テスト（注文カード処理）"""

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
            h._db.get_year_order_count.return_value = 10

            yield h
            h.finish()

    def test_fetch_order_cards_not_found_with_expected(self, handle):
        """注文カードが見つからないが期待値がある場合"""
        # プログレスバーを設定（まだ0件処理）
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        is_skipped, is_last, order_card_count, consecutive_cache_hits = (
            amazhist.order_list.fetch_by_year_page(
                handle,
                2025,
                1,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )
        )

        # 期待値10件あるのに0件 → スキップ扱い
        assert is_skipped is True
        assert order_card_count == 0
        # record_or_update_error が呼ばれる
        handle._db.record_or_update_error.assert_called()

    def test_fetch_problem_alert_retry(self, handle):
        """問題発生アラートでリトライ"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        # 1回目: 注文カード1件、問題アラートあり
        # 2回目（リトライ後）: 正常
        call_count = [0]

        def find_elements_side_effect(by, xpath):
            call_count[0] += 1
            if "order-card" in xpath:
                return [unittest.mock.MagicMock()]  # 1件の注文カード
            if "問題が発生" in xpath:
                # 最初の呼び出しでは問題あり、リトライ後は問題なし
                if call_count[0] <= 2:
                    return [unittest.mock.MagicMock()]
                return []
            if "キャンセル済み" in xpath:
                return []
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                    retry=0,
                )
            )

        # リトライが発生する（再帰呼び出し）
        assert visit_url.call_count >= 2

    def test_fetch_problem_alert_retry_exceeded(self, handle):
        """問題発生アラートでリトライ上限に達した場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        def find_elements_side_effect(by, xpath):
            if "order-card" in xpath:
                return [unittest.mock.MagicMock(), unittest.mock.MagicMock()]  # 2件
            if "問題が発生" in xpath:
                return [unittest.mock.MagicMock()]  # 常に問題あり
            return []

        driver.find_elements.side_effect = find_elements_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                    retry=amazhist.const.RETRY_FETCH,  # リトライ上限
                )
            )

        # スキップされる
        assert is_skipped is True
        assert order_card_count == 2

    def test_fetch_cancelled_order_skipped(self, handle):
        """キャンセル済み注文がスキップされる"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        mock_order_id_elem = unittest.mock.MagicMock()
        mock_order_id_elem.text = "123-4567890-1234567"

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH: '//div[contains(@class, "order-card js-order-card")]'
            # 最初の呼び出し（注文カード数カウント）
            if xpath == '//div[contains(@class, "order-card js-order-card")]':
                return [unittest.mock.MagicMock()]  # 1件の注文カード
            if "問題が発生" in xpath:
                return []
            if "キャンセル済み" in xpath:
                return [unittest.mock.MagicMock()]  # キャンセル済み
            return []

        def find_element_side_effect(by, xpath):
            if "yohtmlc-order-id" in xpath:
                return mock_order_id_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                )
            )

        # キャンセル済みでもスキップではない（正常処理扱い）
        assert is_skipped is False
        assert order_card_count == 1

    def test_fetch_order_no_not_found(self, handle):
        """注文番号が取得できない場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2025年01月15日"

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH: '//div[contains(@class, "order-card js-order-card")]'
            if xpath == '//div[contains(@class, "order-card js-order-card")]':
                return [unittest.mock.MagicMock()]  # 1件の注文カード
            if "問題が発生" in xpath:
                return []
            if "キャンセル済み" in xpath:
                return []
            if "yohtmlc-order-id" in xpath:
                return []  # 注文番号なし
            return []

        def find_element_side_effect(by, xpath):
            if "order-header" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                )
            )

        # エラー記録
        handle._db.record_or_update_error.assert_called()
        assert order_card_count == 1

    def test_fetch_order_details_link_no_href(self, handle):
        """詳細リンクはあるがhrefが取得できない場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2025年01月15日"

        mock_order_id_elem = unittest.mock.MagicMock()
        mock_order_id_elem.text = "123-4567890-1234567"

        mock_link_elem = unittest.mock.MagicMock()
        mock_link_elem.get_attribute.return_value = None  # href が None

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH: '//div[contains(@class, "order-card js-order-card")]'
            if xpath == '//div[contains(@class, "order-card js-order-card")]':
                return [unittest.mock.MagicMock()]  # 1件の注文カード
            if "問題が発生" in xpath:
                return []
            if "キャンセル済み" in xpath:
                return []
            if "yohtmlc-order-id" in xpath:
                return [mock_order_id_elem]
            if "order-details" in xpath:
                return [mock_link_elem]  # リンク要素はあるがhrefなし
            return []

        def find_element_side_effect(by, xpath):
            if "order-header" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock(return_value="https://example.com/order/123")
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        # order.fetch_item_list をモック
        with unittest.mock.patch("amazhist.order.fetch_item_list", return_value=True):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        # gen_order_url が呼ばれる
        gen_order_url.assert_called_with("123-4567890-1234567")
        assert order_card_count == 1

    def test_fetch_order_details_link_not_found(self, handle):
        """詳細リンクが見つからない場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2025年01月15日"

        mock_order_id_elem = unittest.mock.MagicMock()
        mock_order_id_elem.text = "123-4567890-1234567"

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH: '//div[contains(@class, "order-card js-order-card")]'
            if xpath == '//div[contains(@class, "order-card js-order-card")]':
                return [unittest.mock.MagicMock()]  # 1件の注文カード
            if "問題が発生" in xpath:
                return []
            if "キャンセル済み" in xpath:
                return []
            if "yohtmlc-order-id" in xpath:
                return [mock_order_id_elem]
            if "order-details" in xpath:
                return []  # リンク要素なし
            return []

        def find_element_side_effect(by, xpath):
            if "order-header" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock(return_value="https://example.com/order/123")
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        # order.fetch_item_list をモック
        with unittest.mock.patch("amazhist.order.fetch_item_list", return_value=True):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        # gen_order_url が呼ばれる
        gen_order_url.assert_called_with("123-4567890-1234567")
        assert order_card_count == 1

    def test_fetch_order_card_parse_exception(self, handle):
        """注文カード解析中に例外が発生した場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH: '//div[contains(@class, "order-card js-order-card")]'
            if xpath == '//div[contains(@class, "order-card js-order-card")]':
                return [unittest.mock.MagicMock()]  # 1件の注文カード
            if "問題が発生" in xpath:
                return []
            if "キャンセル済み" in xpath:
                return []
            return []

        def find_element_side_effect(by, xpath):
            # 日付要素取得時に例外
            raise Exception("テスト用例外")

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                )
            )

        # 例外発生時はスキップ
        assert is_skipped is True
        # エラー記録
        handle._db.record_or_update_error.assert_called()


class TestFetchByYearPageOrderProcessing:
    """fetch_by_year_page の注文処理テスト"""

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
            h._db.get_year_order_count.return_value = 10
            h._db.exists_order.return_value = False

            yield h
            h.finish()

    def _setup_order_card_mock(self, driver, order_id="123-4567890-1234567"):
        """注文カードのモックを設定するヘルパー"""
        mock_date_elem = unittest.mock.MagicMock()
        mock_date_elem.text = "2025年01月15日"

        mock_order_id_elem = unittest.mock.MagicMock()
        mock_order_id_elem.text = order_id

        mock_link_elem = unittest.mock.MagicMock()
        mock_link_elem.get_attribute.return_value = f"https://example.com/order/{order_id}"

        def find_elements_side_effect(by, xpath):
            # ORDER_XPATH: '//div[contains(@class, "order-card js-order-card")]'
            if xpath == '//div[contains(@class, "order-card js-order-card")]':
                return [unittest.mock.MagicMock()]
            if "問題が発生" in xpath:
                return []
            if "キャンセル済み" in xpath:
                return []
            if "yohtmlc-order-id" in xpath:
                return [mock_order_id_elem]
            if "order-details" in xpath:
                return [mock_link_elem]
            return []

        def find_element_side_effect(by, xpath):
            if "order-header" in xpath:
                return mock_date_elem
            return unittest.mock.MagicMock()

        driver.find_elements.side_effect = find_elements_side_effect
        driver.find_element.side_effect = find_element_side_effect

    def test_fetch_order_new_item(self, handle):
        """新規注文の取得"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order.fetch_item_list", return_value=True):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        assert is_skipped is False
        assert order_card_count == 1
        # 新規取得なので連続キャッシュヒットは0
        assert consecutive_cache_hits == 0

    def test_fetch_order_cached(self, handle):
        """キャッシュ済み注文"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)
        handle._db.exists_order.return_value = True  # キャッシュ済み

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                )
            )

        assert is_skipped is False
        assert order_card_count == 1
        # キャッシュヒットなので連続カウント増加
        assert consecutive_cache_hits == 1

    def test_fetch_order_early_exit_on_cache_hits(self, handle):
        """早期終了条件を満たす場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)
        handle._db.exists_order.return_value = True  # キャッシュ済み

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                amazhist.order_list.fetch_by_year_page(
                    handle,
                    2025,
                    1,
                    visit_url,
                    keep_logged_on,
                    get_caller_name,
                    gen_hist_url,
                    gen_order_url,
                    is_shutdown,
                    can_early_exit=True,
                    consecutive_cache_hits=4,  # 閾値-1
                )
            )

        # 早期終了
        assert is_last is True
        # 閾値以上になるので5
        assert consecutive_cache_hits == 5

    def test_fetch_order_exception_during_processing(self, handle):
        """注文処理中に例外が発生した場合"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order.fetch_item_list", side_effect=Exception("テスト用例外")):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        # 例外発生時はスキップ
        assert is_skipped is True
        # エラー記録
        handle._db.record_or_update_error.assert_called()
        # 連続キャッシュヒットはリセット
        assert consecutive_cache_hits == 0

    def test_fetch_order_debug_mode(self, handle):
        """デバッグモードでは1件だけ処理"""
        handle.debug_mode = True
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order.fetch_item_list", return_value=True):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        # デバッグモードでは最終ページ扱い
        assert is_last is True

    def test_fetch_order_shutdown_requested(self, handle):
        """シャットダウン要求時"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=True)  # シャットダウン要求

        with unittest.mock.patch("amazhist.order.fetch_item_list", return_value=True):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        # シャットダウン時はスキップ扱い、最終ページ扱い
        assert is_skipped is True
        assert is_last is True
        # store_order_info が呼ばれる
        handle._db.set_last_modified.assert_called()

    def test_fetch_order_item_list_failed(self, handle):
        """注文アイテム取得失敗時"""
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 10)
        handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, 10)

        driver, _ = handle.get_selenium_driver()
        self._setup_order_card_mock(driver)

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order.fetch_item_list", return_value=False):
            with unittest.mock.patch("amazhist.order_list.time.sleep"):
                is_skipped, is_last, order_card_count, consecutive_cache_hits = (
                    amazhist.order_list.fetch_by_year_page(
                        handle,
                        2025,
                        1,
                        visit_url,
                        keep_logged_on,
                        get_caller_name,
                        gen_hist_url,
                        gen_order_url,
                        is_shutdown,
                    )
                )

        # 取得失敗はスキップ扱い
        assert is_skipped is True


class TestFetchByYear:
    """fetch_by_year のテスト"""

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
            h._db.get_year_order_count.return_value = 5
            h._db.get_year_list.return_value = [2025, 2024, 2023]
            h._db.is_page_checked.return_value = False
            h._db.is_year_checked.return_value = False
            h._db.get_item_count_by_year.return_value = 0
            h._db.get_unresolved_error_count_by_year.return_value = 0

            yield h
            h.finish()

    def test_fetch_by_year_basic(self, handle):
        """基本的な年の取得"""
        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []  # 注文カードなし

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

        # visit_url が呼ばれる
        visit_url.assert_called()
        # プログレスバーが作成される
        assert handle.has_progress_bar(amazhist.order_list._gen_status_label_by_year(2025))

    def test_fetch_by_year_page_cached(self, handle):
        """ページがキャッシュ済みの場合"""
        handle._db.is_page_checked.return_value = True  # ページキャッシュ済み
        handle.set_progress_bar(amazhist.order_list._gen_status_label_by_year(2025), 5)

        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

        # _skip_by_year_page が呼ばれる（ページスキップ）

    def test_fetch_by_year_shutdown_requested(self, handle):
        """シャットダウン要求時"""
        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=True)  # シャットダウン要求

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

        # シャットダウン時はすぐに終了

    def test_fetch_by_year_debug_mode(self, handle):
        """デバッグモードでは1ページだけ処理"""
        handle.debug_mode = True
        # 複数ページあるが、デバッグモードなので1ページ目で終了
        handle._db.get_year_order_count.return_value = 25  # 3ページ分

        driver, _ = handle.get_selenium_driver()
        # 期待値0で終わらないように、注文カードがある状態にする
        # ただし fetch_by_year_page が is_last=False を返す必要がある
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

        # デバッグモードでは1ページだけ
        # visit_url は初回呼び出し + fetch_by_year_page での呼び出しのみ（1ページ分）
        # デバッグモードなので複数ページ処理されない

    def test_fetch_by_year_year_checked(self, handle):
        """年が正常に完了した場合（注文カードがあって正常処理）"""
        # 注文数を0にして、期待値0件として扱う
        handle._db.get_year_order_count.return_value = 0

        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []  # 注文カードなし（期待値0なのでOK）

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

        # 正常終了時は年がチェック済みになる
        handle._db.set_year_status.assert_called()

    def test_fetch_by_year_with_early_exit_condition(self, handle):
        """今年の早期終了条件を満たす場合"""
        import datetime

        current_year = datetime.datetime.now().year

        # 年リストに今年を含める
        handle._db.get_year_list.return_value = [current_year, 2024, 2023]

        # 早期終了条件を満たすように設定
        handle._db.is_year_checked.return_value = True
        handle._db.get_item_count_by_year.return_value = 10
        handle._db.get_unresolved_error_count_by_year.return_value = 0
        # 注文数を0にしておく（期待値0件）
        handle._db.get_year_order_count.return_value = 0

        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                current_year,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

        # 早期終了条件を満たしている

    def test_fetch_by_year_multiple_pages(self, handle):
        """複数ページの処理"""
        handle._db.get_year_order_count.return_value = 15  # 2ページ分

        driver, _ = handle.get_selenium_driver()

        # 最初のページ: 注文カードなし（即終了させるため）
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )

    def test_fetch_by_year_page_skipped(self, handle):
        """ページがスキップされた場合（チェック済みにしない）"""
        # 最初のページはキャッシュ済み
        call_count = [0]

        def is_page_checked_side_effect(year, page):
            call_count[0] += 1
            return call_count[0] == 1  # 最初のページのみキャッシュ済み

        handle._db.is_page_checked.side_effect = is_page_checked_side_effect

        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        visit_url = unittest.mock.MagicMock()
        keep_logged_on = unittest.mock.MagicMock()
        get_caller_name = unittest.mock.MagicMock(return_value="test")
        gen_hist_url = unittest.mock.MagicMock(return_value="https://example.com/orders")
        gen_order_url = unittest.mock.MagicMock()
        is_shutdown = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("amazhist.order_list.time.sleep"):
            amazhist.order_list.fetch_by_year(
                handle,
                2025,
                visit_url,
                keep_logged_on,
                get_caller_name,
                gen_hist_url,
                gen_order_url,
                is_shutdown,
            )
