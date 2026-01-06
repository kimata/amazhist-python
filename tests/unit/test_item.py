#!/usr/bin/env python3
# ruff: noqa: S101
"""
item.py のテスト
"""

import unittest.mock

import my_lib.graceful_shutdown
import pytest

import amazhist.config
import amazhist.crawler
import amazhist.handle
import amazhist.item


class TestFetchItemCategory:
    """fetch_item_category のテスト"""

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

    def test_fetch_item_category_shutdown(self, handle):
        """シャットダウン時は空リストを返す"""
        my_lib.graceful_shutdown.request_shutdown()

        result = amazhist.item.fetch_item_category(handle, "https://example.com/item")

        assert result == []
        my_lib.graceful_shutdown.reset_shutdown_flag()

    def test_fetch_item_category_success(self, handle):
        """カテゴリ取得成功"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # パンくずリスト要素をシミュレート
        category_elements = []
        for cat in ["本", "コンピュータ・IT", "プログラミング"]:
            elem = unittest.mock.MagicMock()
            elem.text = cat
            category_elements.append(elem)

        driver.find_elements.return_value = category_elements

        with unittest.mock.patch("my_lib.selenium_util.browser_tab"):
            result = amazhist.item.fetch_item_category(handle, "https://example.com/item")

        assert result == ["本", "コンピュータ・IT", "プログラミング"]

    def test_fetch_item_category_error(self, handle):
        """カテゴリ取得失敗時はエラー記録"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        _driver, _ = handle.get_selenium_driver()

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.browser_tab",
                side_effect=Exception("ページ読み込みエラー"),
            ),
            unittest.mock.patch("my_lib.selenium_util.with_retry", side_effect=Exception("リトライ失敗")),
        ):
            result = amazhist.item.fetch_item_category(handle, "https://example.com/item")

        assert result == []
        handle._db.record_error.assert_called_once()

    def test_fetch_item_category_no_error_record(self, handle):
        """record_error=False の場合はエラー記録しない"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        with unittest.mock.patch(
            "my_lib.selenium_util.with_retry",
            side_effect=Exception("リトライ失敗"),
        ):
            result = amazhist.item.fetch_item_category(handle, "https://example.com/item", record_error=False)

        assert result == []
        handle._db.record_error.assert_not_called()


class TestSaveThumbnail:
    """_save_thumbnail のテスト"""

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
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_save_thumbnail_shutdown(self, handle):
        """シャットダウン時は何もしない"""
        my_lib.graceful_shutdown.request_shutdown()

        amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

        # driver.get が呼ばれていないことを確認
        driver, _ = handle.get_selenium_driver()
        driver.get.assert_not_called()
        my_lib.graceful_shutdown.reset_shutdown_flag()

    def test_save_thumbnail_no_asin(self, handle):
        """ASIN がない場合は何もしない"""
        my_lib.graceful_shutdown.reset_shutdown_flag()

        amazhist.item._save_thumbnail(handle, None, "https://example.com/thumb.jpg")

        # driver.get が呼ばれていないことを確認
        driver, _ = handle.get_selenium_driver()
        driver.get.assert_not_called()

    def test_save_thumbnail_success(self, handle, tmp_path):
        """サムネイル保存成功"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 画像要素をシミュレート
        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b"fake_png_data"
        driver.find_element.return_value = mock_img

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("PIL.Image.open"),
        ):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

        # ファイルが作成されたことを確認
        thumb_path = tmp_path / "thumb" / "B012345678.png"
        assert thumb_path.exists()
        assert thumb_path.read_bytes() == b"fake_png_data"


