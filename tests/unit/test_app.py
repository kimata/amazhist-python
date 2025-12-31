#!/usr/bin/env python3
# ruff: noqa: S101
"""
app.py のテスト
"""
import unittest.mock

import pytest

import app
import amazhist.crawler
import amazhist.handle


class TestExecuteFetch:
    """execute_fetch のテスト"""

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
        # 必要なディレクトリを作成
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch("amazhist.handle._init_database"):
            h = amazhist.handle.create(mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h["selenium"] = {"driver": mock_driver, "wait": mock_wait}
            yield h
            amazhist.handle.finish(h)

    def test_execute_fetch_success(self, handle):
        """正常にフェッチ実行"""
        with unittest.mock.patch("amazhist.crawler.fetch_order_item_list") as mock_fetch:
            app.execute_fetch(handle)
            mock_fetch.assert_called_once_with(handle)

    def test_execute_fetch_error_dumps_page(self, handle):
        """エラー時にページダンプ"""
        with (
            unittest.mock.patch(
                "amazhist.crawler.fetch_order_item_list",
                side_effect=Exception("フェッチエラー"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="フェッチエラー"),
        ):
            app.execute_fetch(handle)
            mock_dump.assert_called_once()


class TestExecute:
    """execute のテスト"""

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

    def test_execute_export_mode_only(self, mock_config, tmp_path):
        """エクスポートモードのみ"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch("amazhist.handle._init_database"),
            unittest.mock.patch("amazhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("app.execute_fetch") as mock_fetch,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            app.execute(mock_config, is_export_mode=True)

            mock_fetch.assert_not_called()
            mock_excel.assert_called_once()

    def test_execute_full_mode(self, mock_config, tmp_path):
        """フルモード（フェッチ＋エクスポート）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch("amazhist.handle._init_database"),
            unittest.mock.patch("amazhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("app.execute_fetch") as mock_fetch,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            app.execute(mock_config, is_export_mode=False)

            mock_fetch.assert_called_once()
            mock_excel.assert_called_once()
