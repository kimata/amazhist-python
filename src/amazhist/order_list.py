#!/usr/bin/env python3
"""
注文リストの取得・解析を行う関数群

注文一覧ページから注文情報を収集し、個別の注文詳細を取得します。
"""

from __future__ import annotations

import datetime
import logging
import math
import time

from selenium.webdriver.common.by import By

import amazhist.const
import amazhist.handle
import amazhist.order
import amazhist.parser

# プログレスバーのラベル
STATUS_ORDER_ITEM_ALL = "[収集] 全注文"
_STATUS_ORDER_ITEM_BY_TARGET = "[収集] {target}"

# 今年の巡回を早期終了するための連続キャッシュヒット閾値
_CONSECUTIVE_CACHE_HITS_THRESHOLD = 5


def _gen_target_text(year: int) -> str:
    return f"{year}年"


def _gen_status_label_by_year(year: int) -> str:
    return _STATUS_ORDER_ITEM_BY_TARGET.format(target=_gen_target_text(year))


def _safe_update_progress(handle: amazhist.handle.Handle, year: int, advance: int = 1) -> None:
    """プログレスバーが存在する場合のみ更新

    リトライ時など、プログレスバーが作成されていない状態でも
    安全に呼び出せるようにするためのヘルパー関数。
    """
    year_label = _gen_status_label_by_year(year)
    if handle.has_progress_bar(year_label):
        handle.get_progress_bar(year_label).update(advance)
    if handle.has_progress_bar(STATUS_ORDER_ITEM_ALL):
        handle.get_progress_bar(STATUS_ORDER_ITEM_ALL).update(advance)


def _get_progress_count(handle: amazhist.handle.Handle, year: int) -> int:
    """プログレスバーの現在カウントを取得（存在しない場合は 0）"""
    year_label = _gen_status_label_by_year(year)
    if handle.has_progress_bar(year_label):
        return handle.get_progress_bar(year_label).count
    return 0


