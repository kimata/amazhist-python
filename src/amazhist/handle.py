#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import os
import pathlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import my_lib.selenium_util
import rich.console
import rich.live
import rich.progress
import rich.table
import rich.text
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support.wait

import amazhist.database

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait

    import amazhist.item

import amazhist.config
import amazhist.database

# SQLite スキーマファイルのパス
SQLITE_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"

# ステータスバーの色定義
STATUS_STYLE_NORMAL = "bold #FFFFFF on #e47911"  # Amazon オレンジ
STATUS_STYLE_ERROR = "bold white on red"


@dataclass
class SeleniumInfo:
    driver: selenium.webdriver.remote.webdriver.WebDriver
    wait: selenium.webdriver.support.wait.WebDriverWait


class _DisplayRenderable:
    """Live 表示用の動的 renderable クラス"""

    def __init__(self, handle: Handle) -> None:
        self._handle = handle

    def __rich__(self) -> Any:
        """Rich が描画時に呼び出すメソッド"""
        return self._handle._create_display()


class _NullProgress:
    """非TTY環境用の何もしない Progress（Null Object パターン）"""

    def __init__(self) -> None:
        self.tasks: list[rich.progress.Task] = []

    def add_task(self, description: str, total: float | None = None) -> rich.progress.TaskID:
        return rich.progress.TaskID(0)

    def update(self, task_id: rich.progress.TaskID, advance: float = 1) -> None:
        pass

    def __rich__(self) -> rich.text.Text:
        """Rich プロトコル対応（空のテキストを返す）"""
        return rich.text.Text("")


class _NullLive:
    """非TTY環境用の何もしない Live（Null Object パターン）"""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def refresh(self) -> None:
        pass


class ProgressTask:
    """Rich Progress のタスクを管理するクラス"""

    def __init__(self, handle: Handle, task_id: rich.progress.TaskID, total: int) -> None:
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
        self._handle._progress.update(self._task_id, advance=advance)
        self._handle._refresh_display()


