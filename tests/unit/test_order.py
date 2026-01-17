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

# NOTE: _get_caller_name のテストは crawler.py に統合されたため削除


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
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))
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

        with unittest.mock.patch("amazhist.order._parse_order_digital", return_value=True) as mock_parse:
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

        with unittest.mock.patch("amazhist.order._parse_order_default", return_value=True) as mock_parse:
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
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))
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
        # _extract_order_count_from_page で空リスト、注文カードで5件
        driver.find_elements.side_effect = [[], order_cards]

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

    def test_parse_order_count_with_page_text(self, handle):
        """ページ内テキストから注文件数を取得（line 295）"""
        driver, _ = handle.get_selenium_driver()

        # 「○件の注文」テキストがあるケース
        count_elem = unittest.mock.MagicMock()
        count_elem.text = "15件"
        driver.find_elements.return_value = [count_elem]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 15

    def test_parse_order_count_pagination(self, handle):
        """複数ページにわたる注文のカウント（lines 303-312）"""
        driver, _ = handle.get_selenium_driver()

        import amazhist.const

        # 1ページ目: ORDER_COUNT_PER_PAGE 件、2ページ目: 5件、3ページ目: 0件
        page1_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page2_cards = [unittest.mock.MagicMock() for _ in range(5)]
        page3_cards = []

        # find_elements の呼び出し:
        # 1. _extract_order_count_from_page で空リスト（num-orders要素なし）
        # 2. ORDER_XPATH でページ1のカード（10件）
        # 3. ORDER_XPATH でページ2のカード（5件）
        driver.find_elements.side_effect = [[], page1_cards, page2_cards, page3_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        # 10 + 5 = 15件
        assert result == 15

    def test_parse_order_count_pagination_full_pages(self, handle):
        """ページがちょうど終わる場合（line 307でbreak）"""
        driver, _ = handle.get_selenium_driver()

        import amazhist.const

        # 1ページ目: ORDER_COUNT_PER_PAGE件、2ページ目: 0件（空）
        page1_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page2_cards = []

        driver.find_elements.side_effect = [[], page1_cards, page2_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == amazhist.const.ORDER_COUNT_PER_PAGE

    def test_parse_order_count_pagination_multiple_full_pages(self, handle):
        """複数の満杯ページがある場合（line 312: page += 1）"""
        driver, _ = handle.get_selenium_driver()

        import amazhist.const

        # 1ページ目と2ページ目がORDER_COUNT_PER_PAGE、3ページ目は少ないか空
        page1_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page2_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page3_cards = [unittest.mock.MagicMock() for _ in range(3)]  # 3件

        # find_elements の呼び出し:
        # 1. _extract_order_count_from_page で空リスト（num-orders要素なし）
        # 2. ORDER_XPATH でページ1のカード（ORDER_COUNT_PER_PAGE件）
        # 3. ORDER_XPATH でページ2のカード（ORDER_COUNT_PER_PAGE件）
        # 4. ORDER_XPATH でページ3のカード（3件）
        driver.find_elements.side_effect = [[], page1_cards, page2_cards, page3_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        # 10 + 10 + 3 = 23件
        assert result == amazhist.const.ORDER_COUNT_PER_PAGE * 2 + 3


class TestParseOrderDigital:
    """_parse_order_digital のテスト（lines 67-119）"""

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
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_parse_order_digital_with_link(self, handle):
        """デジタル注文パース（リンクあり、lines 67-119）"""
        driver, _ = handle.get_selenium_driver()

        # デジタル注文の日付
        date_elem = unittest.mock.MagicMock()
        date_elem.text = "デジタル注文: 2024年1月15日"

        # 注文番号
        no_elem = unittest.mock.MagicMock()
        no_elem.text = "注文番号: D01-1234567-8901234"

        # 商品リンク
        link_elem = unittest.mock.MagicMock()
        link_elem.text = "Kindle本タイトル"
        link_elem.get_attribute.return_value = "https://www.amazon.co.jp/dp/B00EXAMPLE/ref=xxx"

        # 価格
        price_elem = unittest.mock.MagicMock()
        price_elem.text = "￥1,000"

        def find_element_side_effect(by, xpath):
            if "デジタル注文" in xpath and "b[contains(text()" in xpath:
                return date_elem
            elif "注文番号" in xpath:
                return no_elem
            elif "//a" in xpath and "td[1]" in xpath:
                return link_elem
            elif "/td[2]" in xpath:
                return price_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.return_value = [link_elem]  # リンクが存在

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="D01-1234567-8901234",
            url="https://www.amazon.co.jp/gp/css/summary/print.html?orderID=D01-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        with (
            unittest.mock.patch(
                "amazhist.parser.parse_date_digital", return_value=datetime.datetime(2024, 1, 15)
            ),
            unittest.mock.patch("amazhist.parser.parse_price", return_value=1000),
            unittest.mock.patch(
                "amazhist.item.fetch_item_category", return_value=["Kindleストア", "電子書籍"]
            ),
        ):
            result = amazhist.order._parse_order_digital(handle, order)

        assert result is True
        handle._db.upsert_item.assert_called_once()

    def test_parse_order_digital_without_link(self, handle):
        """デジタル注文パース（リンクなし、販売ページが存在しない場合）"""
        driver, _ = handle.get_selenium_driver()

        # デジタル注文の日付
        date_elem = unittest.mock.MagicMock()
        date_elem.text = "デジタル注文: 2024年1月15日"

        # 注文番号
        no_elem = unittest.mock.MagicMock()
        no_elem.text = "注文番号: D01-1234567-8901234"

        # 商品名（リンクなし）
        name_elem = unittest.mock.MagicMock()
        name_elem.text = "販売終了商品"

        # 価格
        price_elem = unittest.mock.MagicMock()
        price_elem.text = "￥500"

        def find_element_side_effect(by, xpath):
            if "デジタル注文" in xpath and "b[contains(text()" in xpath:
                return date_elem
            elif "注文番号" in xpath:
                return no_elem
            elif "//b" in xpath and "td[1]" in xpath:
                return name_elem
            elif "/td[2]" in xpath:
                return price_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.return_value = []  # リンクが存在しない

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="D01-1234567-8901234",
            url="https://www.amazon.co.jp/gp/css/summary/print.html?orderID=D01-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        with (
            unittest.mock.patch(
                "amazhist.parser.parse_date_digital", return_value=datetime.datetime(2024, 1, 15)
            ),
            unittest.mock.patch("amazhist.parser.parse_price", return_value=500),
        ):
            result = amazhist.order._parse_order_digital(handle, order)

        assert result is True
        handle._db.upsert_item.assert_called_once()

    def test_parse_order_digital_asin_extraction(self, handle):
        """デジタル注文でASINが正しく抽出されるか"""
        driver, _ = handle.get_selenium_driver()

        date_elem = unittest.mock.MagicMock()
        date_elem.text = "デジタル注文: 2024年1月15日"

        no_elem = unittest.mock.MagicMock()
        no_elem.text = "注文番号: D01-1234567-8901234"

        link_elem = unittest.mock.MagicMock()
        link_elem.text = "テスト商品"
        link_elem.get_attribute.return_value = "https://www.amazon.co.jp/dp/B00TESTASIN/ref=xxx"

        price_elem = unittest.mock.MagicMock()
        price_elem.text = "￥1,500"

        def find_element_side_effect(by, xpath):
            if "デジタル注文" in xpath and "b[contains(text()" in xpath:
                return date_elem
            elif "注文番号" in xpath:
                return no_elem
            elif "//a" in xpath and "td[1]" in xpath:
                return link_elem
            elif "/td[2]" in xpath:
                return price_elem
            return unittest.mock.MagicMock()

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.return_value = [link_elem]

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="D01-1234567-8901234",
            url="https://www.amazon.co.jp/gp/css/summary/print.html?orderID=D01-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        recorded_items = []

        def capture_item(item):
            recorded_items.append(item)

        handle._db.upsert_item = capture_item

        with (
            unittest.mock.patch(
                "amazhist.parser.parse_date_digital", return_value=datetime.datetime(2024, 1, 15)
            ),
            unittest.mock.patch("amazhist.parser.parse_price", return_value=1500),
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=[]),
        ):
            result = amazhist.order._parse_order_digital(handle, order)

        assert result is True
        assert len(recorded_items) == 1
        assert recorded_items[0].asin == "B00TESTASIN"