def fetch_by_year_page(
    handle: amazhist.handle.Handle,
    year: int,
    page: int,
    visit_url_func,
    keep_logged_on_func,
    get_caller_name_func,
    gen_hist_url_func,
    gen_order_url_func,
    is_shutdown_requested_func,
    retry: int = 0,
    can_early_exit: bool = False,
    consecutive_cache_hits: int = 0,
) -> tuple[bool, bool, int, int]:
    """指定年・ページの注文リストを取得

    Args:
        handle: アプリケーションハンドル
        year: 年
        page: ページ番号
        visit_url_func: URL訪問関数
        keep_logged_on_func: ログイン維持関数
        get_caller_name_func: 呼び出し元名取得関数
        gen_hist_url_func: 履歴URL生成関数
        gen_order_url_func: 注文URL生成関数
        is_shutdown_requested_func: シャットダウン要求確認関数
        retry: リトライ回数
        can_early_exit: 早期終了が可能か（今年の条件を満たす場合）
        consecutive_cache_hits: 前ページからの連続キャッシュヒット数

    Returns:
        (スキップされたか, 最終ページか, 注文カード数, 連続キャッシュヒット数)
        注文カード数が0より大きければページ取得自体は成功
    """
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = handle.get_selenium_driver()

    total_page = math.ceil(handle.get_order_count(year) / amazhist.const.ORDER_COUNT_PER_PAGE)

    handle.set_status(
        f"🔍 注文履歴を解析しています... {_gen_target_text(year)} {page}/{total_page} ページ",
    )

    visit_url_func(handle, gen_hist_url_func(year, page), get_caller_name_func())
    keep_logged_on_func(handle)

    logging.info(f"{year}年 {page}/{total_page} ページの注文を確認しています")
    logging.info(f"URL: {driver.current_url}")

    is_skipped = False
    order_list = []
    order_card_count = len(driver.find_elements(By.XPATH, ORDER_XPATH))

    # 注文カードが見つからなかった場合のチェック
    if order_card_count == 0:
        expected_on_page = min(
            handle.get_order_count(year) - _get_progress_count(handle, year),
            amazhist.const.ORDER_COUNT_PER_PAGE,
        )
        if expected_on_page > 0:
            logging.warning(
                f"注文カードが見つかりませんでした（{year}年 {page}ページ、期待: {expected_on_page}件）"
            )
            handle.record_or_update_error(
                url=gen_hist_url_func(year, page),
                error_type=amazhist.const.ERROR_TYPE_PARSE,
                context="order",
                message=f"注文カードが見つかりませんでした（期待: {expected_on_page}件）",
                order_year=year,
                order_page=page,
            )
            # 期待していた分のプログレスを更新
            _safe_update_progress(handle, year, expected_on_page)
            return (True, page >= total_page, 0, 0)  # 注文カード0件

    # ページレベルのエラーチェック（ループの前に1回だけ実行）
    if (
        len(
            driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "a-alert-content")]//span[contains(text(), "問題が発生")]',
            )
        )
        != 0
    ):
        if retry < amazhist.const.RETRY_FETCH:
            logging.warning("問題が発生しました。再試行します...")
            time.sleep(amazhist.const.RETRY_DELAY_DEFAULT)
            return fetch_by_year_page(
                handle,
                year,
                page,
                visit_url_func,
                keep_logged_on_func,
                get_caller_name_func,
                gen_hist_url_func,
                gen_order_url_func,
                is_shutdown_requested_func,
                retry=retry + 1,
                can_early_exit=can_early_exit,
                consecutive_cache_hits=consecutive_cache_hits,
            )
        else:
            # リトライ上限に達した場合は全ての注文カードの分プログレスを更新
            logging.warning(f"リトライ上限に達しました。{order_card_count}件の注文をスキップします")
            _safe_update_progress(handle, year, order_card_count)
            return (True, page >= total_page, order_card_count, 0)

    for i in range(order_card_count):
        order_xpath = ORDER_XPATH + f"[{i + 1}]"

        try:
            # キャンセル済みの注文はスキップ（プログレスバーは更新する）
            if (
                len(
                    driver.find_elements(
                        By.XPATH,
                        order_xpath
                        + "//div[contains(@class, 'yohtmlc-shipment-status-primaryText')]"
                        + "//span[contains(text(), 'キャンセル済み')]",
                    )
                )
                != 0
            ):
                no = driver.find_element(
                    By.XPATH,
                    order_xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[@dir='ltr']",
                ).text
                logging.info(f"キャンセル済みの注文をスキップしました: {no}")
                # キャンセル済みでも「確認した」としてプログレスを更新
                _safe_update_progress(handle, year)
                continue

            # 日付を取得
            date_text = driver.find_element(
                By.XPATH,
                order_xpath
                + "//li[contains(@class, 'order-header__header-list-item')]"
                + "//span[contains(@class, 'a-color-secondary') and contains(@class, 'aok-break-word')]",
            ).text
            date = amazhist.parser.parse_date(date_text)

            # 注文番号を取得
            order_no_elems = driver.find_elements(
                By.XPATH,
                order_xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[@dir='ltr']",
            )
            if not order_no_elems:
                logging.warning(f"注文番号が取得できませんでした（{year}年 {page}ページ {i + 1}番目）")
                handle.record_or_update_error(
                    url=gen_hist_url_func(year, page),
                    error_type=amazhist.const.ERROR_TYPE_NO_ORDER_NO,
                    context="order",
                    message=f"注文番号が取得できませんでした（{i + 1}番目）",
                    order_no=None,
                    order_year=year,
                    order_page=page,
                    order_index=i,
                )
                _safe_update_progress(handle, year)
                continue

            no = order_no_elems[0].text

            # order-details リンクを取得
            order_details_xpath = (
                order_xpath
                + "//li[contains(@class, 'yohtmlc-order-level-connections')]"
                + "//a[contains(@href, 'order-details')]"
            )
            order_details_elems = driver.find_elements(By.XPATH, order_details_xpath)

            if order_details_elems:
                url = order_details_elems[0].get_attribute("href")
                if url is None:
                    # リンク要素はあるが href が取得できない場合 → URLを構築
                    logging.info(f"詳細リンクの URL が取得できないため、URLを構築します: {no}")
                    url = gen_order_url_func(no)
            else:
                # 詳細リンクがない場合 → URLを構築
                logging.info(f"詳細リンクがないため、URLを構築して取得を試みます: {no}")
                url = gen_order_url_func(no)

            order_list.append(amazhist.order.Order(date=date, no=no, url=url, time_filter=year, page=page))
        except Exception as e:
            # 注文カード解析中に予期しない例外が発生した場合
            logging.warning(
                f"注文カードの解析中にエラーが発生しました（{year}年 {page}ページ {i + 1}番目）: {e}"
            )
            handle.record_or_update_error(
                url=gen_hist_url_func(year, page),
                error_type=amazhist.const.ERROR_TYPE_PARSE,
                context="order",
                message=f"注文カードの解析中にエラーが発生しました（{i + 1}番目）: {e}",
                order_no=None,
                order_year=year,
                order_page=page,
                order_index=i,
            )
            is_skipped = True
            # 例外発生時はプログレスバーを更新
            _safe_update_progress(handle, year)

    time.sleep(1)

    for order in order_list:
        try:
            if not handle.get_order_stat(order.no):
                is_skipped |= not amazhist.order.fetch_item_list(
                    handle,
                    order,
                    visit_url_func,
                    keep_logged_on_func,
                    get_caller_name_func,
                )
                # 新規取得したので連続キャッシュヒットをリセット
                consecutive_cache_hits = 0
            else:
                logging.info(
                    "注文処理済み: {date} - {no} [キャッシュ]".format(
                        date=order.date.strftime("%Y-%m-%d"), no=order.no
                    )
                )
                # キャッシュヒットをカウント
                consecutive_cache_hits += 1

                # 早期終了判定
                if can_early_exit and consecutive_cache_hits >= _CONSECUTIVE_CACHE_HITS_THRESHOLD:
                    logging.info(
                        f"{year}年: {consecutive_cache_hits}件連続してキャッシュ済みの注文だったため、"
                        "巡回を打ち切りました"
                    )
                    # 残りの注文分のプログレスを更新
                    remaining = len(order_list) - order_list.index(order) - 1
                    _safe_update_progress(handle, year, remaining)
                    # 全ページを処理済みにマーク
                    for j in range(total_page):
                        handle.set_page_checked(year, j + 1)
                    return (is_skipped, True, order_card_count, consecutive_cache_hits)
        except Exception as e:
            # 予期しない例外が発生してもプログレスバーは更新する
            logging.warning(f"注文の処理中に予期しないエラーが発生しました: {order.no} ({e})")
            handle.record_or_update_error(
                url=order.url,
                error_type=amazhist.const.ERROR_TYPE_FETCH,
                context="order",
                message=str(e),
                order_no=order.no,
                order_year=order.time_filter,
                order_page=order.page,
            )
            is_skipped = True
            # エラー発生時は連続キャッシュヒットをリセット
            consecutive_cache_hits = 0
        finally:
            # 成功・失敗に関わらずプログレスバーを更新
            _safe_update_progress(handle, year)

        # デバッグモードでは1件だけ処理して終了
        if handle.debug_mode:
            logging.info("デバッグモード: 1件の注文を処理したため終了します")
            return (is_skipped, True, order_card_count, consecutive_cache_hits)

        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested_func():
            logging.info("シャットダウンリクエストにより処理を中断します")
            handle.store_order_info()
            return (True, True, order_card_count, consecutive_cache_hits)

    return (is_skipped, page >= total_page, order_card_count, consecutive_cache_hits)


