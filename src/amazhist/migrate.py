#!/usr/bin/env python3
"""pickle から SQLite へのマイグレーション"""

from __future__ import annotations

import datetime
import logging
import pathlib
import shutil

import my_lib.serializer

import amazhist.database


def is_pickle_file(path: pathlib.Path) -> bool:
    """ファイルが pickle 形式かどうかを判定"""
    if not path.exists() or path.stat().st_size < 2:
        return False

    # SQLite ファイルでないことを確認
    if amazhist.database.is_sqlite_file(path):
        return False

    # pickle のマジックバイトをチェック（概ね 0x80 で始まる）
    with path.open("rb") as f:
        header = f.read(2)
    return len(header) >= 1 and header[0] == 0x80


def migrate_pickle_to_sqlite(
    pickle_path: pathlib.Path,
    db_path: pathlib.Path,
    schema_path: pathlib.Path,
) -> bool:
    """pickle ファイルを SQLite に変換

    Args:
        pickle_path: 元の pickle ファイルパス
        db_path: 変換先の SQLite ファイルパス（通常は pickle_path と同じ）
        schema_path: SQLite スキーマファイルパス

    Returns:
        変換が成功したか
    """
    if not pickle_path.exists():
        return False

    if not is_pickle_file(pickle_path):
        logging.debug("ファイルは pickle 形式ではありません: %s", pickle_path)
        return False

    logging.info("pickle から SQLite へのマイグレーションを開始します...")

    # pickle データを読み込み
    try:
        order_data = my_lib.serializer.load(
            pickle_path,
            {
                "year_list": [],
                "year_count": {},
                "year_stat": {},
                "page_stat": {},
                "item_list": [],
                "order_no_stat": {},
                "last_modified": datetime.datetime(1994, 7, 5),
            },
        )
    except Exception as e:
        logging.error("pickle ファイルの読み込みに失敗しました: %s", e)
        return False

    # バックアップを作成
    backup_path = pickle_path.with_suffix(".pickle.bak")
    try:
        shutil.copy2(pickle_path, backup_path)
        logging.info("バックアップを作成しました: %s", backup_path)
    except Exception as e:
        logging.error("バックアップの作成に失敗しました: %s", e)
        return False

    # 元のファイルを削除（SQLite は新規作成する必要がある）
    pickle_path.unlink()

    # SQLite データベースを作成
    try:
        db = amazhist.database.open_database(db_path, schema_path)

        # 商品データを移行
        item_count = 0
        for item in order_data.get("item_list", []):
            db.upsert_item(item)
            item_count += 1

        # 年リストを移行
        year_list = order_data.get("year_list", [])
        if year_list:
            db.set_year_list(year_list)

        # 年ごとのステータスを移行
        year_count = order_data.get("year_count", {})
        year_stat = order_data.get("year_stat", {})

        for year, count in year_count.items():
            checked = year in year_stat
            db.set_year_status(year, order_count=count, checked=checked)

        # ページステータスを移行
        page_stat = order_data.get("page_stat", {})
        for year, pages in page_stat.items():
            for page, checked in pages.items():
                if checked:
                    db.set_page_checked(year, page, True)

        # 最終更新日時を移行
        last_modified = order_data.get("last_modified", datetime.datetime(1994, 7, 5))
        db.set_last_modified(last_modified)

        db.close()

        logging.info(
            "マイグレーションが完了しました: %d 件の商品, %d 年分のデータ",
            item_count,
            len(year_list),
        )
        return True

    except Exception as e:
        logging.error("SQLite への変換に失敗しました: %s", e)
        # 失敗した場合はバックアップを復元
        if backup_path.exists():
            if db_path.exists():
                db_path.unlink()
            shutil.copy2(backup_path, pickle_path)
            logging.info("バックアップから復元しました")
        return False


def needs_migration(cache_path: pathlib.Path) -> bool:
    """マイグレーションが必要か判定"""
    if not cache_path.exists():
        return False
    return is_pickle_file(cache_path)


if __name__ == "__main__":
    import sys

    import my_lib.logger

    my_lib.logger.init("migrate", level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m amazhist.migrate <pickle_file>")
        sys.exit(1)

    pickle_file = pathlib.Path(sys.argv[1])
    schema_file = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"

    if migrate_pickle_to_sqlite(pickle_file, pickle_file, schema_file):
        print("マイグレーションが完了しました")
    else:
        print("マイグレーションに失敗しました")
        sys.exit(1)
