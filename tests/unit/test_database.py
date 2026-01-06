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


class TestIsSqliteFile:
    """_is_sqlite_file のテスト"""

    def test_is_sqlite_file_valid(self, tmp_path):
        """有効な SQLite ファイル"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)
        db.close()

        assert amazhist.database._is_sqlite_file(db_path) is True

    def test_is_sqlite_file_not_exists(self, tmp_path):
        """存在しないファイル"""
        db_path = tmp_path / "not_exists.db"
        assert amazhist.database._is_sqlite_file(db_path) is False

    def test_is_sqlite_file_too_small(self, tmp_path):
        """小さすぎるファイル"""
        db_path = tmp_path / "small.db"
        db_path.write_bytes(b"small")
        assert amazhist.database._is_sqlite_file(db_path) is False

    def test_is_sqlite_file_not_sqlite(self, tmp_path):
        """SQLite 形式でないファイル"""
        db_path = tmp_path / "not_sqlite.db"
        db_path.write_bytes(b"This is not a SQLite file at all")
        assert amazhist.database._is_sqlite_file(db_path) is False


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

    def test_get_conn_after_close(self, tmp_path):
        """接続が閉じられた後のアクセス"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)
        db.close()

        with pytest.raises(RuntimeError, match="Database connection is closed"):
            db._get_conn()

    def test_close_twice(self, tmp_path):
        """接続を2回閉じる (line 70->exit)"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)

        # 1回目の close
        db.close()
        assert db._conn is None

        # 2回目の close（何も起きない）
        db.close()
        assert db._conn is None


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

    def test_get_item_count(self, db):
        """商品数の取得"""
        assert db.get_item_count() == 0

        db.upsert_item({"no": "001", "asin": "A1", "date": datetime.datetime(2025, 1, 10), "name": "商品1"})
        assert db.get_item_count() == 1

        db.upsert_item({"no": "002", "asin": "A2", "date": datetime.datetime(2025, 1, 11), "name": "商品2"})
        assert db.get_item_count() == 2

    def test_get_last_item_by_filter(self, db):
        """time_filter で最後の商品を取得"""
        items = [
            {
                "no": "001",
                "asin": "A1",
                "date": datetime.datetime(2025, 1, 10),
                "name": "商品1",
                "order_time_filter": 2025,
            },
            {
                "no": "002",
                "asin": "A2",
                "date": datetime.datetime(2025, 1, 20),
                "name": "商品2",
                "order_time_filter": 2025,
            },
            {
                "no": "003",
                "asin": "A3",
                "date": datetime.datetime(2024, 12, 15),
                "name": "商品3",
                "order_time_filter": 2024,
            },
        ]
        for item in items:
            db.upsert_item(item)

        # 2025年の最後のアイテム
        last_2025 = db.get_last_item_by_filter(2025)
        assert last_2025 is not None
        assert last_2025["name"] == "商品2"

        # 2024年の最後のアイテム
        last_2024 = db.get_last_item_by_filter(2024)
        assert last_2024 is not None
        assert last_2024["name"] == "商品3"

        # 存在しない年
        last_2023 = db.get_last_item_by_filter(2023)
        assert last_2023 is None


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
        assert errors[0].url == "https://example.com/order/123"
        assert errors[0].error_type == "parse_error"
        assert errors[0].context == "order"
        assert errors[0].order_no == "503-1234567-8901234"
        assert errors[0].resolved is False

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
        assert errors[0].item_name == "テスト商品"
        assert errors[0].context == "thumbnail"

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
        assert errors[0].retry_count == 0

        db.increment_retry_count(error_id)
        db.increment_retry_count(error_id)

        errors = db.get_unresolved_errors()
        assert errors[0].retry_count == 2

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

    def test_get_unresolved_error_by_url(self, db):
        """URL とコンテキストで未解決エラーを検索"""
        db.record_error(url="url1", error_type="error", context="order")
        db.record_error(url="url1", error_type="error", context="thumbnail")

        error = db.get_unresolved_error_by_url("url1", "order")
        assert error is not None
        assert error.context == "order"

        error = db.get_unresolved_error_by_url("url1", "thumbnail")
        assert error is not None
        assert error.context == "thumbnail"

        error = db.get_unresolved_error_by_url("url1", "category")
        assert error is None

        error = db.get_unresolved_error_by_url("url2", "order")
        assert error is None

    def test_record_or_update_error_new(self, db):
        """新規エラーの記録"""
        error_id = db.record_or_update_error(
            url="url1", error_type="error", context="order", message="初回エラー"
        )

        errors = db.get_unresolved_errors()
        assert len(errors) == 1
        assert errors[0].id == error_id
        assert errors[0].retry_count == 0

    def test_record_or_update_error_existing(self, db):
        """既存エラーの更新（retry_count 増加）"""
        error_id1 = db.record_or_update_error(
            url="url1", error_type="error", context="order", message="初回エラー"
        )

        # 同じ URL とコンテキストで再度記録
        error_id2 = db.record_or_update_error(
            url="url1", error_type="error", context="order", message="2回目エラー"
        )

        # 同じ ID が返される
        assert error_id1 == error_id2

        errors = db.get_unresolved_errors()
        assert len(errors) == 1
        assert errors[0].retry_count == 1

    def test_get_failed_order_numbers(self, db):
        """エラーが発生した注文番号を取得"""
        db.record_error(url="url1", error_type="error", context="order", order_no="ORDER-001")
        db.record_error(url="url2", error_type="error", context="order", order_no="ORDER-002")
        # context が違う
        db.record_error(url="url3", error_type="error", context="thumbnail", order_no="ORDER-003")
        db.record_error(url="url4", error_type="error", context="order")  # order_no なし

        order_numbers = db.get_failed_order_numbers()
        assert len(order_numbers) == 2
        assert "ORDER-001" in order_numbers
        assert "ORDER-002" in order_numbers
        assert "ORDER-003" not in order_numbers

    def test_get_failed_category_items(self, db):
        """カテゴリ取得に失敗したアイテムを取得"""
        # アイテムを追加
        db.upsert_item(
            {
                "no": "ORDER-001",
                "asin": "ASIN001",
                "date": datetime.datetime(2025, 1, 10),
                "name": "テスト商品",
                "url": "https://amazon.co.jp/dp/ASIN001",
            }
        )

        # カテゴリエラーを記録
        db.record_error(
            url="https://amazon.co.jp/dp/ASIN001",
            error_type="parse_error",
            context="category",
        )

        failed_items = db.get_failed_category_items()
        assert len(failed_items) == 1
        assert failed_items[0]["url"] == "https://amazon.co.jp/dp/ASIN001"
        assert failed_items[0]["asin"] == "ASIN001"

    def test_update_item_category(self, db):
        """アイテムのカテゴリを更新"""
        db.upsert_item(
            {
                "no": "ORDER-001",
                "asin": "ASIN001",
                "date": datetime.datetime(2025, 1, 10),
                "name": "テスト商品",
                "url": "https://amazon.co.jp/dp/ASIN001",
                "category": [],
            }
        )

        count = db.update_item_category(
            "https://amazon.co.jp/dp/ASIN001",
            ["本", "コンピュータ・IT"],
        )

        assert count == 1

        items = db.get_item_list()
        # Item dataclass では category は tuple
        assert items[0].category == ("本", "コンピュータ・IT")

    def test_get_failed_thumbnail_items(self, db):
        """サムネイル取得に失敗したアイテムを取得"""
        db.upsert_item(
            {
                "no": "ORDER-001",
                "asin": "ASIN001",
                "date": datetime.datetime(2025, 1, 10),
                "name": "テスト商品",
                "url": "https://amazon.co.jp/dp/ASIN001",
            }
        )

        db.record_error(
            url="https://images.amazon.com/ASIN001.jpg",
            error_type="fetch_error",
            context="thumbnail",
            item_name="テスト商品",
        )

        failed_items = db.get_failed_thumbnail_items()
        assert len(failed_items) == 1
        assert failed_items[0]["thumb_url"] == "https://images.amazon.com/ASIN001.jpg"
        assert failed_items[0]["name"] == "テスト商品"

    def test_mark_errors_resolved_by_order_no(self, db):
        """注文番号でエラーを一括解決済みにする"""
        db.record_error(url="url1", error_type="error", context="order", order_no="ORDER-001")
        db.record_error(url="url2", error_type="error", context="thumbnail", order_no="ORDER-001")
        db.record_error(url="url3", error_type="error", context="order", order_no="ORDER-002")

        count = db.mark_errors_resolved_by_order_no("ORDER-001")

        assert count == 2
        assert db.get_error_count(resolved=False) == 1
        assert db.get_error_count(resolved=True) == 2


class TestDatabaseYearStatusExtended:
    """Database 年別ステータスの追加テスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_get_item_count_by_year(self, db):
        """指定年の商品数を取得 (lines 141-147)"""
        # 2025年の商品を追加
        db.upsert_item(
            {
                "no": "001",
                "asin": "A1",
                "date": datetime.datetime(2025, 1, 10),
                "name": "商品1",
                "order_time_filter": 2025,
            }
        )
        db.upsert_item(
            {
                "no": "002",
                "asin": "A2",
                "date": datetime.datetime(2025, 2, 15),
                "name": "商品2",
                "order_time_filter": 2025,
            }
        )
        # 2024年の商品を追加
        db.upsert_item(
            {
                "no": "003",
                "asin": "A3",
                "date": datetime.datetime(2024, 12, 1),
                "name": "商品3",
                "order_time_filter": 2024,
            }
        )

        # 2025年の商品数
        assert db.get_item_count_by_year(2025) == 2
        # 2024年の商品数
        assert db.get_item_count_by_year(2024) == 1
        # 存在しない年
        assert db.get_item_count_by_year(2023) == 0

    def test_set_year_status_with_existing_record(self, db):
        """既存レコードがある場合の年ステータス更新 (lines 208-209)"""
        # まず新規レコードを作成
        db.set_year_status(2025, order_count=50, checked=False)

        assert db.get_year_order_count(2025) == 50
        assert db.is_year_checked(2025) is False

        # 既存レコードを更新（order_count のみ）
        db.set_year_status(2025, order_count=100)

        assert db.get_year_order_count(2025) == 100
        assert db.is_year_checked(2025) is False  # checked は変更されない

        # 既存レコードを更新（checked のみ）
        db.set_year_status(2025, checked=True)

        assert db.get_year_order_count(2025) == 100  # order_count は変更されない
        assert db.is_year_checked(2025) is True

    def test_reset_year_status(self, db):
        """年ステータスのリセット (lines 242-249)"""
        # 年ステータスを設定
        db.set_year_status(2025, order_count=100, checked=True)
        # ページステータスを設定
        db.set_page_checked(2025, 1, True)
        db.set_page_checked(2025, 2, True)

        # 確認
        assert db.get_year_order_count(2025) == 100
        assert db.is_year_checked(2025) is True
        assert db.is_page_checked(2025, 1) is True
        assert db.is_page_checked(2025, 2) is True

        # リセット
        db.reset_year_status(2025)

        # 年ステータスがリセットされている
        assert db.get_year_order_count(2025) == 0
        assert db.is_year_checked(2025) is False
        # ページステータスもリセットされている
        assert db.is_page_checked(2025, 1) is False
        assert db.is_page_checked(2025, 2) is False