class TestParseItem:
    """parse_item のテスト"""

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
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
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

    def test_parse_item_success(self, handle):
        """商品パース成功"""
        import datetime

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 商品リンク要素をシミュレート
        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://www.amazon.co.jp/dp/B012345678"

        # 価格要素をシミュレート
        mock_price = unittest.mock.MagicMock()
        mock_price.get_attribute.return_value = "¥1,234"

        # サムネイル要素をシミュレート
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = "https://example.com/thumb.jpg"

        # 販売者要素をシミュレート
        mock_seller = unittest.mock.MagicMock()
        mock_seller.text = "テスト販売者"

        def find_element_side_effect(by, xpath):
            if "itemTitle" in xpath:
                return mock_link
            elif "itemImage" in xpath:
                return mock_thumb
            return unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "unitPrice" in xpath:
                return [mock_price]
            elif "orderedMerchant" in xpath:
                return [mock_seller]
            return []

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.side_effect = find_elements_side_effect

        order = amazhist.order.Order(
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/order/ORDER-001",
            time_filter=2025,
            page=1,
        )

        with (
            unittest.mock.patch("amazhist.item.fetch_item_category", return_value=["本"]),
            unittest.mock.patch("my_lib.selenium_util.with_retry"),
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
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_save_thumbnail_empty_data(self, handle):
        """画像データが空の場合はエラーを発生"""
        import my_lib.graceful_shutdown

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 空の画像データをシミュレート
        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b""  # 空のデータ
        driver.find_element.return_value = mock_img

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            pytest.raises(RuntimeError, match="サムネイル画像データが空です"),
        ):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

    def test_save_thumbnail_zero_size_file(self, handle, tmp_path):
        """ファイルサイズが0の場合はエラーを発生"""
        import os

        import my_lib.graceful_shutdown

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 非空のデータだがファイルに書き込むと0サイズになるケースをシミュレート
        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b"fake_data"
        driver.find_element.return_value = mock_img

        # stat_result のモック（0サイズを返す）
        mock_stat_result = os.stat_result((0o100644, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("pathlib.Path.stat", return_value=mock_stat_result),
            pytest.raises(RuntimeError, match="サムネイル画像のサイズが0です"),
        ):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")

    def test_save_thumbnail_corrupted_image(self, handle, tmp_path):
        """画像が破損している場合はエラーを発生"""
        import my_lib.graceful_shutdown

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 有効でない画像データをシミュレート
        mock_img = unittest.mock.MagicMock()
        mock_img.screenshot_as_png = b"not_a_real_png_image_data"
        driver.find_element.return_value = mock_img

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("PIL.Image.open", side_effect=Exception("破損した画像")),
            pytest.raises(RuntimeError, match="サムネイル画像が破損しています"),
        ):
            amazhist.item._save_thumbnail(handle, "B012345678", "https://example.com/thumb.jpg")


