#!/usr/bin/env python3
# ruff: noqa: S101
"""
item.py のテスト

ブラウザ層は my_lib.browser の Page 抽象を使用する。
Page / Element のモックは conftest の build_page / build_element ヘルパー
（make_page / make_element フィクスチャ）で組み立て、browser_mocks で Handle に
取り付ける。サムネイル取得・カテゴリ取得は browser_manager.get_browser().tab(url)
の context manager（handle._test_tab）上で操作する。
"""

import unittest.mock

import my_lib.graceful_shutdown
import pytest

import amazhist.config
import amazhist.exceptions
import amazhist.handle
import amazhist.item

_MOCK_CONFIG = {
    "base_dir": None,  # tmp_path で上書き
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


def _make_config(tmp_path):
    config = dict(_MOCK_CONFIG)
    config["base_dir"] = str(tmp_path)
    return config


class TestFetchItemCategory:
    """fetch_item_category のテスト"""

    @pytest.fixture
    def handle(self, tmp_path, browser_mocks):
        """Handle インスタンス（ブラウザモック取り付け済み）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(_make_config(tmp_path)))
            browser_mocks(h)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_fetch_item_category_shutdown(self, handle):
        """シャットダウン時は空リストを返す"""
        my_lib.graceful_shutdown.request_shutdown()

        result = amazhist.item.fetch_item_category(handle, "https://example.com/item")

        assert result == []
        my_lib.graceful_shutdown.reset_shutdown_flag()

    def test_fetch_item_category_success(self, handle, make_element):
        """カテゴリ取得成功（タブ上のパンくずリストを取得）"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        # パンくずリスト要素をシミュレート（tab.find_all の返り値）
        category_elements = [make_element(text=cat) for cat in ["本", "コンピュータ・IT", "プログラミング"]]
        handle._test_tab.find_all.return_value = category_elements

        result = amazhist.item.fetch_item_category(handle, "https://example.com/item")

        assert result == ["本", "コンピュータ・IT", "プログラミング"]

    def test_fetch_item_category_error(self, handle):
        """カテゴリ取得失敗時はエラー記録"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        with unittest.mock.patch(
            "amazhist.webutil.with_retry",
            side_effect=Exception("リトライ失敗"),
        ):
            result = amazhist.item.fetch_item_category(handle, "https://example.com/item")

        assert result == []
        handle._db.record_error.assert_called_once()

    def test_fetch_item_category_no_error_record(self, handle):
        """record_error=False の場合はエラー記録しない"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        with unittest.mock.patch(
            "amazhist.webutil.with_retry",
            side_effect=Exception("リトライ失敗"),
        ):
            result = amazhist.item.fetch_item_category(handle, "https://example.com/item", record_error=False)

        assert result == []
        handle._db.record_error.assert_not_called()


class TestSaveThumbnail:
    """_save_thumbnail のテスト"""

    @pytest.fixture
    def handle(self, tmp_path, browser_mocks):
        """Handle インスタンス（ブラウザモック取り付け済み）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(_make_config(tmp_path)))
            browser_mocks(h)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_save_thumbnail_shutdown(self, handle):
        """シャットダウン時は何もしない"""
        my_lib.graceful_shutdown.request_shutdown()

        amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

        # タブを開いていないことを確認
        handle._test_browser_manager.get_browser.assert_not_called()
        my_lib.graceful_shutdown.reset_shutdown_flag()

    def test_save_thumbnail_no_asin(self, handle):
        """ASIN がない場合は何もしない"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        amazhist.item._save_thumbnail(handle, None, "https://example.com/thumb.jpg")

        # タブを開いていないことを確認
        handle._test_browser_manager.get_browser.assert_not_called()

    def test_save_thumbnail_success(self, handle, tmp_path, make_element):
        """サムネイル保存成功"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        # タブ上の画像要素をシミュレート
        handle._test_tab.find.return_value = make_element(screenshot=b"fake_png_data")

        with unittest.mock.patch("PIL.Image.open"):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

        # ファイルが作成されたことを確認
        thumb_path = tmp_path / "thumb" / "B012345678.png"
        assert thumb_path.exists()
        assert thumb_path.read_bytes() == b"fake_png_data"


class TestParseItem:
    """parse_item のテスト"""

    @pytest.fixture
    def handle(self, tmp_path, browser_mocks):
        """Handle インスタンス（ブラウザモック取り付け済み）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(_make_config(tmp_path)))
            browser_mocks(h)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_parse_item_shutdown(self, handle):
        """シャットダウン時は None を返す"""
        import datetime

        import amazhist.order

        my_lib.graceful_shutdown.request_shutdown()

        order = amazhist.order.Order(
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/order/ORDER-001",
        )
        result = amazhist.item.parse_item(handle, "//div[@data-component='purchasedItems']", order)

        assert result is None
        my_lib.graceful_shutdown.reset_shutdown_flag()

    def test_parse_item_success(self, handle, make_element, by_value):
        """商品パース成功"""
        import datetime

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        page = handle._test_page

        link = make_element(text="テスト商品", href="https://www.amazon.co.jp/dp/B012345678")
        thumb = make_element(attrs={"src": "https://example.com/thumb.jpg"})
        # a-offscreen の価格は textContent（evaluate）で取得する
        price = make_element(evaluate="¥1,234")
        seller = make_element(text="テスト販売者")

        def find_by_value(value):
            if "itemTitle" in value:
                return link
            if "itemImage" in value:
                return thumb
            return None

        def find_all_by_value(value):
            if "unitPrice" in value:
                return [price]
            if "orderedMerchant" in value:
                return [seller]
            return []

        page.find.side_effect = by_value(find_by_value)
        page.find_all.side_effect = by_value(find_all_by_value)

        order = amazhist.order.Order(
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/order/ORDER-001",
            time_filter=2025,
            page=1,
        )

        with (
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=["本"]),
            unittest.mock.patch("amazhist.webutil.with_retry"),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.name == "テスト商品"
        assert result.asin == "B012345678"
        assert result.price == 1234
        assert result.seller == "テスト販売者"
        assert result.kind == "Normal"