class TestDatabaseMetadataExtended:
    """Database メタデータの追加テスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_get_last_modified_default(self, db):
        """最終更新日時のデフォルト値 (line 316)"""
        # メタデータが設定されていない場合はデフォルト値を返す
        result = db.get_last_modified()
        assert result.year == 1994
        assert result.month == 7
        assert result.day == 5


class TestDatabaseItemsExtended:
    """Database アイテム操作の追加テスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_row_to_item_with_invalid_date(self, db):
        """date がパース不能な場合のフォールバック (line 165)"""
        # 直接 SQL で不正な日付フォーマットのレコードを挿入
        conn = db._get_conn()
        conn.execute(
            """
            INSERT INTO items (order_no, date, name, asin, count, price, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("ORDER-INVALID-DATE", "invalid-date-format", "日付不正商品", "ASIN001", 1, 1000, "[]"),
        )
        conn.commit()

        # get_item_list で取得してみる
        items = db.get_item_list()
        assert len(items) == 1
        # パース失敗の場合は 1970-01-01 にフォールバック
        assert items[0].date.year == 1970
        assert items[0].date.month == 1
        assert items[0].date.day == 1


class TestDatabaseErrorLogExtended:
    """Database エラーログの追加テスト"""

    @pytest.fixture
    def db(self, tmp_path):
        """Database インスタンス"""
        db_path = tmp_path / "test.db"
        database = amazhist.database.open_database(db_path, SCHEMA_PATH)
        yield database
        database.close()

    def test_get_unresolved_error_count_by_year(self, db):
        """指定年の未解決エラー数を取得 (lines 449-455)"""
        # 2025年のエラーを記録
        db.record_error(
            url="url1",
            error_type="error",
            context="order",
            order_year=2025,
        )
        db.record_error(
            url="url2",
            error_type="error",
            context="order",
            order_year=2025,
        )
        # 2024年のエラーを記録
        db.record_error(
            url="url3",
            error_type="error",
            context="order",
            order_year=2024,
        )
        # 解決済みのエラー（カウントされない）
        error_id = db.record_error(
            url="url4",
            error_type="error",
            context="order",
            order_year=2025,
        )
        db.mark_error_resolved(error_id)

        assert db.get_unresolved_error_count_by_year(2025) == 2
        assert db.get_unresolved_error_count_by_year(2024) == 1
        assert db.get_unresolved_error_count_by_year(2023) == 0

    def test_get_failed_orders(self, db):
        """エラーが発生した注文情報を取得 (lines 481-490)"""
        # order コンテキストのエラーを記録
        db.record_error(
            url="https://amazon.co.jp/order/1",
            error_type="timeout",
            context="order",
            order_no="ORDER-001",
            order_year=2025,
            order_page=1,
            order_index=0,
        )
        db.record_error(
            url="https://amazon.co.jp/order/2",
            error_type="parse_error",
            context="order",
            order_no="ORDER-002",
            order_year=2025,
            order_page=2,
            order_index=1,
        )
        # thumbnail コンテキストのエラー（含まれない）
        db.record_error(
            url="https://images.amazon.com/thumb.jpg",
            error_type="fetch_error",
            context="thumbnail",
            order_no="ORDER-003",
            order_year=2025,
        )

        failed_orders = db.get_failed_orders()
        assert len(failed_orders) == 2

        # 最新順なので ORDER-002 が先
        assert failed_orders[0]["order_no"] == "ORDER-002"
        assert failed_orders[0]["order_year"] == 2025
        assert failed_orders[0]["order_page"] == 2
        assert failed_orders[0]["order_index"] == 1
        assert failed_orders[0]["error_type"] == "parse_error"

        assert failed_orders[1]["order_no"] == "ORDER-001"
        assert failed_orders[1]["order_year"] == 2025
        assert failed_orders[1]["order_page"] == 1
        assert failed_orders[1]["order_index"] == 0
        assert failed_orders[1]["error_type"] == "timeout"

    def test_get_thumbnail_asin_by_error_id(self, db):
        """エラーIDからサムネイルの ASIN を取得 (lines 588-599)"""
        # アイテムを追加
        db.upsert_item(
            {
                "no": "ORDER-001",
                "asin": "ASIN001",
                "date": datetime.datetime(2025, 1, 10),
                "name": "テスト商品",
                "url": "https://amazon.co.jp/dp/ASIN001",
            }
        )

        # サムネイルエラーを記録
        error_id = db.record_error(
            url="https://images.amazon.com/ASIN001.jpg",
            error_type="fetch_error",
            context="thumbnail",
            item_name="テスト商品",
        )

        # ASIN を取得
        asin = db.get_thumbnail_asin_by_error_id(error_id)
        assert asin == "ASIN001"

        # 存在しないエラーID
        asin = db.get_thumbnail_asin_by_error_id(9999)
        assert asin is None

        # thumbnail コンテキストでないエラー
        other_error_id = db.record_error(
            url="https://amazon.co.jp/order/1",
            error_type="error",
            context="order",
        )
        asin = db.get_thumbnail_asin_by_error_id(other_error_id)
        assert asin is None

    def test_get_error_by_id(self, db):
        """IDでエラーを取得 (lines 626-629)"""
        error_id = db.record_error(
            url="https://amazon.co.jp/order/1",
            error_type="timeout",
            context="order",
            message="リクエストがタイムアウトしました",
            order_no="ORDER-001",
        )

        # 存在するID
        error = db.get_error_by_id(error_id)
        assert error is not None
        assert error.id == error_id
        assert error.url == "https://amazon.co.jp/order/1"
        assert error.error_type == "timeout"
        assert error.context == "order"
        assert error.error_message == "リクエストがタイムアウトしました"
        assert error.order_no == "ORDER-001"

        # 存在しないID
        error = db.get_error_by_id(9999)
        assert error is None

    def test_get_failed_years(self, db):
        """年単位のエラー（order_count_fallback）を取得 (lines 729-739)"""
        # order_count_fallback エラーを記録
        db.record_error(
            url="https://amazon.co.jp/orders/2025",
            error_type="order_count_fallback",
            context="order",
            order_year=2025,
        )
        db.record_error(
            url="https://amazon.co.jp/orders/2024",
            error_type="order_count_fallback",
            context="order",
            order_year=2024,
        )
        # 解決済みのエラー（含まれない）
        error_id = db.record_error(
            url="https://amazon.co.jp/orders/2023",
            error_type="order_count_fallback",
            context="order",
            order_year=2023,
        )
        db.mark_error_resolved(error_id)
        # 別のエラータイプ（含まれない）
        db.record_error(
            url="https://amazon.co.jp/orders/2022",
            error_type="timeout",
            context="order",
            order_year=2022,
        )

        failed_years = db.get_failed_years()
        assert len(failed_years) == 2

        # order_year 順にソートされている
        assert failed_years[0].order_year == 2024
        assert failed_years[1].order_year == 2025


class TestDatabaseUtility:
    """Database ユーティリティのテスト"""

    def test_parse_datetime_with_timezone(self, tmp_path):
        """タイムゾーン付き日時のパース"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)

        # タイムゾーン付きの日時文字列
        result = db._parse_datetime("2025-01-15T10:30:00+09:00")
        assert result is not None
        assert result.tzinfo is None  # タイムゾーン情報は削除される
        assert result.hour == 10

        db.close()

    def test_parse_datetime_invalid(self, tmp_path):
        """不正な日時文字列のパース"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)

        result = db._parse_datetime("invalid-date")
        assert result is None

        result = db._parse_datetime("")
        assert result is None

        result = db._parse_datetime(None)
        assert result is None

        db.close()

    def test_parse_time_filter_invalid(self, tmp_path):
        """不正な time_filter のパース"""
        db_path = tmp_path / "test.db"
        db = amazhist.database.open_database(db_path, SCHEMA_PATH)

        result = db._parse_time_filter("not-a-number")
        assert result is None

        result = db._parse_time_filter("")
        assert result is None

        result = db._parse_time_filter(None)
        assert result is None

        result = db._parse_time_filter("2025")
        assert result == 2025

        db.close()
