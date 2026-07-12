#!/usr/bin/env python3
"""
Amazon の購入履歴情報を取得します．

Usage:
  crawler.py [-c CONFIG] [-y YEAR] [-s PAGE]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -y YEAR       : 購入年．
  -s PAGE       : 開始ページ．[default: 1]
"""

from __future__ import annotations

import datetime
import inspect
import logging
import re
import time
import traceback
from typing import Any

import my_lib.graceful_shutdown
import my_lib.selenium_util
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

import amazhist.config
import amazhist.const
import amazhist.database
import amazhist.exceptions
import amazhist.handle
import amazhist.item
import amazhist.order
import amazhist.order_list
import amazhist.parser

_STATUS_ORDER_COUNT = "[収集] 年数"


def get_caller_name(depth: int = 1) -> str:
    """呼び出し元の関数名を取得

    Args:
        depth: スキップするフレーム数（デフォルト1）
               他のモジュールから呼び出す場合は depth=2 を指定
    """
    frame = inspect.currentframe()
    for _ in range(depth + 1):  # +1 は get_caller_name 自身のフレーム
        if frame is None:
            return "unknown"
        frame = frame.f_back
    if frame is None:
        return "unknown"
    return frame.f_code.co_name


# Graceful shutdown 用のエイリアス（my_lib.graceful_shutdown を使用）
def is_shutdown_requested() -> bool:
    """シャットダウンがリクエストされているかを返す"""
    return my_lib.graceful_shutdown.is_shutdown_requested()


def _setup_graceful_shutdown(handle: amazhist.handle.Handle) -> None:
    """グレースフルシャットダウン用のシグナルハンドラを設定"""
    my_lib.graceful_shutdown.set_live_display(handle)
    my_lib.graceful_shutdown.setup_signal_handler()
    my_lib.graceful_shutdown.reset_shutdown_flag()


def _wait_for_loading(handle: amazhist.handle.Handle, sec: float = 2) -> None:
    time.sleep(sec)


def _resolve_captcha(handle: amazhist.handle.Handle) -> None:
    driver, _wait = handle.get_selenium_driver()

    logging.info("画像認証の解決を試みます")

    def _try_solve():
        captcha_img_path = handle.config.captcha_file_path
        captcha_png_data = driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png

        logging.info(f"画像を保存しました: {captcha_img_path}")

        with captcha_img_path.open("wb") as f:
            f.write(captcha_png_data)

        captcha_text = input(f"「{captcha_img_path}」に書かれているテキストを入力してください: ")

        driver.find_element(By.XPATH, '//input[@name="cvf_captcha_input"]').send_keys(captcha_text.strip())
        driver.find_element(By.XPATH, '//input[@type="submit"]').click()

        _wait_for_loading(handle)

        if my_lib.selenium_util.xpath_exists(driver, '//input[@name="cvf_captcha_input"]'):
            dump_id = amazhist.const.generate_debug_dump_id()
            my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)
            raise amazhist.exceptions.CaptchaError("CAPTCHA未解決")

    try:
        my_lib.selenium_util.with_retry(
            _try_solve,
            max_retries=amazhist.const.RETRY_CAPTCHA,
            exceptions=(amazhist.exceptions.CaptchaError,),
            on_retry=lambda attempt, e: logging.info("画像認証の解決を再試行します"),
        )
    except amazhist.exceptions.CaptchaError:
        logging.error("画像認証の解決を諦めました")
        raise amazhist.exceptions.CaptchaError("画像認証を解決できませんでした．") from None


def _execute_login(handle: amazhist.handle.Handle) -> None:
    driver, _wait = handle.get_selenium_driver()

    time.sleep(1)

    if my_lib.selenium_util.xpath_exists(driver, '//input[@id="ap_email" and @type!="hidden"]'):
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(handle.get_login_user())

        if my_lib.selenium_util.xpath_exists(driver, '//input[@id="continue"]'):
            driver.find_element(By.XPATH, '//input[@id="continue"]').click()
            _wait_for_loading(handle)

    if my_lib.selenium_util.xpath_exists(driver, '//input[@id="ap_password"]'):
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').send_keys(handle.get_login_pass())

    if my_lib.selenium_util.xpath_exists(driver, '//input[@id="rememberMe"]') and not driver.find_element(
        By.XPATH, '//input[@name="rememberMe"]'
    ).get_attribute("checked"):
        driver.find_element(By.XPATH, '//input[@name="rememberMe"]').click()

    driver.find_element(By.XPATH, '//input[@id="signInSubmit"]').click()

    _wait_for_loading(handle)

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="cvf_captcha_input"]'):
        _resolve_captcha(handle)


