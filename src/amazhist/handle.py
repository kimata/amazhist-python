#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import os
import pathlib
import time
from typing import Any

import my_lib.selenium_util
import openpyxl.styles
import rich.console
import rich.live
import rich.progress
import rich.table
import rich.text
from selenium.webdriver.support.wait import WebDriverWait

import amazhist.const
import amazhist.database
import amazhist.migrate

# SQLite スキーマファイルのパス
SQLITE_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"

# ステータスバーの色定義
STATUS_STYLE_NORMAL = "bold #FFFFFF on #e47911"  # Amazon オレンジ
STATUS_STYLE_ERROR = "bold white on red"


class _DisplayRenderable:
    """Live 表示用の動的 renderable クラス"""

    def __init__(self, handle: dict) -> None:
        self._handle = handle

    def __rich__(self) -> Any:
        """Rich が描画時に呼び出すメソッド"""
        return _create_display(self._handle)


class ProgressTask:
    """Rich Progress のタスクを管理するクラス"""

    def __init__(self, handle: dict, task_id: rich.progress.TaskID, total: int) -> None:
        self._handle = handle
        self._task_id = task_id
        self._total = total
        self._count = 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def count(self) -> int:
        return self._count

    def update(self, advance: int = 1) -> None:
        """プログレスを進める"""
        self._count += advance
        if self._handle["rich"]["progress"] is not None:
            self._handle["rich"]["progress"].update(self._task_id, advance=advance)
            _refresh_display(self._handle)


def _init_progress(handle: dict) -> None:
    """Progress と Live を初期化"""
    console = handle["rich"]["console"]

    # 非TTY環境では Live を使用しない
    if not console.is_terminal:
        return

    handle["rich"]["progress"] = rich.progress.Progress(
        rich.progress.TextColumn("[bold]{task.description:<31}"),
        rich.progress.BarColumn(bar_width=None),
        rich.progress.TaskProgressColumn(),
        rich.progress.TextColumn("{task.completed:>5} / {task.total:<5}"),
        rich.progress.TimeElapsedColumn(),
        console=console,
        expand=True,
    )
    handle["rich"]["start_time"] = time.time()
    handle["rich"]["display_renderable"] = _DisplayRenderable(handle)
    handle["rich"]["live"] = rich.live.Live(
        handle["rich"]["display_renderable"],
        console=console,
        refresh_per_second=4,
    )
    handle["rich"]["live"].start()


def _create_status_bar(handle: dict) -> rich.table.Table:
    """ステータスバーを作成（左: タイトル、中央: 進捗、右: 時間）"""
    style = STATUS_STYLE_ERROR if handle["rich"]["status_is_error"] else STATUS_STYLE_NORMAL
    elapsed = time.time() - handle["rich"]["start_time"]
    elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

    # ターミナル幅を取得し、明示的に幅を制限
    # NOTE: tmux 環境では幅計算が実際と異なることがあるため、余裕を持たせる
    console = handle["rich"]["console"]
    terminal_width = console.width
    if os.environ.get("TMUX"):
        terminal_width -= 2

    table = rich.table.Table(
        show_header=False,
        show_edge=False,
        box=None,
        padding=0,
        expand=False,  # expand=False にして幅を明示的に制御
        width=terminal_width,  # ターミナル幅に制限
        style=style,
    )
    table.add_column("title", justify="left", ratio=1, no_wrap=True, overflow="ellipsis", style=style)
    table.add_column("status", justify="center", ratio=3, no_wrap=True, overflow="ellipsis", style=style)
    table.add_column("time", justify="right", ratio=1, no_wrap=True, overflow="ellipsis", style=style)

    table.add_row(
        rich.text.Text(" 🛒 アマゾン ", style=style),
        rich.text.Text(handle["rich"]["status_text"], style=style),
        rich.text.Text(f" {elapsed_str} ", style=style),
    )

    return table


def _create_display(handle: dict) -> Any:
    """表示内容を作成"""
    status_bar = _create_status_bar(handle)
    progress = handle["rich"]["progress"]
    if progress is not None and len(progress.tasks) > 0:
        return rich.console.Group(status_bar, progress)
    return status_bar


def _refresh_display(handle: dict) -> None:
    """表示を強制的に再描画"""
    live = handle["rich"]["live"]
    if live is not None:
        live.refresh()


