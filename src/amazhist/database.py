#!/usr/bin/env python3
"""SQLite データベースアクセス層"""

from __future__ import annotations

import datetime
import json
import pathlib
import sqlite3
from typing import Any

SQLITE_MAGIC = b"SQLite format 3\x00"


def is_sqlite_file(path: pathlib.Path) -> bool:
    """ファイルが SQLite 形式かどうかを判定"""
    if not path.exists() or path.stat().st_size < 16:
        return False
    with path.open("rb") as f:
        header = f.read(16)
    return header.startswith(SQLITE_MAGIC)


class Database:
    """SQLite データベースアクセス層"""

    def __init__(self, db_path: pathlib.Path, schema_path: pathlib.Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def _init_database(self) -> None:
        """データベースを初期化"""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row

        with self._schema_path.open("r", encoding="utf-8") as f:
            schema = f.read()
        self._conn.executescript(schema)
        self._conn.commit()

    def close(self) -> None:
        """データベース接続を閉じる"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """接続を取得"""
        if self._conn is None:
            raise RuntimeError("Database connection is closed")
        return self._conn

    # --- 商品 ---
    def upsert_item(self, item: dict[str, Any]) -> None:
        """商品を挿入または更新"""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO items (
                order_no, date, name, url, asin, count, price, category,
                seller, condition, kind, order_time_filter, order_page
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["no"],
                item["date"].isoformat() if isinstance(item["date"], datetime.datetime) else item["date"],
                item["name"],
                item.get("url"),
                item.get("asin"),
                item.get("count", 1),
                item.get("price", 0),
                json.dumps(item.get("category", []), ensure_ascii=False),
                item.get("seller"),
                item.get("condition"),
                item.get("kind"),
                str(item.get("order_time_filter", "")),
                item.get("order_page"),
            ),
        )
        conn.commit()

    def exists_order(self, order_no: str) -> bool:
        """注文が存在するか確認"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT 1 FROM items WHERE order_no = ?", (order_no,))
        return cursor.fetchone() is not None

    def get_item_list(self) -> list[dict[str, Any]]:
        """商品リストを取得（date 順）"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM items ORDER BY date")
        return [self._row_to_item(row) for row in cursor.fetchall()]

    def get_item_count(self) -> int:
        """商品数を取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM items")
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_last_item_by_filter(self, time_filter: str | int) -> dict[str, Any] | None:
        """指定した time_filter の最後の商品を取得"""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM items WHERE order_time_filter = ? ORDER BY date DESC LIMIT 1",
            (str(time_filter),),
        )
        row = cursor.fetchone()
        return self._row_to_item(row) if row else None

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        """Row を item dict に変換"""
        return {
            "no": row["order_no"],
            "date": self._parse_datetime(row["date"]),
            "name": row["name"],
            "url": row["url"],
            "asin": row["asin"],
            "count": row["count"] or 1,
            "price": row["price"] or 0,
            "category": json.loads(row["category"]) if row["category"] else [],
            "seller": row["seller"],
            "condition": row["condition"],
            "kind": row["kind"],
            "order_time_filter": self._parse_time_filter(row["order_time_filter"]),
            "order_page": row["order_page"],
        }

    @staticmethod
    def _parse_time_filter(value: str | None) -> int | str | None:
        """time_filter を適切な型に変換"""
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return value

    # --- 年ステータス ---
    def set_year_status(self, year: str | int, order_count: int | None = None, checked: bool | None = None) -> None:
        """年ステータスを設定"""
        conn = self._get_conn()
        year_str = str(year)

        # 既存レコードを取得
        cursor = conn.execute("SELECT order_count, checked FROM year_status WHERE year = ?", (year_str,))
        row = cursor.fetchone()

        if row:
            current_count = row["order_count"]
            current_checked = row["checked"]
        else:
            current_count = 0
            current_checked = 0

        new_count = order_count if order_count is not None else current_count
        new_checked = (1 if checked else 0) if checked is not None else current_checked

        conn.execute(
            "INSERT OR REPLACE INTO year_status (year, order_count, checked) VALUES (?, ?, ?)",
            (year_str, new_count, new_checked),
        )
        conn.commit()

    def get_year_order_count(self, year: str | int) -> int:
        """年の注文数を取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT order_count FROM year_status WHERE year = ?", (str(year),))
        row = cursor.fetchone()
        return row["order_count"] if row else 0

    def is_year_checked(self, year: str | int) -> bool:
        """年が処理済みか確認"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT checked FROM year_status WHERE year = ?", (str(year),))
        row = cursor.fetchone()
        return bool(row["checked"]) if row else False

    def get_year_list(self) -> list[int | str]:
        """年リストを取得"""
        value = self.get_metadata("year_list", "[]")
        year_list = json.loads(value)
        return [self._parse_time_filter(str(y)) for y in year_list]

    def set_year_list(self, year_list: list[int | str]) -> None:
        """年リストを設定"""
        self.set_metadata("year_list", json.dumps(year_list))

    def get_total_order_count(self) -> int:
        """全注文数を取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT SUM(order_count) FROM year_status")
        result = cursor.fetchone()
        return result[0] if result and result[0] else 0

    # --- ページステータス ---
    def set_page_checked(self, year: str | int, page: int, checked: bool = True) -> None:
        """ページの処理完了フラグを設定"""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO page_status (year, page, checked) VALUES (?, ?, ?)",
            (str(year), page, 1 if checked else 0),
        )
        conn.commit()

    def is_page_checked(self, year: str | int, page: int) -> bool:
        """ページが処理済みか確認"""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT checked FROM page_status WHERE year = ? AND page = ?",
            (str(year), page),
        )
        row = cursor.fetchone()
        return bool(row["checked"]) if row else False

    def clear_page_status(self, year: str | int) -> None:
        """指定年のページステータスをクリア"""
        conn = self._get_conn()
        conn.execute("DELETE FROM page_status WHERE year = ?", (str(year),))
        conn.commit()

    # --- メタデータ ---
    def get_metadata(self, key: str, default: str = "") -> str:
        """メタデータを取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_metadata(self, key: str, value: str) -> None:
        """メタデータを設定"""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()

    def get_last_modified(self) -> datetime.datetime:
        """最終更新日時を取得"""
        value = self.get_metadata("last_modified", "")
        if value:
            return self._parse_datetime(value) or datetime.datetime(1994, 7, 5)
        return datetime.datetime(1994, 7, 5)

    def set_last_modified(self, dt: datetime.datetime) -> None:
        """最終更新日時を設定"""
        self.set_metadata("last_modified", dt.isoformat())

    # --- ユーティリティ ---
    @staticmethod
    def _parse_datetime(value: str | None) -> datetime.datetime | None:
        """ISO 8601 文字列を datetime に変換"""
        if not value:
            return None
        try:
            dt = datetime.datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            return None


def open_database(db_path: pathlib.Path, schema_path: pathlib.Path) -> Database:
    """データベースを開く"""
    return Database(db_path, schema_path)