@dataclass
class Handle:
    config: amazhist.config.Config
    ignore_cache: bool = False
    debug_mode: bool = False
    clear_profile_on_browser_error: bool = False
    selenium: SeleniumInfo | None = None
    _db: amazhist.database.Database | None = field(default=None, repr=False)

    # Rich 関連
    _console: rich.console.Console = field(default_factory=rich.console.Console)
    _progress: rich.progress.Progress | _NullProgress = field(default_factory=_NullProgress, repr=False)
    _live: rich.live.Live | _NullLive = field(default_factory=_NullLive, repr=False)
    _start_time: float = field(default_factory=time.time)
    _status_text: str = ""
    _status_is_error: bool = False
    _display_renderable: _DisplayRenderable | None = field(default=None, repr=False)

    # プログレスタスク管理
    progress_bar: dict[str, ProgressTask] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._prepare_directory()
        self._init_database()
        self._init_progress()

        if self.ignore_cache:
            logging.info("キャッシュ無視モード: キャッシュを無視してデータを収集します")

    def _init_database(self) -> None:
        """データベースを初期化"""
        self._db = amazhist.database.open_database(
            self.config.cache_file_path,
            SQLITE_SCHEMA_PATH,
        )
        # NOTE: 再開した時には巡回すべきなのでページステータスを削除しておく
        for time_filter in [
            datetime.datetime.now().year,
            self.get_cache_last_modified().year,
        ]:
            self._db.clear_page_status(time_filter)

    @property
    def db(self) -> amazhist.database.Database:
        """データベースインスタンスを取得"""
        if self._db is None:
            raise RuntimeError("Database is not initialized")
        return self._db

    def _init_progress(self) -> None:
        """Progress と Live を初期化"""
        # 非TTY環境では Live を使用しない
        if not self._console.is_terminal:
            return

        self._progress = rich.progress.Progress(
            rich.progress.TextColumn("[bold]{task.description:<31}"),
            rich.progress.BarColumn(bar_width=None),
            rich.progress.TaskProgressColumn(),
            rich.progress.TextColumn("{task.completed:>5} / {task.total:<5}"),
            rich.progress.TextColumn("経過:"),
            rich.progress.TimeElapsedColumn(),
            rich.progress.TextColumn("残り:"),
            rich.progress.TimeRemainingColumn(),
            console=self._console,
            expand=True,
        )
        self._start_time = time.time()
        self._display_renderable = _DisplayRenderable(self)
        self._live = rich.live.Live(
            self._display_renderable,
            console=self._console,
            refresh_per_second=4,
        )
        self._live.start()

    def _create_status_bar(self) -> rich.table.Table:
        """ステータスバーを作成（左: タイトル、中央: 進捗、右: 時間）"""
        style = STATUS_STYLE_ERROR if self._status_is_error else STATUS_STYLE_NORMAL
        elapsed = time.time() - self._start_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

        # ターミナル幅を取得し、明示的に幅を制限
        # NOTE: tmux 環境では幅計算が実際と異なることがあるため、余裕を持たせる
        terminal_width = self._console.width
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
            rich.text.Text(self._status_text, style=style),
            rich.text.Text(f" {elapsed_str} ", style=style),
        )

        return table

    def _create_display(self) -> Any:
        """表示内容を作成"""
        status_bar = self._create_status_bar()
        # NullProgress の場合 tasks は常に空なのでこの条件で十分
        if len(self._progress.tasks) > 0:
            return rich.console.Group(status_bar, self._progress)
        return status_bar

    def _refresh_display(self) -> None:
        """表示を強制的に再描画"""
        self._live.refresh()

    def pause_live(self) -> None:
        """Live 表示を一時停止（input() の前に呼び出す）"""
        self._live.stop()

    def resume_live(self) -> None:
        """Live 表示を再開（input() の後に呼び出す）"""
        self._live.start()

    # --- Selenium 関連 ---
    def get_selenium_driver(self) -> tuple[WebDriver, WebDriverWait]:
        if self.selenium is not None:
            return (self.selenium.driver, self.selenium.wait)

        try:
            driver = my_lib.selenium_util.create_driver(
                "Amazhist", self.config.selenium_data_dir_path, use_subprocess=False
            )
            wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

            my_lib.selenium_util.clear_cache(driver)

            self.selenium = SeleniumInfo(driver=driver, wait=wait)

            return (driver, wait)
        except Exception as e:
            if self.clear_profile_on_browser_error:
                my_lib.selenium_util.delete_profile("Amazhist", self.config.selenium_data_dir_path)
            raise my_lib.selenium_util.SeleniumError(f"Selenium の起動に失敗しました: {e}") from e

    # --- ログイン情報 ---
    def get_login_user(self) -> str:
        return self.config.login.amazon.user

    def get_login_pass(self) -> str:
        return self.config.login.amazon.password

    # --- 商品関連 ---
    def record_item(self, item: amazhist.item.Item) -> None:
        """商品を記録"""
        self.db.upsert_item(item)

    def get_item_list(self) -> list[amazhist.item.Item]:
        """商品リストを取得（date順）"""
        return self.db.get_item_list()

    def get_last_item(self, time_filter: str | int) -> amazhist.item.Item | None:
        """指定した time_filter の最後の商品を取得"""
        return self.db.get_last_item_by_filter(time_filter)

    def get_thumb_path(self, asin: str | None) -> pathlib.Path | None:
        """サムネイル画像のパスを取得"""
        if asin is None:
            return None
        return self.config.thumb_dir_path / (asin + ".png")

    def get_order_stat(self, no: str) -> bool:
        """注文が処理済みか確認（ignore_cache時は常にFalse）"""
        if self.ignore_cache:
            return False
        return self.db.exists_order(no)

    # --- 年ステータス ---
    def set_year_list(self, year_list: list[int]) -> None:
        """年リストを設定"""
        self.db.set_year_list(year_list)

    def get_year_list(self) -> list[int]:
        """年リストを取得"""
        return self.db.get_year_list()

    def set_order_count(self, year: int, order_count: int) -> None:
        """年の注文数を設定"""
        self.db.set_year_status(year, order_count=order_count)

    def get_order_count(self, year: int) -> int:
        """年の注文数を取得"""
        return self.db.get_year_order_count(year)

    def get_total_order_count(self) -> int:
        """全注文数を取得"""
        return self.db.get_total_order_count()

    def get_cache_last_modified(self) -> datetime.datetime:
        """キャッシュの最終更新日時を取得"""
        return self.db.get_last_modified()

    # --- ページステータス ---
    def set_page_checked(self, year: int, page: int) -> None:
        """ページの処理完了フラグを設定"""
        self.db.set_page_checked(year, page, True)

    def get_page_checked(self, year: int, page: int) -> bool:
        """ページが処理済みか確認（ignore_cache時は常にFalse）"""
        if self.ignore_cache:
            return False
        return self.db.is_page_checked(year, page)

    def set_year_checked(self, year: int) -> None:
        """年の処理完了フラグを設定"""
        self.db.set_year_status(year, checked=True)
        self.store_order_info()

    def get_year_checked(self, year: int) -> bool:
        """年が処理済みか確認（ignore_cache時は常にFalse）"""
        if self.ignore_cache:
            return False
        return self.db.is_year_checked(year)

    # --- メタデータ保存 ---
    def store_order_info(self) -> None:
        """注文情報を保存（最終更新日時を更新）"""
        self.db.set_last_modified(datetime.datetime.now())

    # --- プログレスバー ---
    def set_progress_bar(self, desc: str, total: int) -> None:
        """プログレスバーを作成"""
        task_id = self._progress.add_task(desc, total=total)
        self.progress_bar[desc] = ProgressTask(self, task_id, total)
        self._refresh_display()

    def get_progress_bar(self, desc: str) -> ProgressTask:
        return self.progress_bar[desc]

    def has_progress_bar(self, desc: str) -> bool:
        """プログレスバーが存在するか確認"""
        return desc in self.progress_bar

    def set_status(self, status: str, is_error: bool = False) -> None:
        """ステータスを更新"""
        self._status_text = status
        self._status_is_error = is_error

        # 非TTY環境では logging で出力
        if not self._console.is_terminal:
            if is_error:
                logging.error(status)
            else:
                logging.info(status)
            return

        self._refresh_display()

    # --- 終了処理 ---
    def quit_selenium(self) -> None:
        """Selenium ドライバーを終了"""
        if self.selenium is not None:
            self.set_status("🛑 クローラを終了しています...")
            my_lib.selenium_util.quit_driver_gracefully(self.selenium.driver, wait_sec=5)
            self.selenium = None

    def finish(self) -> None:
        self.quit_selenium()

        self._live.stop()
        self._live = _NullLive()

        if self._db is not None:
            self._db.close()
            self._db = None

    # --- エラーログ ---
    def record_error(
        self,
        url: str,
        error_type: str,
        context: str,
        message: str | None = None,
        order_no: str | None = None,
        item_name: str | None = None,
        order_year: int | None = None,
        order_page: int | None = None,
        order_index: int | None = None,
    ) -> int:
        """エラーを記録"""
        return self.db.record_error(
            url, error_type, context, message, order_no, item_name, order_year, order_page, order_index
        )

    def record_or_update_error(
        self,
        url: str,
        error_type: str,
        context: str,
        message: str | None = None,
        order_no: str | None = None,
        item_name: str | None = None,
        order_year: int | None = None,
        order_page: int | None = None,
        order_index: int | None = None,
    ) -> int:
        """エラーを記録または更新（既存エラーがあれば retry_count を増加）"""
        return self.db.record_or_update_error(
            url, error_type, context, message, order_no, item_name, order_year, order_page, order_index
        )

    def get_unresolved_errors(self, context: str | None = None) -> list[amazhist.database.ErrorLog]:
        """未解決のエラー一覧を取得"""
        return self.db.get_unresolved_errors(context)

    def get_all_errors(self, limit: int = 100) -> list[amazhist.database.ErrorLog]:
        """全エラー一覧を取得"""
        return self.db.get_all_errors(limit)

    def get_error_by_id(self, error_id: int) -> amazhist.database.ErrorLog | None:
        """IDでエラーを取得"""
        return self.db.get_error_by_id(error_id)

    def get_error_count(self, resolved: bool | None = None) -> int:
        """エラー件数を取得"""
        return self.db.get_error_count(resolved)

    def mark_error_resolved(self, error_id: int) -> None:
        """エラーを解決済みにする"""
        self.db.mark_error_resolved(error_id)

    def clear_old_errors(self, days: int = 30) -> int:
        """古い解決済みエラーを削除"""
        return self.db.clear_old_errors(days)

    def get_failed_order_numbers(self) -> list[str]:
        """エラーが発生した注文番号を取得"""
        return self.db.get_failed_order_numbers()

    def get_failed_orders(self) -> list[dict[str, Any]]:
        """エラーが発生した注文情報を取得（年/ページ/インデックス情報を含む）"""
        return self.db.get_failed_orders()

    def get_failed_years(self) -> list[amazhist.database.ErrorLog]:
        """年単位のエラー（order_count_fallback）を取得"""
        return self.db.get_failed_years()

    def get_failed_category_items(self) -> list[dict[str, Any]]:
        """カテゴリ取得に失敗したアイテムを取得"""
        return self.db.get_failed_category_items()

    def update_item_category(self, url: str, category: list[str]) -> int:
        """アイテムのカテゴリを更新"""
        return self.db.update_item_category(url, category)

    def get_failed_thumbnail_items(self) -> list[dict[str, Any]]:
        """サムネイル取得に失敗したアイテムを取得"""
        return self.db.get_failed_thumbnail_items()

    def get_thumbnail_asin_by_error_id(self, error_id: int) -> str | None:
        """エラーIDからサムネイルの ASIN を取得"""
        return self.db.get_thumbnail_asin_by_error_id(error_id)

    def mark_errors_resolved_by_order_no(self, order_no: str) -> int:
        """指定注文番号のエラーを全て解決済みにする"""
        return self.db.mark_errors_resolved_by_order_no(order_no)

    def _prepare_directory(self) -> None:
        self.config.selenium_data_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.debug_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.thumb_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.captcha_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.excel_file_path.parent.mkdir(parents=True, exist_ok=True)