def skip_by_year_page(handle: amazhist.handle.Handle, year: int, page: int) -> bool:
    """ページをスキップ（キャッシュ済みの場合）

    Args:
        handle: アプリケーションハンドル
        year: 年
        page: ページ番号

    Returns:
        最終ページか
    """
    logging.info(f"{year}年 {page} ページの注文をスキップしました [キャッシュ]")
    incr_order = min(
        handle.get_order_count(year) - _get_progress_count(handle, year),
        amazhist.const.ORDER_COUNT_PER_PAGE,
    )
    _safe_update_progress(handle, year, incr_order)

    # NOTE: これ，状況によっては最終ページで成り立たないので，良くない
    return incr_order != amazhist.const.ORDER_COUNT_PER_PAGE


def fetch_by_year(
    handle: amazhist.handle.Handle,
    year: int,
    visit_url_func,
    keep_logged_on_func,
    get_caller_name_func,
    gen_hist_url_func,
    gen_order_url_func,
    is_shutdown_requested_func,
    start_page: int = 1,
) -> None:
    """指定年の注文リストを取得

    Args:
        handle: アプリケーションハンドル
        year: 年
        visit_url_func: URL訪問関数
        keep_logged_on_func: ログイン維持関数
        get_caller_name_func: 呼び出し元名取得関数
        gen_hist_url_func: 履歴URL生成関数
        gen_order_url_func: 注文URL生成関数
        is_shutdown_requested_func: シャットダウン要求確認関数
        start_page: 開始ページ
    """
    visit_url_func(handle, gen_hist_url_func(year, start_page), get_caller_name_func())

    keep_logged_on_func(handle)

    year_list = handle.get_year_list()

    logging.info(f"{year}年の注文を確認しています ({year_list.index(year) + 1}/{len(year_list)})")

    handle.set_progress_bar(
        _gen_status_label_by_year(year),
        handle.get_order_count(year),
    )

    # 今年の早期終了条件を判定
    current_year = datetime.datetime.now().year
    can_early_exit = (
        year == current_year
        and handle.get_year_checked(year)
        and handle.get_item_count_by_year(year) > 0
        and handle.get_unresolved_error_count_by_year(year) == 0
    )

    page = start_page
    is_skipped = False
    consecutive_cache_hits = 0
    while True:
        if not handle.get_page_checked(year, page):
            is_skipped_page, is_last, _, consecutive_cache_hits = fetch_by_year_page(
                handle,
                year,
                page,
                visit_url_func,
                keep_logged_on_func,
                get_caller_name_func,
                gen_hist_url_func,
                gen_order_url_func,
                is_shutdown_requested_func,
                can_early_exit=can_early_exit,
                consecutive_cache_hits=consecutive_cache_hits,
            )

            if not is_skipped_page:
                handle.set_page_checked(year, page)

            is_skipped |= is_skipped_page
            time.sleep(1)
        else:
            is_last = skip_by_year_page(handle, year, page)
            # ページスキップ時は連続カウントをリセット（既存キャッシュは新規取得扱い）
            consecutive_cache_hits = 0

        handle.store_order_info()

        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested_func():
            break

        if is_last:
            break

        # デバッグモードでは1ページだけ処理して終了
        if handle.debug_mode:
            break

        page += 1

    if not is_skipped and not is_shutdown_requested_func() and not handle.debug_mode:
        handle.set_year_checked(year)


def gen_status_label_by_year(year: int) -> str:
    """年のプログレスバーラベルを生成（外部公開用）"""
    return _gen_status_label_by_year(year)