class TestParseOrderDefault:
    """_parse_order_default のテスト（lines 132-154）"""

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
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_parse_order_default_with_items(self, handle):
        """通常注文パース（商品あり、lines 132-154）"""
        driver, _ = handle.get_selenium_driver()

        # 2つの商品要素
        item_elem1 = unittest.mock.MagicMock()
        item_elem2 = unittest.mock.MagicMock()
        driver.find_elements.return_value = [item_elem1, item_elem2]

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        import amazhist.item as item_module

        mock_item1 = item_module.Item(
            name="商品1",
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            price=1000,
        )
        mock_item2 = item_module.Item(
            name="商品2",
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            price=2000,
        )

        with (
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("amazhist.item.parse_item", side_effect=[mock_item1, mock_item2]),
        ):
            result = amazhist.order._parse_order_default(handle, order)

        assert result is True
        assert handle._db.upsert_item.call_count == 2

    def test_parse_order_default_no_items(self, handle):
        """通常注文パース（商品なし）"""
        driver, _ = handle.get_selenium_driver()

        driver.find_elements.return_value = []

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        result = amazhist.order._parse_order_default(handle, order)

        assert result is False

    def test_parse_order_default_shutdown_requested(self, handle):
        """シャットダウン要求時の中断（line 139-140）"""
        driver, _ = handle.get_selenium_driver()

        item_elem1 = unittest.mock.MagicMock()
        item_elem2 = unittest.mock.MagicMock()
        driver.find_elements.return_value = [item_elem1, item_elem2]

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        # 最初の商品処理後にシャットダウン要求
        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            result = amazhist.order._parse_order_default(handle, order)

        assert result is False

    def test_parse_order_default_item_returns_none(self, handle):
        """parse_item が None を返す場合（シャットダウン中断）"""
        driver, _ = handle.get_selenium_driver()

        item_elem = unittest.mock.MagicMock()
        driver.find_elements.return_value = [item_elem]

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        with (
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("amazhist.item.parse_item", return_value=None),
        ):
            result = amazhist.order._parse_order_default(handle, order)

        assert result is False


