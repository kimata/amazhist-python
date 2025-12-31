#!/usr/bin/env python3
# ruff: noqa: S101
"""
order.py のテスト
"""
import datetime
import unittest.mock

import pytest

import amazhist.config
import amazhist.handle
import amazhist.order


class TestGetCallerName:
    """_get_caller_name のテスト"""

    def test_get_caller_name(self):
        """呼び出し元の関数名を取得"""
        result = amazhist.order._get_caller_name()

        assert result == "test_get_caller_name"

    def test_get_caller_name_from_nested(self):
        """ネストした関数から呼び出した場合"""

        def inner_function():
            return amazhist.order._get_caller_name()

        result = inner_function()

        assert result == "inner_function"


class TestParseOrder:
    """parse_order のテスト"""

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

    def test_parse_order_digital(self, handle):
        """デジタル注文のパース"""
        driver, _ = handle.get_selenium_driver()

        # デジタル注文ページをシミュレート
        driver.find_elements.return_value = [unittest.mock.MagicMock()]

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="D01-1234567-8901234",
            url="https://www.amazon.co.jp/gp/css/summary/print.html?orderID=D01-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        with unittest.mock.patch(
            "amazhist.order._parse_order_digital", return_value=True
        ) as mock_parse:
            result = amazhist.order.parse_order(handle, order)

        assert result is True
        mock_parse.assert_called_once()

    def test_parse_order_default(self, handle):
        """通常注文のパース"""
        driver, _ = handle.get_selenium_driver()

        # 通常注文ページをシミュレート（デジタル注文要素なし）
        driver.find_elements.return_value = []

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        with unittest.mock.patch(
            "amazhist.order._parse_order_default", return_value=True
        ) as mock_parse:
            result = amazhist.order.parse_order(handle, order)

        assert result is True
        mock_parse.assert_called_once()


class TestParseOrderCount:
    """parse_order_count のテスト"""

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

    def test_parse_order_count_with_count_element(self, handle):
        """注文件数要素がある場合"""
        driver, _ = handle.get_selenium_driver()

        # 注文件数表示をシミュレート
        count_elem = unittest.mock.MagicMock()
        count_elem.text = "42件の注文"
        driver.find_element.return_value = count_elem

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=True),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 42

    def test_parse_order_count_without_count_element(self, handle):
        """注文件数要素がない場合（注文数が少ない）"""
        driver, _ = handle.get_selenium_driver()

        # 注文カード要素をシミュレート
        order_cards = [unittest.mock.MagicMock() for _ in range(5)]
        driver.find_elements.return_value = order_cards

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 5

    def test_parse_order_count_no_orders(self, handle):
        """注文がない場合"""
        driver, _ = handle.get_selenium_driver()
        driver.find_elements.return_value = []

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 0