def _is_signin_page(driver: Any) -> bool:
    """サインインページに居るかを URL で判定

    ページタイトルは言語設定により変化する（例: "Amazon Sign-In"）ため、URL パスで判定する。
    """
    return amazhist.const.SIGNIN_URL_PATH in driver.current_url


def _keep_logged_on(handle: amazhist.handle.Handle) -> None:
    driver, _wait = handle.get_selenium_driver()

    if not _is_signin_page(driver):
        return

    logging.info("ログインを試みます")

    def _try_login():
        _execute_login(handle)
        if _is_signin_page(driver):
            dump_id = amazhist.const.generate_debug_dump_id()
            my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)
            raise amazhist.exceptions.LoginError("ログイン失敗")

    try:
        my_lib.selenium_util.with_retry(
            _try_login,
            max_retries=amazhist.const.RETRY_LOGIN,
            exceptions=(amazhist.exceptions.LoginError,),
            on_retry=lambda attempt, e: logging.info("ログインを再試行します"),
        )
        logging.info("ログインに成功しました")
    except amazhist.exceptions.LoginError:
        logging.error("ログインを諦めました")
        raise amazhist.exceptions.LoginError("ログインに失敗しました．") from None


def gen_hist_url(year: int, page: int) -> str:
    """履歴ページのURLを生成"""
    return amazhist.const.HIST_URL_BY_YEAR.format(
        year=year, start=amazhist.const.ORDER_COUNT_PER_PAGE * (page - 1)
    )


def gen_order_url(no: str) -> str:
    """注文詳細ページのURLを生成"""
    return amazhist.const.HIST_URL_BY_ORDER_NO.format(no=no)


def visit_url(handle: amazhist.handle.Handle, url: str, caller_name: str) -> None:
    """URLにアクセス

    TimeoutException が発生した場合はリトライします。
    """
    driver, _wait = handle.get_selenium_driver()

    def _load_page():
        driver.get(url)
        _wait_for_loading(handle)

    my_lib.selenium_util.with_retry(
        _load_page,
        max_retries=amazhist.const.RETRY_URL_ACCESS,
        delay=amazhist.const.RETRY_DELAY_TIMEOUT,
        exceptions=(TimeoutException,),
        on_retry=lambda attempt, e: logging.warning(
            f"タイムアウト。リトライします ({attempt}/{amazhist.const.RETRY_URL_ACCESS})"
        ),
    )


def _fetch_order_list_by_year_page(
    handle: amazhist.handle.Handle, year: int, page: int, retry: int = 0
) -> tuple[bool, bool, int, int]:
    """指定年・ページの注文リストを取得（order_list.fetch_by_year_page のラッパー）"""
    return amazhist.order_list.fetch_by_year_page(
        handle,
        year,
        page,
        visit_url,
        _keep_logged_on,
        get_caller_name,
        gen_hist_url,
        gen_order_url,
        is_shutdown_requested,
        retry,
    )


def _fetch_year_list(handle: amazhist.handle.Handle) -> list[int]:
    """年リストを取得"""
    driver, _wait = handle.get_selenium_driver()

    visit_url(handle, amazhist.const.HIST_URL, get_caller_name())

    _keep_logged_on(handle)

    driver.find_element(
        By.XPATH, "//form[@action='/your-orders/orders']//span[contains(@class, 'a-dropdown-prompt')]"
    ).click()

    _wait_for_loading(handle)

    year_str_list = [
        elem.text
        for elem in driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'a-popover-wrapper')]//li",
        )
    ]

    year_list = list(
        reversed([int(label.replace("年", "")) for label in year_str_list if re.match(r"\d+年", label)])
    )

    handle.set_year_list(year_list)

    return year_list