def pause_live(handle: dict) -> None:
    """Live 表示を一時停止（input() の前に呼び出す）"""
    live = handle["rich"]["live"]
    if live is not None:
        live.stop()


def resume_live(handle: dict) -> None:
    """Live 表示を再開（input() の後に呼び出す）"""
    live = handle["rich"]["live"]
    if live is not None:
        live.start()


def create(config, force_mode=False):
    handle = {
        "rich": {
            "console": rich.console.Console(),
            "progress": None,
            "live": None,
            "start_time": time.time(),
            "status_text": "",
            "status_is_error": False,
            "display_renderable": None,
        },
        "progress_bar": {},
        "config": config,
        "db": None,
        "force_mode": force_mode,
    }

    prepare_directory(handle)
    _init_progress(handle)
    _init_database(handle)

    if force_mode:
        logging.info("強制収集モード: キャッシュを無視してデータを収集します")

    return handle


def _init_database(handle: dict) -> None:
    """データベースを初期化（必要に応じてマイグレーションを実行）"""
    cache_path = get_cache_file_path(handle)

    # pickle から SQLite へのマイグレーションが必要か確認
    if amazhist.migrate.needs_migration(cache_path):
        logging.info("pickle ファイルを検出しました。SQLite へ移行します...")
        if not amazhist.migrate.migrate_pickle_to_sqlite(cache_path, cache_path, SQLITE_SCHEMA_PATH):
            raise RuntimeError("マイグレーションに失敗しました")

    # データベースを開く
    handle["db"] = amazhist.database.open_database(cache_path, SQLITE_SCHEMA_PATH)

    # NOTE: 再開した時には巡回すべきなのでページステータスを削除しておく
    db = handle["db"]
    for time_filter in [
        datetime.datetime.now().year,
        get_cache_last_modified(handle).year,
        amazhist.const.ARCHIVE_LABEL,
    ]:
        db.clear_page_status(time_filter)


def get_login_user(handle):
    return handle["config"]["login"]["amazon"]["user"]


def get_login_pass(handle):
    return handle["config"]["login"]["amazon"]["pass"]


def prepare_directory(handle):
    get_selenium_data_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_debug_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_thumb_dir_path(handle).mkdir(parents=True, exist_ok=True)

    get_cache_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_captcha_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_excel_file_path(handle).parent.mkdir(parents=True, exist_ok=True)


def get_excel_font(handle):
    font_config = handle["config"]["output"]["excel"]["font"]
    return openpyxl.styles.Font(name=font_config["name"], size=font_config["size"])


def get_cache_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["amazon"]["cache"]["order"])


# NOTE: 後方互換性のためのエイリアス（typo）
def get_caceh_file_path(handle):
    return get_cache_file_path(handle)


def get_excel_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["output"]["excel"]["table"])


def get_thumb_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["amazon"]["cache"]["thumb"])


def get_selenium_data_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["selenium"])


def get_debug_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["debug"])


def get_captcha_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["output"]["captcha"])


def get_selenium_driver(handle):
    if "selenium" in handle:
        return (handle["selenium"]["driver"], handle["selenium"]["wait"])
    else:
        driver = my_lib.selenium_util.create_driver("Amazhist", get_selenium_data_dir_path(handle))
        wait = WebDriverWait(driver, 5)

        my_lib.selenium_util.clear_cache(driver)

        handle["selenium"] = {
            "driver": driver,
            "wait": wait,
        }

        return (driver, wait)


def record_item(handle, item):
    """商品を記録"""
    db: amazhist.database.Database = handle["db"]
    db.upsert_item(item)


def get_item_list(handle):
    """商品リストを取得（date順）"""
    db: amazhist.database.Database = handle["db"]
    return db.get_item_list()


def get_last_item(handle, time_filter):
    """指定した time_filter の最後の商品を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_last_item_by_filter(time_filter)


def get_thumb_path(handle, item):
    if ("asin" not in item) or (item["asin"] is None):
        return None
    else:
        return get_thumb_dir_path(handle) / (item["asin"] + ".png")


def get_order_stat(handle, no):
    """注文が処理済みか確認（force_mode時は常にFalse）"""
    if handle.get("force_mode", False):
        return False
    db: amazhist.database.Database = handle["db"]
    return db.exists_order(no)


def set_year_list(handle, year_list):
    """年リストを設定"""
    db: amazhist.database.Database = handle["db"]
    db.set_year_list(year_list)


def set_order_count(handle, year, order_count):
    """年の注文数を設定"""
    db: amazhist.database.Database = handle["db"]
    db.set_year_status(year, order_count=order_count)


def get_cache_last_modified(handle):
    """キャッシュの最終更新日時を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_last_modified()


