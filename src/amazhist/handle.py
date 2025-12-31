#!/usr/bin/env python3
from __future__ import annotations

import datetime
import functools
import logging
import os
import pathlib
import time
from typing import Any

import my_lib.selenium_util
import my_lib.serializer
import openpyxl.styles
import rich.console
import rich.live
import rich.progress
import rich.table
import rich.text
from selenium.webdriver.support.wait import WebDriverWait

import amazhist.const

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
        rich.text.Text(" アマゾン ", style=style),
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


def create(config):
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
    }

    _init_progress(handle)
    load_order_info(handle)
    prepare_directory(handle)

    return handle


def get_login_user(handle):
    return handle["config"]["login"]["amazon"]["user"]


def get_login_pass(handle):
    return handle["config"]["login"]["amazon"]["pass"]


def prepare_directory(handle):
    get_selenium_data_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_debug_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_thumb_dir_path(handle).mkdir(parents=True, exist_ok=True)

    get_caceh_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_captcha_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_excel_file_path(handle).parent.mkdir(parents=True, exist_ok=True)


def get_excel_font(handle):
    font_config = handle["config"]["output"]["excel"]["font"]
    return openpyxl.styles.Font(name=font_config["name"], size=font_config["size"])


def get_caceh_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["amazon"]["cache"]["order"])


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
    handle["order"]["item_list"].append(item)
    handle["order"]["order_no_stat"][item["no"]] = True


def get_item_list(handle):
    return sorted(handle["order"]["item_list"], key=lambda x: x["date"])


def get_last_item(handle, time_filter):
    return next(
        filter(lambda item: item["order_time_filter"] == time_filter, reversed(get_item_list(handle))), None
    )


def get_thumb_path(handle, item):
    if ("asin" not in item) or (item["asin"] is None):
        return None
    else:
        return get_thumb_dir_path(handle) / (item["asin"] + ".png")


def get_order_stat(handle, no):
    return no in handle["order"]["order_no_stat"]


def set_year_list(handle, year_list):
    handle["order"]["year_list"] = year_list


def set_order_count(handle, year, order_count):
    handle["order"]["year_count"][year] = order_count


def get_cache_last_modified(handle):
    return handle["order"]["last_modified"]


def get_order_count(handle, year):
    return handle["order"]["year_count"][year]


def get_total_order_count(handle):
    return functools.reduce(lambda a, b: a + b, handle["order"]["year_count"].values())


def get_year_list(handle):
    return handle["order"]["year_list"]


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
    if "selenium" in handle:
        handle["selenium"]["driver"].quit()
        handle.pop("selenium")

    live = handle["rich"]["live"]
    if live is not None:
        live.stop()
        handle["rich"]["live"] = None


def store_order_info(handle):
    handle["order"]["last_modified"] = datetime.datetime.now()

    my_lib.serializer.store(get_caceh_file_path(handle), handle["order"])


def set_page_checked(handle, year, page):
    if year in handle["order"]["page_stat"]:
        handle["order"]["page_stat"][year][page] = True
    else:
        handle["order"]["page_stat"][year] = {page: True}


def get_page_checked(handle, year, page):
    if (year in handle["order"]["page_stat"]) and (page in handle["order"]["page_stat"][year]):
        return handle["order"]["page_stat"][year][page]
    else:
        return False


def set_year_checked(handle, year):
    handle["order"]["year_stat"][year] = True
    store_order_info(handle)


def get_year_checked(handle, year):
    return year in handle["order"]["year_stat"]


def load_order_info(handle):
    handle["order"] = my_lib.serializer.load(
        get_caceh_file_path(handle),
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

    # NOTE: 再開した時には巡回すべきなので削除しておく
    for time_filter in [
        datetime.datetime.now().year,
        get_cache_last_modified(handle).year,
        amazhist.const.ARCHIVE_LABEL,
    ]:
        if time_filter in handle["order"]["page_stat"]:
            del handle["order"]["page_stat"][time_filter]


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]