def _fetch_order_list_by_year(handle: amazhist.handle.Handle, year: int, start_page: int = 1) -> None:
    """指定年の注文リストを取得（order_list.fetch_by_year のラッパー）"""
    amazhist.order_list.fetch_by_year(
        handle,
        year,
        visit_url,
        _keep_logged_on,
        get_caller_name,
        gen_hist_url,
        gen_order_url,
        is_shutdown_requested,
        start_page,
    )


def _fetch_order_count_by_year(handle: amazhist.handle.Handle, year: int) -> int:
    handle.set_status(
        f"🔍 注文件数を調べています... {year}年",
    )

    return amazhist.order.parse_order_count(handle, year)


def _fetch_order_count(handle: amazhist.handle.Handle) -> None:
    year_list = handle.get_year_list()

    logging.info("注文件数を収集しています")

    handle.set_progress_bar(_STATUS_ORDER_COUNT, len(year_list))

    total_count = 0
    for year in year_list:
        if year >= handle.get_cache_last_modified().year:
            count = _fetch_order_count_by_year(handle, year)
            handle.set_order_count(year, count)
            logging.info(f"{year}年: {count:4,} 件")
        else:
            count = handle.get_order_count(year)
            logging.info(f"{year}年: {count:4,} 件 [キャッシュ]")

        total_count += count
        handle.get_progress_bar(_STATUS_ORDER_COUNT).update()

    logging.info(f"合計注文数: {total_count:,} 件")

    handle.store_order_info()


def _fetch_order_list_all_year(handle: amazhist.handle.Handle) -> None:
    # Selenium ドライバーが起動していることを確認
    handle.get_selenium_driver()

    year_list = _fetch_year_list(handle)
    _fetch_order_count(handle)

    # 年指定モードではその年の注文数のみをプログレスバーに設定
    if handle.target_year is not None:
        if handle.target_year in year_list:
            total_count = handle.get_order_count(handle.target_year)
        else:
            logging.warning(f"指定された年 {handle.target_year} は注文履歴に存在しません")
            return
    else:
        total_count = handle.get_total_order_count()

    handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, total_count)

    for year in year_list:
        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            break

        # 年指定モードでは、指定年以外をスキップ
        if handle.target_year is not None and year != handle.target_year:
            continue

        if (
            (year == datetime.datetime.now().year)
            or (year == handle.get_cache_last_modified().year)
            or (not handle.get_year_checked(year))
            or (handle.target_year is not None)  # 年指定モードでは常に処理
        ):
            _fetch_order_list_by_year(handle, year)

            # デバッグモードでは1年だけ処理して終了
            if handle.debug_mode:
                break
        else:
            logging.info(
                f"{year}年の注文処理済み ({year_list.index(year) + 1}/{len(year_list)}) [キャッシュ]"
            )
            handle.get_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL).update(
                handle.get_order_count(year)
            )


def fetch_order_list(handle: amazhist.handle.Handle) -> None:
    """注文履歴を収集

    Args:
        handle: アプリケーションハンドル
    """
    handle.set_status("🤖 巡回ロボットの準備をします...")
    driver, _wait = handle.get_selenium_driver()

    _setup_graceful_shutdown(handle)

    handle.set_status("📥 注文履歴の収集を開始します...")

    try:
        _fetch_order_list_all_year(handle)
    except Exception:
        if not is_shutdown_requested():
            dump_id = amazhist.const.generate_debug_dump_id()
            my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)
        raise

    if is_shutdown_requested():
        handle.set_status("🛑 注文履歴の収集を中断しました")
    else:
        handle.set_status("✅ 注文履歴の収集が完了しました")