def get_order_count(handle, year):
    """年の注文数を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_year_order_count(year)


def get_total_order_count(handle):
    """全注文数を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_total_order_count()


def get_year_list(handle):
    """年リストを取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_year_list()


def set_progress_bar(handle, desc, total):
    """プログレスバーを作成"""
    progress = handle["rich"]["progress"]

    if progress is None:
        # 非TTY環境でもダミーのProgressTaskを作成（KeyError防止）
        handle["progress_bar"][desc] = ProgressTask(handle, rich.progress.TaskID(-1), total)
        return

    task_id = progress.add_task(desc, total=total)
    handle["progress_bar"][desc] = ProgressTask(handle, task_id, total)
    _refresh_display(handle)


def set_status(handle, status, is_error=False):
    """ステータスを更新"""
    handle["rich"]["status_text"] = status
    handle["rich"]["status_is_error"] = is_error

    console = handle["rich"]["console"]

    # 非TTY環境では logging で出力
    if not console.is_terminal:
        if is_error:
            logging.error(status)
        else:
            logging.info(status)
        return

    _refresh_display(handle)


def finish(handle):
    """終了処理"""
    if "selenium" in handle:
        handle["selenium"]["driver"].quit()
        handle.pop("selenium")

    live = handle["rich"]["live"]
    if live is not None:
        live.stop()
        handle["rich"]["live"] = None

    # データベースを閉じる
    if handle["db"] is not None:
        handle["db"].close()
        handle["db"] = None


def store_order_info(handle):
    """注文情報を保存（最終更新日時を更新）"""
    db: amazhist.database.Database = handle["db"]
    db.set_last_modified(datetime.datetime.now())


def set_page_checked(handle, year, page):
    """ページの処理完了フラグを設定"""
    db: amazhist.database.Database = handle["db"]
    db.set_page_checked(year, page, True)


def get_page_checked(handle, year, page):
    """ページが処理済みか確認（force_mode時は常にFalse）"""
    if handle.get("force_mode", False):
        return False
    db: amazhist.database.Database = handle["db"]
    return db.is_page_checked(year, page)


def set_year_checked(handle, year):
    """年の処理完了フラグを設定"""
    db: amazhist.database.Database = handle["db"]
    db.set_year_status(year, checked=True)
    store_order_info(handle)


def get_year_checked(handle, year):
    """年が処理済みか確認（force_mode時は常にFalse）"""
    if handle.get("force_mode", False):
        return False
    db: amazhist.database.Database = handle["db"]
    return db.is_year_checked(year)


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]


# --- エラーログ ---
def record_error(
    handle,
    url: str,
    error_type: str,
    context: str,
    message: str | None = None,
    order_no: str | None = None,
    item_name: str | None = None,
) -> int:
    """エラーを記録

    Args:
        handle: アプリケーションハンドル
        url: エラーが発生したURL
        error_type: エラーの種類（"timeout", "parse_error", "not_found" など）
        context: エラーのコンテキスト（"order", "item", "thumbnail", "category" など）
        message: エラーメッセージ
        order_no: 関連する注文番号
        item_name: 関連する商品名

    Returns:
        挿入されたエラーログのID
    """
    db: amazhist.database.Database = handle["db"]
    return db.record_error(url, error_type, context, message, order_no, item_name)


def get_unresolved_errors(handle, context: str | None = None) -> list:
    """未解決のエラー一覧を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_unresolved_errors(context)


def get_all_errors(handle, limit: int = 100) -> list:
    """全エラー一覧を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_all_errors(limit)


def get_error_count(handle, resolved: bool | None = None) -> int:
    """エラー件数を取得"""
    db: amazhist.database.Database = handle["db"]
    return db.get_error_count(resolved)


def mark_error_resolved(handle, error_id: int) -> None:
    """エラーを解決済みにする"""
    db: amazhist.database.Database = handle["db"]
    db.mark_error_resolved(error_id)


def clear_old_errors(handle, days: int = 30) -> int:
    """古い解決済みエラーを削除"""
    db: amazhist.database.Database = handle["db"]
    return db.clear_old_errors(days)