class TestParseItemErrors:
    """parse_item のエラーケースのテスト"""

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
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)
        (tmp_path / "debug").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = amazhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h._db = unittest.mock.MagicMock()
            yield h
            h.finish()

    def test_parse_item_thumbnail_fetch_failure(self, handle):
        """サムネイル取得失敗時はエラーを記録"""
        import datetime

        import my_lib.graceful_shutdown

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 商品リンク要素をシミュレート
        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://www.amazon.co.jp/dp/B012345678"

        # 価格要素をシミュレート
        mock_price = unittest.mock.MagicMock()
        mock_price.get_attribute.return_value = "¥1,234"

        # サムネイル要素をシミュレート
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = "https://example.com/thumb.jpg"

        # 販売者要素をシミュレート
        mock_seller = unittest.mock.MagicMock()
        mock_seller.text = "テスト販売者"

        def find_element_side_effect(by, xpath):
            if "itemTitle" in xpath:
                return mock_link
            elif "itemImage" in xpath:
                return mock_thumb
            return unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "unitPrice" in xpath:
                return [mock_price]
            elif "orderedMerchant" in xpath:
                return [mock_seller]
            return []

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.side_effect = find_elements_side_effect

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
                "my_lib.selenium_util.with_retry",
                side_effect=Exception("サムネイル取得失敗"),
            ),
            unittest.mock.patch("time.sleep"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.name == "テスト商品"
        # エラーが記録されていることを確認
        handle._db.record_error.assert_called_once()

    def test_parse_item_price_parse_failure(self, handle):
        """価格パース失敗時はエラーを記録"""
        import datetime

        import my_lib.graceful_shutdown

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 商品リンク要素をシミュレート
        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://www.amazon.co.jp/dp/B012345678"

        # 価格要素をシミュレート（不正な値）
        mock_price = unittest.mock.MagicMock()
        mock_price.get_attribute.return_value = "無料"  # パースできない価格

        # サムネイル要素をシミュレート
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = None  # サムネイルなし

        # 販売者要素をシミュレート
        mock_seller = unittest.mock.MagicMock()
        mock_seller.text = "テスト販売者"

        def find_element_side_effect(by, xpath):
            if "itemTitle" in xpath:
                return mock_link
            elif "itemImage" in xpath:
                return mock_thumb
            return unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "unitPrice" in xpath:
                return [mock_price]
            elif "orderedMerchant" in xpath:
                return [mock_seller]
            return []

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.side_effect = find_elements_side_effect

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
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.price == 0  # パース失敗時は 0
        # エラーが記録されていることを確認
        handle._db.record_or_update_error.assert_called_once()

    def test_parse_item_price_not_found(self, handle):
        """価格要素が見つからない場合はエラーを記録"""
        import datetime

        import my_lib.graceful_shutdown

        import amazhist.order

        my_lib.graceful_shutdown.reset_shutdown_flag()
        driver, _ = handle.get_selenium_driver()

        # 商品リンク要素をシミュレート
        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://www.amazon.co.jp/dp/B012345678"

        # サムネイル要素をシミュレート
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = None  # サムネイルなし

        # 販売者要素をシミュレート
        mock_seller = unittest.mock.MagicMock()
        mock_seller.text = "テスト販売者"

        def find_element_side_effect(by, xpath):
            if "itemTitle" in xpath:
                return mock_link
            elif "itemImage" in xpath:
                return mock_thumb
            return unittest.mock.MagicMock()

        def find_elements_side_effect(by, xpath):
            if "unitPrice" in xpath:
                return []  # 価格要素なし
            elif "orderedMerchant" in xpath:
                return [mock_seller]
            return []

        driver.find_element.side_effect = find_element_side_effect
        driver.find_elements.side_effect = find_elements_side_effect

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
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = amazhist.item.parse_item(handle, "//div", order)

        assert result is not None
        assert result.price == 0  # 価格なしの場合は 0
        # エラーが記録されていることを確認
        handle._db.record_or_update_error.assert_called_once()


class TestParseItemGiftcard:
    """_parse_item_giftcard のテスト"""

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

    def test_parse_item_giftcard(self, handle):
        """ギフトカードのパース"""
        driver, _ = handle.get_selenium_driver()

        # 価格要素をシミュレート
        mock_price_elem = unittest.mock.MagicMock()
        mock_price_elem.text = "¥5,000"
        driver.find_element.return_value = mock_price_elem

        result = amazhist.item._parse_item_giftcard(handle, "//div")

        assert result["count"] == 1
        assert result["price"] == 5000
        assert result["seller"] == "アマゾンジャパン合同会社"
        assert result["condition"] == "新品"
        assert result["kind"] == "Gift card"

    def test_parse_item_giftcard_invalid_price(self, handle):
        """ギフトカードの価格パース失敗時は0"""
        driver, _ = handle.get_selenium_driver()

        # 価格要素をシミュレート（不正な値）
        mock_price_elem = unittest.mock.MagicMock()
        mock_price_elem.text = "無効な価格"
        driver.find_element.return_value = mock_price_elem

        result = amazhist.item._parse_item_giftcard(handle, "//div")

        assert result["price"] == 0


class TestParseItemDefault:
    """_parse_item_default のテスト"""

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

    def test_parse_item_default(self, handle):
        """デフォルトパースのテスト"""
        driver, _ = handle.get_selenium_driver()

        # 価格要素をシミュレート
        mock_price_elem = unittest.mock.MagicMock()
        mock_price_elem.text = "¥1,234"
        driver.find_element.return_value = mock_price_elem

        with unittest.mock.patch("my_lib.selenium_util.get_text") as mock_get_text:
            # 数量: 2, 販売者: テスト販売者, コンディション: 中古品
            def get_text_side_effect(driver, xpath, default):
                if "item-view-qty" in xpath:
                    return "2"
                elif "販売:" in xpath:
                    return " テスト販売者 から"
                elif "コンディション" in xpath:
                    return "中古品"
                return default

            mock_get_text.side_effect = get_text_side_effect

            result = amazhist.item._parse_item_default(handle, "//div")

        assert result["count"] == 2
        assert result["price"] == 2468  # 1234 * 2
        assert result["seller"] == "テスト販売者"
        assert result["condition"] == "中古品"
        assert result["kind"] == "Normal"

    def test_parse_item_default_with_defaults(self, handle):
        """デフォルト値のテスト"""
        driver, _ = handle.get_selenium_driver()

        # 価格要素をシミュレート
        mock_price_elem = unittest.mock.MagicMock()
        mock_price_elem.text = "¥500"
        driver.find_element.return_value = mock_price_elem

        with unittest.mock.patch("my_lib.selenium_util.get_text") as mock_get_text:
            # デフォルト値を使用
            def get_text_side_effect(driver, xpath, default):
                return default

            mock_get_text.side_effect = get_text_side_effect

            result = amazhist.item._parse_item_default(handle, "//div")

        assert result["count"] == 1
        assert result["price"] == 500
        assert result["seller"] == "アマゾンジャパン合同会社"
        assert result["condition"] == "新品"
        assert result["kind"] == "Normal"
