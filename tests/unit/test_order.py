#!/usr/bin/env python3
# ruff: noqa: S101
"""
order.py のテスト

ブラウザ層は my_lib.browser の Page 抽象を使用する。
Page / Element のモックは conftest の build_page / build_element ヘルパー
（make_page / make_element フィクスチャ）で組み立てる。
"""

import datetime
import unittest.mock

import my_lib.browser
import pytest

import amazhist.config
import amazhist.const
import amazhist.handle
import amazhist.order

# NOTE: _get_caller_name のテストは crawler.py に統合されたため削除


@pytest.fixture
def mock_config(tmp_path):
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
def handle(mock_config, tmp_path, browser_mocks):
    """ブラウザモックを取り付けた Handle インスタンス"""
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

    with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
        h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
        browser_mocks(h)
        h._db = unittest.mock.MagicMock()
        yield h
        h.finish()


class TestParseOrder:
    """parse_order のテスト"""

    def test_parse_order_digital(self, handle):
        """デジタル注文のパース"""
        # デジタル注文要素が存在する
        handle._test_page.exists.return_value = True

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
        # デジタル注文要素なし
        handle._test_page.exists.return_value = False

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

    def test_parse_order_count_with_count_element(self, handle, make_element):
        """注文件数要素がある場合"""
        page = handle._test_page

        # 注文件数表示をシミュレート（num-orders 要素あり）
        page.exists.return_value = True
        page.find.return_value = make_element(text="42件の注文")

        with unittest.mock.patch("amazhist.crawler.visit_url"):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 42

    def test_parse_order_count_with_comma(self, handle, make_element):
        """注文件数がカンマ区切りの場合（1,234件 → 1234）"""
        page = handle._test_page

        page.exists.return_value = True
        page.find.return_value = make_element(text="1,234件の注文")

        with unittest.mock.patch("amazhist.crawler.visit_url"):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 1234

    def test_parse_order_count_without_count_element(self, handle):
        """注文件数要素がない場合（注文数が少ない）"""
        page = handle._test_page

        # 注文カード要素をシミュレート
        order_cards = [unittest.mock.MagicMock() for _ in range(5)]
        # num-orders 要素なし → False、ORDER_XPATH あり → True
        page.exists.side_effect = [False, True]
        # _extract_order_count_from_page で空リスト、ORDER_XPATH で5件
        page.find_all.side_effect = [[], order_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 5

    def test_parse_order_count_no_orders(self, handle):
        """注文がない場合"""
        page = handle._test_page
        page.exists.return_value = False
        page.find_all.return_value = []

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 0

    def test_parse_order_count_with_page_text(self, handle, make_element):
        """ページ内テキストから注文件数を取得"""
        page = handle._test_page

        # 「○件の注文」テキストがあるケース
        page.exists.side_effect = [False, True]
        page.find_all.return_value = [make_element(text="15件")]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == 15

    def test_parse_order_count_pagination(self, handle):
        """複数ページにわたる注文のカウント"""
        page = handle._test_page

        # 1ページ目: ORDER_COUNT_PER_PAGE 件、2ページ目: 5件、3ページ目: 0件
        page1_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page2_cards = [unittest.mock.MagicMock() for _ in range(5)]
        page3_cards = []

        # find_all の呼び出し:
        # 1. _extract_order_count_from_page で空リスト（num-orders要素なし）
        # 2. ORDER_XPATH でページ1のカード（10件）
        # 3. ORDER_XPATH でページ2のカード（5件）
        page.exists.side_effect = [False, True]
        page.find_all.side_effect = [[], page1_cards, page2_cards, page3_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        # 10 + 5 = 15件
        assert result == 15

    def test_parse_order_count_pagination_full_pages(self, handle):
        """ページがちょうど終わる場合"""
        page = handle._test_page

        # 1ページ目: ORDER_COUNT_PER_PAGE件、2ページ目: 0件（空）
        page1_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page2_cards = []

        page.exists.side_effect = [False, True]
        page.find_all.side_effect = [[], page1_cards, page2_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        assert result == amazhist.const.ORDER_COUNT_PER_PAGE

    def test_parse_order_count_pagination_multiple_full_pages(self, handle):
        """複数の満杯ページがある場合"""
        page = handle._test_page

        # 1ページ目と2ページ目がORDER_COUNT_PER_PAGE、3ページ目は少ない
        page1_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page2_cards = [unittest.mock.MagicMock() for _ in range(amazhist.const.ORDER_COUNT_PER_PAGE)]
        page3_cards = [unittest.mock.MagicMock() for _ in range(3)]  # 3件

        page.exists.side_effect = [False, True]
        page.find_all.side_effect = [[], page1_cards, page2_cards, page3_cards]

        with (
            unittest.mock.patch("amazhist.crawler.visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.order.parse_order_count(handle, 2024)

        # 10 + 10 + 3 = 23件
        assert result == amazhist.const.ORDER_COUNT_PER_PAGE * 2 + 3


class TestParseOrderDigital:
    """_parse_order_digital のテスト"""

    @staticmethod
    def _digital_finder(make_element, *, link=None, name=None):
        """デジタル注文ページの find（単一要素）side_effect を組み立てる。"""
        date_elem = make_element(text="デジタル注文: 2024年1月15日")
        no_elem = make_element(text="注文番号: D01-1234567-8901234")
        price_elem = make_element(text="￥1,000")

        def find_by_value(value):
            if "デジタル注文" in value:
                return date_elem
            if "注文番号" in value:
                return no_elem
            if "/td[1]//a" in value:
                return link
            if "/td[1]//b" in value:
                return name
            if "/td[2]" in value:
                return price_elem
            return None

        return find_by_value

    def test_parse_order_digital_with_link(self, handle, make_element, by_value):
        """デジタル注文パース（リンクあり）"""
        page = handle._test_page

        link_elem = make_element(
            text="Kindle本タイトル",
            href="https://www.amazon.co.jp/dp/B00EXAMPLE/ref=xxx",
        )

        page.exists.return_value = True  # 商品リンクが存在
        page.find.side_effect = by_value(self._digital_finder(make_element, link=link_elem))

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

    def test_parse_order_digital_without_link(self, handle, make_element, by_value):
        """デジタル注文パース（リンクなし、販売ページが存在しない場合）"""
        page = handle._test_page

        name_elem = make_element(text="販売終了商品")

        page.exists.return_value = False  # 商品リンクが存在しない
        page.find.side_effect = by_value(self._digital_finder(make_element, name=name_elem))

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

    def test_parse_order_digital_asin_extraction(self, handle, make_element, by_value):
        """デジタル注文でASINが正しく抽出されるか"""
        page = handle._test_page

        link_elem = make_element(
            text="テスト商品",
            href="https://www.amazon.co.jp/dp/B00TESTASIN/ref=xxx",
        )

        page.exists.return_value = True
        page.find.side_effect = by_value(self._digital_finder(make_element, link=link_elem))

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
    """_parse_order_default のテスト"""

    def test_parse_order_default_with_items(self, handle):
        """通常注文パース（商品あり）"""
        # 2つの商品要素
        handle._test_page.find_all.return_value = [
            unittest.mock.MagicMock(),
            unittest.mock.MagicMock(),
        ]

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
        handle._test_page.find_all.return_value = []

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
        """シャットダウン要求時の中断"""
        handle._test_page.find_all.return_value = [
            unittest.mock.MagicMock(),
            unittest.mock.MagicMock(),
        ]

        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        # 最初の商品処理前にシャットダウン要求
        with unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True):
            result = amazhist.order._parse_order_default(handle, order)

        assert result is False

    def test_parse_order_default_item_returns_none(self, handle):
        """parse_item が None を返す場合（シャットダウン中断）"""
        handle._test_page.find_all.return_value = [unittest.mock.MagicMock()]

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
    """fetch_item_list のテスト"""

    def test_fetch_item_list_success(self, handle):
        """正常に商品情報を取得"""
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
        """ページ遷移失敗（NavigationError）時"""
        order = amazhist.order.Order(
            date=datetime.datetime(2024, 1, 15),
            no="503-1234567-8901234",
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
            time_filter=2024,
            page=1,
        )

        mock_visit_url = unittest.mock.MagicMock(side_effect=my_lib.browser.NavigationError("timeout"))
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
        if call_args[1]:
            assert call_args[1]["error_type"] == "timeout"
        else:
            assert call_args[0][1] == "timeout"

    def test_fetch_item_list_parse_failed(self, handle):
        """パース失敗時"""
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
            unittest.mock.patch("my_lib.browser.helpers.dump_page"),
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
    """_extract_order_count_from_page のテスト"""

    def test_extract_order_count_success(self, make_page, make_element):
        """注文件数を抽出"""
        page = make_page()
        page.find_all.return_value = [make_element(text="42件の注文")]

        result = amazhist.order._extract_order_count_from_page(page)

        assert result == 42

    def test_extract_order_count_multiple_elements(self, make_page, make_element):
        """複数の要素がある場合、最初にマッチしたものを返す"""
        page = make_page()
        page.find_all.return_value = [
            make_element(text="テキストなし"),
            make_element(text="25件"),
        ]

        result = amazhist.order._extract_order_count_from_page(page)

        assert result == 25

    def test_extract_order_count_with_comma(self, make_page, make_element):
        """カンマ区切りの件数（1,234件 → 1234）"""
        page = make_page()
        page.find_all.return_value = [make_element(text="1,234件")]

        result = amazhist.order._extract_order_count_from_page(page)

        assert result == 1234

    def test_extract_order_count_no_match(self, make_page, make_element):
        """マッチする要素がない場合"""
        page = make_page()
        page.find_all.return_value = [make_element(text="件数なし")]

        result = amazhist.order._extract_order_count_from_page(page)

        assert result is None

    def test_extract_order_count_empty(self, make_page):
        """要素が空の場合"""
        page = make_page()
        page.find_all.return_value = []

        result = amazhist.order._extract_order_count_from_page(page)

        assert result is None