class TestItemDataclass:
    """Item dataclass のテスト"""

    def test_item_getitem(self):
        """辞書風アクセスのテスト"""
        import datetime

        item = amazhist.item.Item(
            name="テスト商品",
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            price=1234,
        )

        assert item["name"] == "テスト商品"
        assert item["no"] == "ORDER-001"
        assert item["price"] == 1234

    def test_item_contains_with_string_key(self):
        """文字列キーでの存在確認"""
        import datetime

        item = amazhist.item.Item(
            name="テスト商品",
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
        )

        assert "name" in item
        assert "date" in item
        assert "nonexistent" not in item

    def test_item_contains_with_non_string_key(self):
        """非文字列キーでの存在確認（False を返す）"""
        import datetime

        item = amazhist.item.Item(
            name="テスト商品",
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
        )

        # 非文字列キーは False を返す
        assert (123 in item) is False
        assert (None in item) is False
        assert (["name"] in item) is False

    def test_item_to_dict(self):
        """辞書変換のテスト"""
        import datetime

        item = amazhist.item.Item(
            name="テスト商品",
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/dp/B012345678",
            asin="B012345678",
            count=2,
            price=1234,
            category=("本", "コンピュータ"),
            seller="テスト販売者",
            condition="新品",
            kind="Normal",
        )

        result = item.to_dict()

        assert isinstance(result, dict)
        assert result["name"] == "テスト商品"
        assert result["no"] == "ORDER-001"
        assert result["price"] == 1234
        # tuple が list に変換されていることを確認
        assert isinstance(result["category"], list)
        assert result["category"] == ["本", "コンピュータ"]