def _retry_order_from_list_page(
    handle: amazhist.handle.Handle, error_info: amazhist.database.FailedOrderInfo
) -> bool:
    """注文一覧ページから詳細リンクを取得して再取得を試みる

    Args:
        handle: アプリケーションハンドル
        error_info: エラー情報

    Returns:
        成功した場合 True
    """
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'
    driver, _wait = handle.get_selenium_driver()

    year = error_info.order_year
    page = error_info.order_page
    index = error_info.order_index
    order_no = error_info.order_no

    # year または page が None の場合は処理できない
    if year is None or page is None:
        logging.warning("注文の年/ページ情報がありません")
        return False

    # 注文一覧ページにアクセス
    visit_url(handle, gen_hist_url(year, page), get_caller_name())
    _keep_logged_on(handle)

    # 注文番号がない場合（NO_ORDER_NO エラー）はインデックスで注文を特定
    order_xpath: str | None = None

    if order_no is None and index is not None:
        order_elems = driver.find_elements(By.XPATH, ORDER_XPATH)
        if index >= len(order_elems):
            logging.warning(
                f"注文が見つかりませんでした（インデックス超過）: {year}年 {page}ページ {index + 1}番目"
            )
            return False

        order_xpath = ORDER_XPATH + f"[{index + 1}]"

        # 注文番号を取得
        order_no_elems = driver.find_elements(
            By.XPATH,
            order_xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[@dir='ltr']",
        )
        if not order_no_elems:
            logging.warning(f"注文番号が取得できませんでした: {year}年 {page}ページ {index + 1}番目")
            return False

        order_no = order_no_elems[0].text
    else:
        # 注文番号から注文を特定
        order_elems = driver.find_elements(By.XPATH, ORDER_XPATH)
        for i in range(len(order_elems)):
            xpath = ORDER_XPATH + f"[{i + 1}]"
            no_elems = driver.find_elements(
                By.XPATH,
                xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[@dir='ltr']",
            )
            if no_elems and no_elems[0].text == order_no:
                order_xpath = xpath
                break

    if order_xpath is None or order_no is None:
        logging.warning(f"注文が見つかりませんでした: {order_no}")
        return False

    # 日付を取得
    date_text = driver.find_element(
        By.XPATH,
        order_xpath
        + "//li[contains(@class, 'order-header__header-list-item')]"
        + "//span[contains(@class, 'a-color-secondary') and contains(@class, 'aok-break-word')]",
    ).text
    date = amazhist.parser.parse_date(date_text)

    # 詳細リンクを取得
    order_details_xpath = (
        order_xpath
        + "//li[contains(@class, 'yohtmlc-order-level-connections')]"
        + "//a[contains(@href, 'order-details')]"
    )
    order_details_elems = driver.find_elements(By.XPATH, order_details_xpath)

    url: str
    if order_details_elems:
        url_attr = order_details_elems[0].get_attribute("href")
        if url_attr:
            logging.info(f"詳細リンクを取得しました: {order_no}")
            url = url_attr
        else:
            logging.info(f"詳細リンクの URL が取得できないため、URLを構築します: {order_no}")
            url = gen_order_url(order_no)
    else:
        logging.info(f"詳細リンクがないため、URLを構築して取得を試みます: {order_no}")
        url = gen_order_url(order_no)

    # 注文を取得
    order = amazhist.order.Order(
        date=date,
        no=order_no,
        url=url,
        time_filter=year,
        page=page,
    )

    visit_url(handle, order.url, get_caller_name())
    _keep_logged_on(handle)

    return amazhist.order.parse_order(handle, order)


def _retry_failed_years(handle: amazhist.handle.Handle) -> tuple[int, int]:
    """年単位のエラー（order_count_fallback）を再巡回

    注文件数要素が見つからずフォールバックで注文カードを数えた年を再巡回し、
    年ステータスをリセットして再収集します。

    Returns:
        (成功件数, 失敗件数)
    """
    failed_years = handle.get_failed_years()

    if not failed_years:
        logging.info("再巡回対象の年はありません")
        return (0, 0)

    # 対象年をユニークにする
    years = sorted({error.order_year for error in failed_years if error.order_year})

    if not years:
        logging.info("再巡回対象の年はありません")
        return (0, 0)

    logging.info(f"年単位の再巡回を行います: {years}")

    handle.set_progress_bar("[再取得] 年", len(years))

    success_count = 0
    fail_count = 0

    for year in years:
        if is_shutdown_requested():
            break

        logging.info(f"{year}年の再巡回を開始します")

        try:
            # 年ステータスをリセット（再収集を可能にする）
            handle.db.reset_year_status(year)

            # 年単位の収集を実行
            _fetch_order_list_by_year(handle, year)

            # 該当年のエラーを解決済みにする
            for error in failed_years:
                if error.order_year == year:
                    handle.mark_error_resolved(error.id)

            logging.info(f"{year}年の再巡回が完了しました")
            success_count += 1
        except Exception as e:
            logging.warning(f"{year}年の再巡回をスキップしました: {e}")
            fail_count += 1

        handle.get_progress_bar("[再取得] 年").update()
        time.sleep(1)

    return (success_count, fail_count)


