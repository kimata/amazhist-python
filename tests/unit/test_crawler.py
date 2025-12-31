#!/usr/bin/env python3
# ruff: noqa: S101
"""
crawler.py のテスト
"""
import unittest.mock

import pytest

import amazhist.crawler


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


class TestFetchOrderItemList:
    """fetch_order_item_list のテスト"""

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
        import amazhist.handle

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch("amazhist.handle._init_database"):
            h = amazhist.handle.create(mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h["selenium"] = {"driver": mock_driver, "wait": mock_wait}
            yield h
            amazhist.handle.finish(h)

    def test_fetch_order_item_list_shutdown_requested(self, handle):
        """シャットダウンリクエスト時は即座に終了"""
        with (
            unittest.mock.patch(
                "amazhist.crawler._fetch_order_item_list_all_year"
            ) as mock_fetch,
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
        ):
            amazhist.crawler.fetch_order_item_list(handle)

            # シャットダウンリクエスト時もフェッチは呼ばれる
            mock_fetch.assert_called_once()
