#!/usr/bin/env python3
# ruff: noqa: S101
"""
database.py のテスト
"""
import datetime
import pathlib

import pytest

import amazhist.database

# スキーマファイルのパス
SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


class TestDatabaseBasic:
    """Database 基本操作のテスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_open_database(self, tmp_path):
        """データベースを開く"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)

        assert db is not None
        db.close()

    def test_database_creates_file(self, tmp_path):
        """データベースファイルが作成される"""
        db_path = tmp_path / "new_test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)
        db.close()

        assert db_path.exists()


class TestDatabaseItems:
    """Database アイテム操作のテスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_upsert_item(self, db):
        """アイテムの挿入"""
        item = {
            "no": "503-1234567-8901234",
            "date": datetime.datetime(2025, 1, 15),
            "name": "テスト商品",
            "url": "https://www.amazon.co.jp/dp/B0123456789",
            "asin": "B0123456789",
            "count": 1,
            "price": 1500,
            "seller": "アマゾンジャパン合同会社",
            "condition": "新品",
            "category": ["本", "コンピュータ・IT"],
        }

        db.upsert_item(item)

        items = db.get_item_list()
        assert len(items) == 1
        assert items[0]["name"] == "テスト商品"

    def test_upsert_item_update(self, db):
        """アイテムの更新"""
        item = {
            "no": "503-1234567-8901234",
            "date": datetime.datetime(2025, 1, 15),
            "name": "テスト商品",
            "asin": "B0123456789",
            "price": 1500,
        }

        db.upsert_item(item)

        # 同じ no と asin で更新
        item["price"] = 2000
        db.upsert_item(item)

        items = db.get_item_list()
        assert len(items) == 1
        assert items[0]["price"] == 2000

    def test_get_item_list_sorted(self, db):
        """アイテムリストが日付順にソートされる"""
        items = [
            {"no": "001", "asin": "A1", "date": datetime.datetime(2025, 1, 20), "name": "商品3"},
            {"no": "002", "asin": "A2", "date": datetime.datetime(2025, 1, 10), "name": "商品1"},
            {"no": "003", "asin": "A3", "date": datetime.datetime(2025, 1, 15), "name": "商品2"},
        ]

        for item in items:
            db.upsert_item(item)

        result = db.get_item_list()

        assert result[0]["name"] == "商品1"  # 1/10
        assert result[1]["name"] == "商品2"  # 1/15
        assert result[2]["name"] == "商品3"  # 1/20

    def test_exists_order(self, db):
        """注文の存在確認"""
        item = {
            "no": "503-1234567-8901234",
            "asin": "B0123456789",
            "date": datetime.datetime(2025, 1, 15),
            "name": "テスト商品",
        }

        db.upsert_item(item)

        assert db.exists_order("503-1234567-8901234") is True
        assert db.exists_order("999-9999999-9999999") is False


class TestDatabaseYearStatus:
    """Database 年別ステータスのテスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_set_year_list(self, db):
        """年リストの設定"""
        db.set_year_list([2023, 2024, 2025])

        year_list = db.get_year_list()
        assert 2023 in year_list
        assert 2024 in year_list
        assert 2025 in year_list

    def test_set_year_status(self, db):
        """年ステータスの設定"""
        db.set_year_list([2025])
        db.set_year_status(2025, order_count=100, checked=True)

        assert db.get_year_order_count(2025) == 100
        assert db.is_year_checked(2025) is True

    def test_is_year_checked_default(self, db):
        """年チェックのデフォルト値"""
        db.set_year_list([2025])

        assert db.is_year_checked(2025) is False


class TestDatabasePageStatus:
    """Database ページステータスのテスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_set_page_checked(self, db):
        """ページチェックの設定"""
        db.set_page_checked(2025, 1, True)

        assert db.is_page_checked(2025, 1) is True
        assert db.is_page_checked(2025, 2) is False

    def test_clear_page_status(self, db):
        """ページステータスのクリア"""
        db.set_page_checked(2025, 1, True)
        db.set_page_checked(2025, 2, True)

        db.clear_page_status(2025)

        assert db.is_page_checked(2025, 1) is False
        assert db.is_page_checked(2025, 2) is False


class TestDatabaseMetadata:
    """Database メタデータのテスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_set_last_modified(self, db):
        """最終更新日時の設定"""
        now = datetime.datetime(2025, 1, 15, 10, 30)
        db.set_last_modified(now)

        result = db.get_last_modified()
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_get_total_order_count(self, db):
        """全注文数の取得（year_status の合計）"""
        db.set_year_list([2023, 2024, 2025])
        db.set_year_status(2023, order_count=50)
        db.set_year_status(2024, order_count=100)
        db.set_year_status(2025, order_count=150)

        assert db.get_total_order_count() == 300