def _retry_single_order(
    handle: amazhist.handle.Handle, error_info: amazhist.database.FailedOrderInfo
) -> bool:
    """単一の注文エラーを再取得

    Args:
        handle: Handle インスタンス
        error_info: エラー情報

    Returns:
        成功した場合は True
    """
    order_no = error_info.order_no
    order_year = error_info.order_year
    order_page = error_info.order_page
    order_index = error_info.order_index
    current_year = datetime.datetime.now().year

    display_name = order_no or f"{order_year}年 {order_page}ページ"

    # order_no も order_index もない場合はページ全体を再巡回
    if order_no is None and order_index is None and order_year is not None and order_page is not None:
        logging.info(f"ページ全体を再巡回します: {display_name}")
        is_skipped, _, order_card_count, _ = _fetch_order_list_by_year_page(handle, order_year, order_page)
        # order_card_count > 0 ならページ取得自体は成功
        # 個別の注文でエラーがあっても、それらは別途エラーとして記録されている
        if order_card_count > 0 and not is_skipped:
            # ページ処理完了を記録（次回の通常実行時にスキップされるようにする）
            handle.set_page_checked(order_year, order_page)
        return order_card_count > 0

    if order_year is not None and order_year != current_year:
        # 過去の年: 注文一覧ページから詳細リンクを取得して再取得
        logging.info(f"過去の年の注文を一覧ページから再取得します: {display_name}")
        return _retry_order_from_list_page(handle, error_info)

    # 現在の年または年情報がない場合
    if order_no:
        # 構築したURLで直接取得
        logging.info(f"構築したURLで直接取得します: {order_no}")
        order = amazhist.order.Order(
            date=datetime.datetime.now(),
            no=order_no,
            url=gen_order_url(order_no),
            time_filter=order_year,
            page=order_page,
        )

        visit_url(handle, order.url, get_caller_name())
        _keep_logged_on(handle)

        return amazhist.order.parse_order(handle, order)

    if order_year is not None:
        # 現在の年で注文番号がない場合も一覧ページから再取得を試みる
        logging.info(f"現在の年の注文を一覧ページから再取得します: {display_name}")
        return _retry_order_from_list_page(handle, error_info)

    return False


def _retry_failed_orders(handle: amazhist.handle.Handle) -> tuple[int, int]:
    """エラーが発生した注文を再取得

    現在の年のエラー: 構築したURLで直接取得（新規注文でページ位置がずれる可能性があるため）
    過去の年のエラー: 注文一覧ページに戻って詳細リンクを取得し、なければ構築したURLで取得

    Returns:
        (成功件数, 失敗件数)
    """
    failed_orders = handle.get_failed_orders()

    if not failed_orders:
        logging.info("再取得対象の注文はありません")
        return (0, 0)

    logging.info(f"エラーが発生した注文を再取得します: {len(failed_orders)} 件")

    handle.set_progress_bar("[再取得] 注文", len(failed_orders))

    success_count = 0
    fail_count = 0

    for error_info in failed_orders:
        if is_shutdown_requested():
            break

        order_no = error_info.order_no
        error_id = error_info.error_id
        display_name = order_no or f"{error_info.order_year}年 {error_info.order_page}ページ"

        handle.set_status(f"🔄 注文を再取得しています: {display_name}")

        try:
            success = _retry_single_order(handle, error_info)

            if success:
                handle.mark_error_resolved(error_id)
                if order_no:
                    handle.mark_errors_resolved_by_order_no(order_no)
                logging.info(f"注文の再取得に成功しました: {display_name}")
                success_count += 1
            else:
                logging.warning(f"注文の再取得をスキップしました: {display_name}")
                fail_count += 1
        except Exception as e:
            logging.warning(f"注文の再取得をスキップしました: {display_name} ({e})")
            fail_count += 1

        handle.get_progress_bar("[再取得] 注文").update()
        time.sleep(1)

    return (success_count, fail_count)


