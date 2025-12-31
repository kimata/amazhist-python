#!/usr/bin/env python3
# ruff: noqa: S101
"""
migrate.py のテスト
"""
import pathlib
import pickle

import pytest

import amazhist.migrate

# スキーマファイルのパス
SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


class TestIsPickleFile:
    """is_pickle_file のテスト"""

    def test_is_pickle_file_true(self, tmp_path):
        """pickle ファイルの場合 True"""
        pickle_path = tmp_path / "test.dat"
        with open(pickle_path, "wb") as f:
            pickle.dump({"test": "data"}, f)

        assert amazhist.migrate.is_pickle_file(pickle_path) is True

    def test_is_pickle_file_false_not_exists(self, tmp_path):
        """存在しないファイルは False"""
        not_exists = tmp_path / "not_exists.dat"

        assert amazhist.migrate.is_pickle_file(not_exists) is False

    def test_is_pickle_file_false_sqlite(self, tmp_path):
        """SQLite ファイルは False"""
        import sqlite3

        sqlite_path = tmp_path / "test.db"
        conn = sqlite3.connect(sqlite_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        assert amazhist.migrate.is_pickle_file(sqlite_path) is False

    def test_is_pickle_file_false_text(self, tmp_path):
        """テキストファイルは False"""
        text_path = tmp_path / "test.txt"
        text_path.write_text("hello world")

        assert amazhist.migrate.is_pickle_file(text_path) is False


class TestNeedsMigration:
    """needs_migration のテスト"""

    def test_needs_migration_pickle_exists(self, tmp_path):
        """pickle ファイルが存在する場合 True"""
        pickle_path = tmp_path / "cache.dat"
        with open(pickle_path, "wb") as f:
            pickle.dump({"test": "data"}, f)

        assert amazhist.migrate.needs_migration(pickle_path) is True

    def test_needs_migration_not_exists(self, tmp_path):
        """ファイルが存在しない場合 False"""
        not_exists = tmp_path / "not_exists.dat"

        assert amazhist.migrate.needs_migration(not_exists) is False

    def test_needs_migration_sqlite_exists(self, tmp_path):
        """SQLite ファイルが存在する場合 False"""
        import sqlite3

        sqlite_path = tmp_path / "cache.dat"
        conn = sqlite3.connect(sqlite_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        assert amazhist.migrate.needs_migration(sqlite_path) is False


class TestMigratePickleToSqlite:
    """migrate_pickle_to_sqlite のテスト"""

    def test_migrate_empty_data(self, tmp_path):
        """空のデータをマイグレーション"""
        pickle_path = tmp_path / "cache.dat"
        sqlite_path = tmp_path / "cache_new.dat"

        # 空のデータを pickle で保存
        data = {
            "order_info": {},
            "stat": {"year_list": []},
        }
        with open(pickle_path, "wb") as f:
            pickle.dump(data, f)

        result = amazhist.migrate.migrate_pickle_to_sqlite(pickle_path, sqlite_path, SCHEMA_PATH)

        assert result is True
        assert sqlite_path.exists()

    def test_migrate_with_items(self, tmp_path):
        """アイテム付きのデータをマイグレーション"""
        import datetime

        pickle_path = tmp_path / "cache.dat"
        sqlite_path = tmp_path / "cache.dat"  # 同じパス

        # データを pickle で保存（実際の pickle 形式で）
        data = {
            "year_list": [2025],
            "year_count": {2025: 1},
            "year_stat": {},
            "page_stat": {},
            "item_list": [
                {
                    "no": "503-1234567-8901234",
                    "date": datetime.datetime(2025, 1, 15),
                    "name": "テスト商品",
                    "asin": "B0123456789",
                    "price": 1500,
                }
            ],
            "order_no_stat": {},
            "last_modified": datetime.datetime(2025, 1, 15),
        }
        with open(pickle_path, "wb") as f:
            pickle.dump(data, f)

        result = amazhist.migrate.migrate_pickle_to_sqlite(pickle_path, sqlite_path, SCHEMA_PATH)

        assert result is True
        assert sqlite_path.exists()

        # バックアップが作成されている (.dat → .pickle.bak)
        backup_path = pickle_path.with_suffix(".pickle.bak")
        assert backup_path.exists()

    def test_migrate_creates_backup(self, tmp_path):
        """マイグレーション時にバックアップが作成される"""
        pickle_path = tmp_path / "cache.dat"
        sqlite_path = tmp_path / "cache.dat"  # 同じパス

        data = {
            "year_list": [],
            "year_count": {},
            "year_stat": {},
            "page_stat": {},
            "item_list": [],
            "order_no_stat": {},
        }
        with open(pickle_path, "wb") as f:
            pickle.dump(data, f)

        amazhist.migrate.migrate_pickle_to_sqlite(pickle_path, sqlite_path, SCHEMA_PATH)

        # バックアップが作成されている (.dat → .pickle.bak)
        backup_path = pickle_path.with_suffix(".pickle.bak")
        assert backup_path.exists()
