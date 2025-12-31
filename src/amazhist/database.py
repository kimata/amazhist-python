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
    def _parse_time_filter(value: str | None) -> int | None:
        """time_filter を適切な型に変換"""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None

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

    def get_year_list(self) -> list[int]:
        """年リストを取得"""
        value = self.get_metadata("year_list", "[]")
        year_list = json.loads(value)
        return [x for x in (self._parse_time_filter(str(y)) for y in year_list) if x is not None]

    def set_year_list(self, year_list: list[int]) -> None:
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

    # --- エラーログ ---
    def record_error(
        self,
        url: str,
        error_type: str,
        context: str,
        message: str | None = None,
        order_no: str | None = None,
        item_name: str | None = None,
    ) -> int:
        """エラーを記録

        Args:
            url: エラーが発生したURL
            error_type: エラーの種類（"timeout", "parse_error", "not_found" など）
            context: エラーのコンテキスト（"order", "item", "thumbnail", "category" など）
            message: エラーメッセージ
            order_no: 関連する注文番号
            item_name: 関連する商品名

        Returns:
            挿入されたエラーログのID
        """
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO error_log (url, error_type, error_message, context, order_no, item_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                error_type,
                message,
                context,
                order_no,
                item_name,
                datetime.datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def get_unresolved_errors(self, context: str | None = None) -> list[dict[str, Any]]:
        """未解決のエラー一覧を取得

        Args:
            context: フィルタするコンテキスト（None の場合は全て）

        Returns:
            エラーログのリスト
        """
        conn = self._get_conn()
        if context:
            cursor = conn.execute(
                "SELECT * FROM error_log WHERE resolved = 0 AND context = ? ORDER BY created_at DESC",
                (context,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM error_log WHERE resolved = 0 ORDER BY created_at DESC"
            )
        return [self._row_to_error(row) for row in cursor.fetchall()]

    def get_failed_order_numbers(self) -> list[str]:
        """エラーが発生した注文番号を取得

        未解決のエラーで context が "order" のものから注文番号を取得します。

        Returns:
            注文番号のリスト
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT DISTINCT order_no FROM error_log WHERE resolved = 0 AND context = 'order' AND order_no IS NOT NULL"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_failed_category_items(self) -> list[dict[str, Any]]:
        """カテゴリ取得に失敗したアイテムを取得

        未解決のエラーで context が "category" のものから URL を取得し、
        対応するアイテム情報を返します。

        Returns:
            アイテム情報のリスト（url, error_id を含む）
        """
        conn = self._get_conn()
        cursor = conn.execute(
            """
            SELECT e.id as error_id, e.url, i.order_no, i.name, i.asin
            FROM error_log e
            LEFT JOIN items i ON e.url = i.url
            WHERE e.resolved = 0 AND e.context = 'category'
            """
        )
        return [
            {
                "error_id": row[0],
                "url": row[1],
                "order_no": row[2],
                "name": row[3],
                "asin": row[4],
            }
            for row in cursor.fetchall()
        ]

    def update_item_category(self, url: str, category: list[str]) -> int:
        """アイテムのカテゴリを更新

        Args:
            url: アイテムのURL
            category: カテゴリのリスト

        Returns:
            更新した件数
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE items SET category = ? WHERE url = ?",
            (json.dumps(category, ensure_ascii=False), url),
        )
        conn.commit()
        return cursor.rowcount

    def get_failed_thumbnail_items(self) -> list[dict[str, Any]]:
        """サムネイル取得に失敗したアイテムを取得

        未解決のエラーで context が "thumbnail" のものから URL を取得し、
        対応するアイテム情報を返します。

        Returns:
            アイテム情報のリスト（error_id, url, asin, item_name を含む）
        """
        conn = self._get_conn()
        cursor = conn.execute(
            """
            SELECT e.id as error_id, e.url as thumb_url, e.item_name, i.asin, i.url as item_url
            FROM error_log e
            LEFT JOIN items i ON e.item_name = i.name
            WHERE e.resolved = 0 AND e.context = 'thumbnail'
            """
        )
        return [
            {
                "error_id": row[0],
                "thumb_url": row[1],
                "name": row[2],
                "asin": row[3],
                "item_url": row[4],
            }
            for row in cursor.fetchall()
        ]

    def get_all_errors(self, limit: int = 100) -> list[dict[str, Any]]:
        """全エラー一覧を取得（最新順）

        Args:
            limit: 取得件数の上限

        Returns:
            エラーログのリスト
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM error_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_error(row) for row in cursor.fetchall()]

    def mark_error_resolved(self, error_id: int) -> None:
        """エラーを解決済みにする

        Args:
            error_id: エラーログのID
        """
        conn = self._get_conn()
        conn.execute("UPDATE error_log SET resolved = 1 WHERE id = ?", (error_id,))
        conn.commit()

    def mark_errors_resolved_by_url(self, url: str) -> int:
        """指定URLのエラーを全て解決済みにする

        Args:
            url: URL

        Returns:
            解決済みにしたエラーの件数
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE error_log SET resolved = 1 WHERE url = ? AND resolved = 0",
            (url,),
        )
        conn.commit()
        return cursor.rowcount

    def mark_errors_resolved_by_order_no(self, order_no: str) -> int:
        """指定注文番号のエラーを全て解決済みにする

        Args:
            order_no: 注文番号

        Returns:
            解決済みにしたエラーの件数
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE error_log SET resolved = 1 WHERE order_no = ? AND resolved = 0",
            (order_no,),
        )
        conn.commit()
        return cursor.rowcount

    def increment_retry_count(self, error_id: int) -> None:
        """リトライ回数をインクリメント

        Args:
            error_id: エラーログのID
        """
        conn = self._get_conn()
        conn.execute("UPDATE error_log SET retry_count = retry_count + 1 WHERE id = ?", (error_id,))
        conn.commit()

    def clear_old_errors(self, days: int = 30) -> int:
        """古い解決済みエラーを削除

        Args:
            days: 何日前より古いエラーを削除するか

        Returns:
            削除した件数
        """
        conn = self._get_conn()
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        cursor = conn.execute(
            "DELETE FROM error_log WHERE resolved = 1 AND created_at < ?",
            (cutoff,),
        )
        conn.commit()
        return cursor.rowcount

    def get_error_count(self, resolved: bool | None = None) -> int:
        """エラー件数を取得

        Args:
            resolved: True=解決済み, False=未解決, None=全て

        Returns:
            件数
        """
        conn = self._get_conn()
        if resolved is None:
            cursor = conn.execute("SELECT COUNT(*) FROM error_log")
        else:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM error_log WHERE resolved = ?",
                (1 if resolved else 0,),
            )
        result = cursor.fetchone()
        return result[0] if result else 0

    def _row_to_error(self, row: sqlite3.Row) -> dict[str, Any]:
        """Row を error dict に変換"""
        return {
            "id": row["id"],
            "url": row["url"],
            "error_type": row["error_type"],
            "error_message": row["error_message"],
            "context": row["context"],
            "order_no": row["order_no"],
            "item_name": row["item_name"],
            "created_at": self._parse_datetime(row["created_at"]),
            "retry_count": row["retry_count"],
            "resolved": bool(row["resolved"]),
        }

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