def _retry_failed_categories(handle: amazhist.handle.Handle) -> tuple[int, int]:
    """カテゴリ取得に失敗したアイテムを再取得

    Returns:
        (成功件数, 失敗件数)
    """
    failed_items = handle.get_failed_category_items()

    if not failed_items:
        logging.info("再取得対象のカテゴリはありません")
        return (0, 0)

    logging.info(f"カテゴリ取得に失敗したアイテムを再取得します: {len(failed_items)} 件")

    handle.set_progress_bar("[再取得] カテゴリ", len(failed_items))

    success_count = 0
    fail_count = 0

    for item in failed_items:
        if is_shutdown_requested():
            break

        name = item.name or "不明"
        url = item.url

        handle.set_status(f"🔄 カテゴリを再取得しています: {name[:30]}")

        try:
            # record_error=False でエラー記録を抑制（既にエラーログに記録されているため）
            category = amazhist.item.fetch_item_category(handle, url, record_error=False)
            if category:
                handle.update_item_category(url, category)
                handle.mark_error_resolved(item.error_id)
                logging.info(f"カテゴリの再取得に成功しました: {name}")
                success_count += 1
            else:
                logging.warning(f"カテゴリの再取得をスキップしました（空）: {name}")
                fail_count += 1
        except Exception as e:
            logging.warning(f"カテゴリの再取得をスキップしました: {name} ({e})")
            fail_count += 1

        handle.get_progress_bar("[再取得] カテゴリ").update()
        time.sleep(0.5)

    return (success_count, fail_count)


def _retry_failed_thumbnails(handle: amazhist.handle.Handle) -> tuple[int, int]:
    """サムネイル取得に失敗したアイテムを再取得

    Returns:
        (成功件数, 失敗件数)
    """
    failed_items = handle.get_failed_thumbnail_items()

    if not failed_items:
        logging.info("再取得対象のサムネイルはありません")
        return (0, 0)

    logging.info(f"サムネイル取得に失敗したアイテムを再取得します: {len(failed_items)} 件")

    handle.set_progress_bar("[再取得] サムネイル", len(failed_items))

    success_count = 0
    fail_count = 0

    for item in failed_items:
        if is_shutdown_requested():
            break

        name = item.name or "不明"
        thumb_url = item.thumb_url
        asin = item.asin

        if not asin:
            logging.warning(f"ASIN が不明のためスキップしました: {name}")
            handle.get_progress_bar("[再取得] サムネイル").update()
            fail_count += 1
            continue

        handle.set_status(f"🔄 サムネイルを再取得しています: {name[:30]}")

        try:
            amazhist.item._save_thumbnail(handle, asin, thumb_url)
            handle.mark_error_resolved(item.error_id)
            logging.info(f"サムネイルの再取得に成功しました: {name}")
            success_count += 1
        except Exception as e:
            logging.warning(f"サムネイルの再取得をスキップしました: {name} ({e})")
            fail_count += 1

        handle.get_progress_bar("[再取得] サムネイル").update()
        time.sleep(0.5)

    return (success_count, fail_count)