class TestSaveThumbnailErrors:
    """_save_thumbnail のエラーケースのテスト"""

    @pytest.fixture
    def handle(self, tmp_path, browser_mocks):
        """Handle インスタンス（ブラウザモック取り付け済み）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(_make_config(tmp_path)))
            browser_mocks(h)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_save_thumbnail_empty_data(self, handle, make_element):
        """画像データが空の場合はエラーを発生"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        # 空の画像データをシミュレート
        handle._test_tab.find.return_value = make_element(screenshot=b"")

        with pytest.raises(amazhist.exceptions.ThumbnailEmptyError):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

    def test_save_thumbnail_zero_size_file(self, handle, tmp_path, make_element):
        """ファイルサイズが0の場合はエラーを発生"""
        import os
        import pathlib

        my_lib.graceful_shutdown.reset_shutdown_flag()

        # 非空のデータだがファイルに書き込むと0サイズになるケースをシミュレート
        handle._test_tab.find.return_value = make_element(screenshot=b"fake_data")

        # stat_result のモック（0サイズを返す）
        mock_stat_result = os.stat_result((0o100644, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        with (
            unittest.mock.patch.object(pathlib.Path, "stat", return_value=mock_stat_result),
            pytest.raises(amazhist.exceptions.ThumbnailSizeError),
        ):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

    def test_save_thumbnail_corrupted_image(self, handle, tmp_path, make_element):
        """画像が破損している場合はエラーを発生"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        # 有効でない画像データをシミュレート
        handle._test_tab.find.return_value = make_element(screenshot=b"not_a_real_png_image_data")

        with (
            unittest.mock.patch("PIL.Image.open", side_effect=Exception("破損した画像")),
            pytest.raises(amazhist.exceptions.ThumbnailCorruptError),
        ):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")


class TestParseItemErrors:
    """parse_item のエラーケースのテスト"""

    @pytest.fixture
    def handle(self, tmp_path, browser_mocks):
        """Handle インスタンス（ブラウザモック取り付け済み）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)
        (tmp_path / "debug").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(_make_config(tmp_path)))
            browser_mocks(h)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_parse_item_thumbnail_fetch_failure(self, handle, make_element, by_value):
        """サムネイル取得失敗時はエラーを記録"""
        import datetime

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        page = handle._test_page

        link = make_element(text="テスト商品", href="https://www.amazon.co.jp/dp/B012345678")
        thumb = make_element(attrs={"src": "https://example.com/thumb.jpg"})
        price = make_element(evaluate="¥1,234")
        seller = make_element(text="テスト販売者")

        def find_by_value(value):
            if "itemTitle" in value:
                return link
            if "itemImage" in value:
                return thumb
            return None

        def find_all_by_value(value):
            if "unitPrice" in value:
                return [price]
            if "orderedMerchant" in value:
                return [seller]
            return []

        page.find.side_effect = by_value(find_by_value)
        page.find_all.side_effect = by_value(find_all_by_value)

        order = amazhist.order.Order(
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/order/ORDER-001",
            time_filter=2025,
            page=1,
        )

        # サムネイル取得失敗をシミュレート
        with (
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=["本"]),
            unittest.mock.patch(
                "amazhist.webutil.with_retry",
                side_effect=Exception("サムネイル取得失敗"),
            ),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.name == "テスト商品"
        # エラーが記録されていることを確認
        handle._db.record_error.assert_called_once()

    def test_parse_item_price_parse_failure(self, handle, make_element, by_value):
        """価格パース失敗時はエラーを記録"""
        import datetime

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        page = handle._test_page

        link = make_element(text="テスト商品", href="https://www.amazon.co.jp/dp/B012345678")
        thumb = make_element(attrs={"src": None})  # サムネイルなし
        price = make_element(evaluate="無料")  # パースできない価格
        seller = make_element(text="テスト販売者")

        def find_by_value(value):
            if "itemTitle" in value:
                return link
            if "itemImage" in value:
                return thumb
            return None

        def find_all_by_value(value):
            if "unitPrice" in value:
                return [price]
            if "orderedMerchant" in value:
                return [seller]
            return []

        page.find.side_effect = by_value(find_by_value)
        page.find_all.side_effect = by_value(find_all_by_value)

        order = amazhist.order.Order(
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/order/ORDER-001",
            time_filter=2025,
            page=1,
        )

        with (
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=["本"]),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("my_lib.browser.helpers.dump_page"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.price == 0  # パース失敗時は 0
        # エラーが記録されていることを確認
        handle._db.record_or_update_error.assert_called_once()

    def test_parse_item_price_not_found(self, handle, make_element, by_value):
        """価格要素が見つからない場合はエラーを記録"""
        import datetime

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        page = handle._test_page

        link = make_element(text="テスト商品", href="https://www.amazon.co.jp/dp/B012345678")
        thumb = make_element(attrs={"src": None})  # サムネイルなし
        seller = make_element(text="テスト販売者")

        def find_by_value(value):
            if "itemTitle" in value:
                return link
            if "itemImage" in value:
                return thumb
            return None

        def find_all_by_value(value):
            if "unitPrice" in value:
                return []  # 価格要素なし
            if "orderedMerchant" in value:
                return [seller]
            return []

        page.find.side_effect = by_value(find_by_value)
        page.find_all.side_effect = by_value(find_all_by_value)

        order = amazhist.order.Order(
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/order/ORDER-001",
            time_filter=2025,
            page=1,
        )

        with (
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=["本"]),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("my_lib.browser.helpers.dump_page"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.price == 0  # 価格なしの場合は 0
        # エラーが記録されていることを確認
        handle._db.record_or_update_error.assert_called_once()
