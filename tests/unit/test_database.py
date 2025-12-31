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


class TestDatabaseErrorLog:
    """Database エラーログのテスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_record_error(self, db):
        """エラーの記録"""
        error_id = db.record_error(
            url="https://example.com/order/123",
            error_type="parse_error",
            context="order",
            message="注文のパースに失敗しました",
            order_no="503-1234567-8901234",
        )

        assert error_id > 0

        errors = db.get_unresolved_errors()
        assert len(errors) == 1
        assert errors[0]["url"] == "https://example.com/order/123"
        assert errors[0]["error_type"] == "parse_error"
        assert errors[0]["context"] == "order"
        assert errors[0]["order_no"] == "503-1234567-8901234"
        assert errors[0]["resolved"] is False

    def test_record_error_with_item_name(self, db):
        """商品名付きエラーの記録"""
        db.record_error(
            url="https://example.com/thumb/abc.jpg",
            error_type="fetch_error",
            context="thumbnail",
            message="Timeout",
            item_name="テスト商品",
        )

        errors = db.get_unresolved_errors()
        assert len(errors) == 1
        assert errors[0]["item_name"] == "テスト商品"
        assert errors[0]["context"] == "thumbnail"

    def test_get_unresolved_errors_filter_by_context(self, db):
        """コンテキストでフィルタ"""
        db.record_error(url="url1", error_type="error", context="order")
        db.record_error(url="url2", error_type="error", context="thumbnail")
        db.record_error(url="url3", error_type="error", context="order")

        order_errors = db.get_unresolved_errors(context="order")
        assert len(order_errors) == 2

        thumb_errors = db.get_unresolved_errors(context="thumbnail")
        assert len(thumb_errors) == 1

    def test_mark_error_resolved(self, db):
        """エラーを解決済みにする"""
        error_id = db.record_error(url="url1", error_type="error", context="order")

        assert db.get_error_count(resolved=False) == 1
        assert db.get_error_count(resolved=True) == 0

        db.mark_error_resolved(error_id)

        assert db.get_error_count(resolved=False) == 0
        assert db.get_error_count(resolved=True) == 1

    def test_mark_errors_resolved_by_url(self, db):
        """URL でエラーを一括解決済みにする"""
        db.record_error(url="url1", error_type="error", context="order")
        db.record_error(url="url1", error_type="error", context="order")
        db.record_error(url="url2", error_type="error", context="order")

        count = db.mark_errors_resolved_by_url("url1")

        assert count == 2
        assert db.get_error_count(resolved=False) == 1
        assert db.get_error_count(resolved=True) == 2

    def test_increment_retry_count(self, db):
        """リトライ回数のインクリメント"""
        error_id = db.record_error(url="url1", error_type="error", context="order")

        errors = db.get_unresolved_errors()
        assert errors[0]["retry_count"] == 0

        db.increment_retry_count(error_id)
        db.increment_retry_count(error_id)

        errors = db.get_unresolved_errors()
        assert errors[0]["retry_count"] == 2

    def test_get_all_errors(self, db):
        """全エラー取得（解決済み含む）"""
        error_id = db.record_error(url="url1", error_type="error", context="order")
        db.record_error(url="url2", error_type="error", context="order")
        db.mark_error_resolved(error_id)

        all_errors = db.get_all_errors()
        assert len(all_errors) == 2

        unresolved = db.get_unresolved_errors()
        assert len(unresolved) == 1

    def test_get_error_count(self, db):
        """エラー件数取得"""
        db.record_error(url="url1", error_type="error", context="order")
        error_id = db.record_error(url="url2", error_type="error", context="order")
        db.record_error(url="url3", error_type="error", context="order")
        db.mark_error_resolved(error_id)

        assert db.get_error_count() == 3
        assert db.get_error_count(resolved=False) == 2
        assert db.get_error_count(resolved=True) == 1

    def test_clear_old_errors(self, db):
        """古いエラーの削除"""
        # 古いエラーを手動で挿入（通常の record_error は現在時刻を使う）
        conn = db._get_conn()
        old_date = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
        conn.execute(
            """
            INSERT INTO error_log (url, error_type, context, created_at, resolved)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("old_url", "error", "order", old_date, 1),
        )
        conn.commit()

        # 新しい解決済みエラー
        error_id = db.record_error(url="new_url", error_type="error", context="order")
        db.mark_error_resolved(error_id)

        # 30日以上前の解決済みエラーを削除
        deleted = db.clear_old_errors(days=30)

        assert deleted == 1
        assert db.get_error_count() == 1