def retry_error_by_id(handle: amazhist.handle.Handle, error_id: int) -> bool:
    """特定のエラーIDを再取得

    Args:
        handle: Handle インスタンス
        error_id: エラーID

    Returns:
        成功した場合は True
    """
    # まずエラー情報を確認（Selenium 起動前）
    error = handle.get_error_by_id(error_id)
    if error is None:
        logging.error(f"エラーID {error_id} は見つかりませんでした")
        handle.set_status(f"❌ エラーID {error_id} は見つかりませんでした", is_error=True)
        return False

    if error.resolved:
        logging.info(f"エラーID {error_id} は既に解決済みです")
        handle.set_status(f"✅ エラーID {error_id} は既に解決済みです")
        return True

    # エラーが有効な場合のみ Selenium を起動
    handle.set_status("🤖 巡回ロボットの準備をします...")
    driver, _wait = handle.get_selenium_driver()

    _setup_graceful_shutdown(handle)

    context = error.context
    display_name = error.item_name or error.order_no or f"ID:{error_id}"
    handle.set_status(f"🔄 再取得しています: {display_name[:40]}")

    try:
        success = False

        if context == "order":
            # 注文の再取得
            error_info = amazhist.database.FailedOrderInfo(
                error_id=error.id,
                order_no=error.order_no,
                order_year=error.order_year,
                order_page=error.order_page,
                order_index=error.order_index,
                url=error.url,
                error_type=error.error_type,
            )
            success = _retry_single_order(handle, error_info)

            if success and error.order_no:
                handle.mark_errors_resolved_by_order_no(error.order_no)

        elif context == "category":
            # カテゴリの再取得
            category = amazhist.item.fetch_item_category(handle, error.url, record_error=False)
            if category:
                handle.update_item_category(error.url, category)
                success = True

        elif context == "thumbnail":
            # サムネイルの再取得
            asin = handle.get_thumbnail_asin_by_error_id(error_id)
            if asin:
                amazhist.item._save_thumbnail(handle, asin, error.url)
                success = True

        elif error.error_type == "order_count_fallback" and error.order_year:
            # 年単位の再巡回
            year = error.order_year
            handle.db.reset_year_status(year)
            _fetch_order_list_by_year(handle, year)
            success = True

        if success:
            handle.mark_error_resolved(error_id)
            logging.info(f"エラーID {error_id} の再取得に成功しました")
            handle.set_status(f"✅ 再取得に成功しました: {display_name[:40]}")
        else:
            logging.warning(f"エラーID {error_id} の再取得に失敗しました")
            handle.set_status(f"❌ 再取得に失敗しました: {display_name[:40]}", is_error=True)

        return success

    except Exception as e:
        logging.exception(f"エラーID {error_id} の再取得中にエラーが発生しました: {e}")
        handle.set_status("❌ 再取得中にエラーが発生しました", is_error=True)
        if not is_shutdown_requested():
            dump_id = amazhist.const.generate_debug_dump_id()
            my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)
        return False


def retry_failed_items(handle: amazhist.handle.Handle) -> None:
    """エラーが発生したアイテムを再取得"""
    handle.set_status("🤖 巡回ロボットの準備をします...")
    driver, _wait = handle.get_selenium_driver()

    _setup_graceful_shutdown(handle)

    handle.set_status("🔄 エラーが発生したアイテムを再取得します...")

    try:
        # 年単位の再巡回（order_count_fallback エラー）
        year_success, year_fail = _retry_failed_years(handle)

        # 注文の再取得
        order_success, order_fail = _retry_failed_orders(handle)

        # カテゴリの再取得
        category_success, category_fail = _retry_failed_categories(handle)

        # サムネイルの再取得
        thumb_success, thumb_fail = _retry_failed_thumbnails(handle)

        # 結果をログに出力
        total_success = year_success + order_success + category_success + thumb_success
        total_fail = year_fail + order_fail + category_fail + thumb_fail

        logging.info(f"再取得結果: 成功 {total_success} 件, 失敗 {total_fail} 件")
        logging.info(f"  年: 成功 {year_success}, 失敗 {year_fail}")
        logging.info(f"  注文: 成功 {order_success}, 失敗 {order_fail}")
        logging.info(f"  カテゴリ: 成功 {category_success}, 失敗 {category_fail}")
        logging.info(f"  サムネイル: 成功 {thumb_success}, 失敗 {thumb_fail}")

    except Exception:
        if not is_shutdown_requested():
            dump_id = amazhist.const.generate_debug_dump_id()
            my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)
        raise

    if is_shutdown_requested():
        handle.set_status("🛑 再取得を中断しました")
    else:
        handle.set_status("✅ 再取得が完了しました")


if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    assert __doc__ is not None  # noqa: S101
    args = docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    handle = amazhist.handle.Handle(config=amazhist.config.Config.load(config))

    try:
        if args["-y"] is None:
            fetch_order_list(handle)
        else:
            year = int(args["-y"])
            start_page = int(args["-s"])

            handle.set_year_list([year])

            count = _fetch_order_count_by_year(handle, year)
            handle.set_order_count(year, count)
            handle.set_progress_bar(amazhist.order_list.STATUS_ORDER_ITEM_ALL, count)

            _fetch_order_list_by_year(handle, year, start_page)
    except Exception:
        driver, _wait = handle.get_selenium_driver()
        logging.error(traceback.format_exc())
        dump_id = amazhist.const.generate_debug_dump_id()
        my_lib.selenium_util.dump_page(driver, dump_id, handle.config.debug_dir_path)
