#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import my_lib.browser
import my_lib.cui_progress

import amazhist.database

if TYPE_CHECKING:
    from my_lib.browser import Page

    import amazhist.item

import amazhist.config
import amazhist.database

# SQLite スキーマファイルのパス
_SQLITE_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


@dataclass
class Handle:
    config: amazhist.config.Config
    ignore_cache: bool = False
    target_year: int | None = None
    debug_mode: bool = False
    clear_profile_on_browser_error: bool = False
    _db: amazhist.database.Database | None = field(default=None, repr=False)
    _browser_manager: my_lib.browser.BrowserManager | None = field(default=None, init=False, repr=False)

    # プログレス管理
    _progress_manager: my_lib.cui_progress.ProgressManager = field(
        default_factory=lambda: my_lib.cui_progress.ProgressManager(
            color="#e47911",  # Amazon オレンジ
            title=" 🛒 アマゾン ",
        ),
        repr=False,
    )

    def __post_init__(self) -> None:
        self._prepare_directory()
        self._init_database()
        self._browser_manager = my_lib.browser.BrowserManager(
            my_lib.browser.BrowserProfile(
                name="Amazhist",
                data_dir=self.config.selenium_data_dir_path,
                # NOTE: bot 検出回避のため headful（Xvfb 上での実行を想定）。
                headless=False,
            ),
        )

        if self.ignore_cache:
            logging.info("キャッシュ無視モード: キャッシュを無視してデータを収集します")

    def _init_database(self) -> None:
        """データベースを初期化"""
        self._db = amazhist.database.open_database(
            self.config.cache_file_path,
            _SQLITE_SCHEMA_PATH,
        )
        # NOTE: 再開した時には巡回すべきなのでページステータスを削除しておく
        years_to_clear = [
            datetime.datetime.now().year,
            self.get_cache_last_modified().year,
        ]
        # 年指定モードでは、その年のページステータスもクリア
        if self.target_year is not None:
            years_to_clear.append(self.target_year)

        for time_filter in years_to_clear:
            self._db.clear_page_status(time_filter)

    @property
    def db(self) -> amazhist.database.Database:
        """データベースインスタンスを取得"""
        if self._db is None:
            raise RuntimeError("Database is not initialized")
        return self._db

    def pause_live(self) -> None:
        """Live 表示を一時停止（input() の前に呼び出す）"""
        self._progress_manager.pause_live()

    def resume_live(self) -> None:
        """Live 表示を再開（input() の後に呼び出す）"""
        self._progress_manager.resume_live()

    # --- ブラウザ関連 ---
    def get_page(self) -> Page:
        """ブラウザページを取得（必要に応じて起動）"""
        if self._browser_manager is None:
            raise RuntimeError("BrowserManager is not initialized")
        return self._browser_manager.get_page()

    @property
    def browser_manager(self) -> my_lib.browser.BrowserManager:
        if self._browser_manager is None:
            raise RuntimeError("BrowserManager is not initialized")
        return self._browser_manager

    def has_browser(self) -> bool:
        """ブラウザが起動済みか確認"""
        return self._browser_manager is not None and self._browser_manager.has_browser()

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

    def get_item_count_by_year(self, year: int) -> int:
        """指定年の商品数を取得"""
        return self.db.get_item_count_by_year(year)

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
        self._progress_manager.set_progress_bar(desc, total)

    def update_progress_bar(self, desc: str, advance: int = 1) -> None:
        """プログレスバーを進める（存在しない場合は何もしない）"""
        self._progress_manager.update_progress_bar(desc, advance)

    def get_progress_bar(self, desc: str) -> my_lib.cui_progress.ProgressTask:
        """プログレスバーを取得"""
        return self._progress_manager.get_progress_bar(desc)

    def has_progress_bar(self, desc: str) -> bool:
        """プログレスバーが存在するか確認"""
        return self._progress_manager.has_progress_bar(desc)

    def set_status(self, status: str, is_error: bool = False) -> None:
        """ステータスを更新"""
        self._progress_manager.set_status(status, is_error=is_error)

    # --- 終了処理 ---
    def quit_selenium(self) -> None:
        """ブラウザを終了"""
        if self._browser_manager is not None and self._browser_manager.has_browser():
            self.set_status("🛑 クローラを終了しています...")
            self._browser_manager.quit()

    def finish(self) -> None:
        self.quit_selenium()
        self._progress_manager.stop()
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

    def get_unresolved_error_count_by_year(self, year: int) -> int:
        """指定年の未解決エラー数を取得"""
        return self.db.get_unresolved_error_count_by_year(year)

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

    def get_failed_orders(self) -> list[amazhist.database.FailedOrderInfo]:
        """エラーが発生した注文情報を取得（年/ページ/インデックス情報を含む）"""
        return self.db.get_failed_orders()

    def get_failed_years(self) -> list[amazhist.database.ErrorLog]:
        """年単位のエラー（order_count_fallback）を取得"""
        return self.db.get_failed_years()

    def get_failed_category_items(self) -> list[amazhist.database.FailedCategoryItem]:
        """カテゴリ取得に失敗したアイテムを取得"""
        return self.db.get_failed_category_items()

    def update_item_category(self, url: str, category: list[str]) -> int:
        """アイテムのカテゴリを更新"""
        return self.db.update_item_category(url, category)

    def get_failed_thumbnail_items(self) -> list[amazhist.database.FailedThumbnailItem]:
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