class TestFetchItemList:
    """fetch_item_list のテスト（lines 201-235）"""

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
        (tmp_path / "debug").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_fetch_item_list_success(self, handle):
        """正常に商品情報を取得（line 235）"""
        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        mock_visit_url = unittest.mock.MagicMock()
        mock_keep_logged_on = unittest.mock.MagicMock()
        mock_get_caller_name = unittest.mock.MagicMock(return_value="test_caller")

        with unittest.mock.patch("amazhist.order.parse_order", return_value=True):
            result = amazhist.order.fetch_item_list(
                handle,
                order,
                mock_visit_url,
                mock_keep_logged_on,
                mock_get_caller_name,
            )

        assert result is True
        mock_visit_url.assert_called_once()
        mock_keep_logged_on.assert_called_once()

    def test_fetch_item_list_timeout(self, handle):
        """タイムアウト発生時（lines 206-218）"""
        from selenium.common.exceptions import TimeoutException

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        mock_visit_url = unittest.mock.MagicMock(side_effect=TimeoutException("timeout"))
        mock_keep_logged_on = unittest.mock.MagicMock()
        mock_get_caller_name = unittest.mock.MagicMock(return_value="test_caller")

        with unittest.mock.patch("time.sleep"):
            result = amazhist.order.fetch_item_list(
                handle,
                order,
                mock_visit_url,
                mock_keep_logged_on,
                mock_get_caller_name,
            )

        assert result is False
        handle._db.record_or_update_error.assert_called_once()
        # エラータイプを確認（positional args で渡される場合があるため）
        call_args = handle._db.record_or_update_error.call_args
        # args[1] が error_type の位置
        if call_args[1]:
            assert call_args[1]["error_type"] == "timeout"
        else:
            assert call_args[0][1] == "timeout"

    def test_fetch_item_list_parse_failed(self, handle):
        """パース失敗時（lines 220-233）"""
        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        mock_visit_url = unittest.mock.MagicMock()
        mock_keep_logged_on = unittest.mock.MagicMock()
        mock_get_caller_name = unittest.mock.MagicMock(return_value="test_caller")

        with (
            unittest.mock.patch("amazhist.order.parse_order", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.fetch_item_list(
                handle,
                order,
                mock_visit_url,
                mock_keep_logged_on,
                mock_get_caller_name,
            )

        assert result is False
        handle._db.record_or_update_error.assert_called_once()
        # エラータイプを確認（positional args で渡される場合があるため）
        call_args = handle._db.record_or_update_error.call_args
        if call_args[1]:
            assert call_args[1]["error_type"] == "parse_error"
        else:
            assert call_args[0][1] == "parse_error"


class TestExtractOrderCountFromPage:
    """_extract_order_count_from_page のテスト（lines 253-256）"""

    def test_extract_order_count_success(self):
        """注文件数を抽出（lines 253-256）"""
        mock_driver = unittest.mock.MagicMock()

        elem = unittest.mock.MagicMock()
        elem.text = "42件の注文"
        mock_driver.find_elements.return_value = [elem]

        result = amazhist.order._extract_order_count_from_page(mock_driver)

        assert result == 42

    def test_extract_order_count_multiple_elements(self):
        """複数の要素がある場合、最初にマッチしたものを返す"""
        mock_driver = unittest.mock.MagicMock()

        elem1 = unittest.mock.MagicMock()
        elem1.text = "テキストなし"
        elem2 = unittest.mock.MagicMock()
        elem2.text = "25件"
        mock_driver.find_elements.return_value = [elem1, elem2]

        result = amazhist.order._extract_order_count_from_page(mock_driver)

        assert result == 25

    def test_extract_order_count_no_match(self):
        """マッチする要素がない場合"""
        mock_driver = unittest.mock.MagicMock()

        elem = unittest.mock.MagicMock()
        elem.text = "件数なし"
        mock_driver.find_elements.return_value = [elem]

        result = amazhist.order._extract_order_count_from_page(mock_driver)

        assert result is None

    def test_extract_order_count_empty(self):
        """要素が空の場合"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.find_elements.return_value = []

        result = amazhist.order._extract_order_count_from_page(mock_driver)

        assert result is None
