#!/usr/bin/env python3
# ruff: noqa: S101
"""
history.py のテスト
"""
import unittest.mock

import pytest

import amazhist.config
import amazhist.handle
import amazhist.history


class TestSheetDef:
    """_SHEET_DEF のテスト"""

    def test_sheet_def_exists(self):
        """シート定義が存在"""
        assert "SHEET_TITLE" in amazhist.history._SHEET_DEF
        assert "TABLE_HEADER" in amazhist.history._SHEET_DEF

    def test_columns(self):
        """カラム定義"""
        cols = amazhist.history._SHEET_DEF["TABLE_HEADER"]["col"]
        expected_cols = ["shop_name", "date", "name", "image", "count", "price", "category", "seller", "id", "no"]
        for col in expected_cols:
            assert col in cols

    def test_link_func_id(self):
        """商品IDのリンク関数"""
        import datetime

        import amazhist.item

        cols = amazhist.history._SHEET_DEF["TABLE_HEADER"]["col"]
        item = amazhist.item.Item(
            name="テスト商品",
            date=datetime.datetime(2025, 1, 1),
            no="ORDER-001",
            url="https://www.amazon.co.jp/dp/B0123456789",
        )

        assert cols["id"]["link_func"](item) == "https://www.amazon.co.jp/dp/B0123456789"

    def test_link_func_no(self):
        """注文番号のリンク関数"""
        import datetime

        import amazhist.item

        cols = amazhist.history._SHEET_DEF["TABLE_HEADER"]["col"]
        item = amazhist.item.Item(
            name="テスト商品",
            date=datetime.datetime(2025, 1, 1),
            no="503-1234567-8901234",
        )

        result = cols["no"]["link_func"](item)
        assert "503-1234567-8901234" in result

    def test_shop_name_value(self):
        """ショップ名の固定値"""
        cols = amazhist.history._SHEET_DEF["TABLE_HEADER"]["col"]
        assert cols["shop_name"]["value"] == "アマゾン"


class TestGenerateTableExcel:
    """generate_table_excel のテスト"""

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
        (tmp_path / "output").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            # データベースモック
            h._db = unittest.mock.MagicMock()
            h._db.get_item_list.return_value = []
            yield h
            h.finish()

    def test_generate_table_excel_empty(self, handle, tmp_path):
        """空のリストでExcel生成"""
        excel_path = tmp_path / "output" / "test.xlsx"

        def mock_gen_sheet(book, *args, **kwargs):
            # テスト用にシートを追加
            book.create_sheet("テスト")

        with unittest.mock.patch("my_lib.openpyxl_util.generate_list_sheet", side_effect=mock_gen_sheet):
            amazhist.history.generate_table_excel(handle, excel_path, is_need_thumb=True)

        assert excel_path.exists()

    def test_generate_table_excel_without_thumb(self, handle, tmp_path):
        """サムネイルなしでExcel生成"""
        excel_path = tmp_path / "output" / "test_no_thumb.xlsx"

        def mock_gen_sheet(book, *args, **kwargs):
            book.create_sheet("テスト")

        with unittest.mock.patch("my_lib.openpyxl_util.generate_list_sheet", side_effect=mock_gen_sheet) as mock_gen:
            amazhist.history.generate_table_excel(handle, excel_path, is_need_thumb=False)

            # is_need_thumb が False で渡されることを確認
            call_args = mock_gen.call_args
            assert call_args[0][3] is False  # is_need_thumb

    def test_generate_table_excel_status_updates(self, handle, tmp_path):
        """ステータス更新が行われる"""
        excel_path = tmp_path / "output" / "test_status.xlsx"

        def mock_gen_sheet(book, *args, **kwargs):
            book.create_sheet("テスト")

        with unittest.mock.patch("my_lib.openpyxl_util.generate_list_sheet", side_effect=mock_gen_sheet):
            amazhist.history.generate_table_excel(handle, excel_path)

        # 最終ステータスが完了になっている
        assert "完了" in handle._status_text
