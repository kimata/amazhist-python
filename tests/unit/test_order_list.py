#!/usr/bin/env python3
# ruff: noqa: S101
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
