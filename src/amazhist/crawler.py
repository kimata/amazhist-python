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
import math
import random
import re
import signal
import sys
import time
import traceback

import my_lib.selenium_util
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

import amazhist.config
import amazhist.const
import amazhist.handle
import amazhist.item
import amazhist.order
import amazhist.parser

_STATUS_ORDER_COUNT = "[収集] 年数"
_STATUS_ORDER_ITEM_ALL = "[収集] 全注文"
_STATUS_ORDER_ITEM_BY_TARGET = "[収集] {target}"


class LoginError(Exception):
    """ログイン失敗を示す例外"""


class CaptchaError(Exception):
    """CAPTCHA解決失敗を示す例外"""


def _get_caller_name() -> str:
    """呼び出し元の関数名を取得"""
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        return "unknown"
    return frame.f_back.f_code.co_name

# Graceful shutdown 用のフラグとハンドル
_shutdown_requested = False
_current_handle = None


def _signal_handler(signum, frame):
    """Ctrl+C シグナルハンドラ"""
    global _shutdown_requested, _current_handle

    # 既にシャットダウンリクエスト中の場合は強制終了
    if _shutdown_requested:
        logging.warning("強制終了します")
        sys.exit(1)

    try:
        # Rich Live を一時停止して入力を受け付ける
        if _current_handle is not None:
            _current_handle.pause_live()

        response = input("\n終了しますか？(y/N): ").strip().lower()
        if response == "y":
            _shutdown_requested = True
            # urllib3 の接続エラー WARNING を抑制
            logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
            logging.info("終了リクエストを受け付けました。現在の処理が完了次第終了します...")
        else:
            logging.info("処理を継続します")

        # Rich Live を再開
        if _current_handle is not None:
            _current_handle.resume_live()
    except EOFError:
        # 入力が取得できない場合は継続
        logging.info("処理を継続します")
        if _current_handle is not None:
            _current_handle.resume_live()


def setup_signal_handler():
    """シグナルハンドラを設定"""
    signal.signal(signal.SIGINT, _signal_handler)


def is_shutdown_requested():
    """シャットダウンがリクエストされているかを返す"""
    return _shutdown_requested


def reset_shutdown_flag():
    """シャットダウンフラグをリセット"""
    global _shutdown_requested
    _shutdown_requested = False


def _wait_for_loading(handle, sec=2):
    time.sleep(sec)


def _resolve_captcha(handle: amazhist.handle.Handle):
    driver, wait = handle.get_selenium_driver()

    logging.info("画像認証の解決を試みます")

    def _try_solve():
        captcha_img_path = handle.config.captcha_file_path
        captcha_png_data = driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png

        logging.info(f"画像を保存しました: {captcha_img_path}")

        with open(captcha_img_path, "wb") as f:
            f.write(captcha_png_data)

        captcha_text = input(f"「{captcha_img_path}」に書かれているテキストを入力してください: ")

        driver.find_element(By.XPATH, '//input[@name="cvf_captcha_input"]').send_keys(captcha_text.strip())
        driver.find_element(By.XPATH, '//input[@type="submit"]').click()

        _wait_for_loading(handle)

        if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) != 0:
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), handle.config.debug_dir_path
            )
            raise CaptchaError("CAPTCHA未解決")

    try:
        my_lib.selenium_util.with_retry(
            _try_solve,
            max_retries=amazhist.const.RETRY_CAPTCHA,
            exceptions=(CaptchaError,),
            on_retry=lambda attempt, e: logging.info("画像認証の解決を再試行します"),
        )
    except CaptchaError:
        logging.error("画像認証の解決を諦めました")
        raise Exception("画像認証を解決できませんでした．")


def _execute_login(handle: amazhist.handle.Handle):
    driver, wait = handle.get_selenium_driver()

    time.sleep(1)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_email" and @type!="hidden"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(
            handle.get_login_user()
        )

        if len(driver.find_elements(By.XPATH, '//input[@id="continue"]')) != 0:
            driver.find_element(By.XPATH, '//input[@id="continue"]').click()
            _wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_password"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').send_keys(
            handle.get_login_pass()
        )

    if len(driver.find_elements(By.XPATH, '//input[@id="rememberMe"]')) != 0:
        if not driver.find_element(By.XPATH, '//input[@name="rememberMe"]').get_attribute("checked"):
            driver.find_element(By.XPATH, '//input[@name="rememberMe"]').click()

    driver.find_element(By.XPATH, '//input[@id="signInSubmit"]').click()

    _wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) != 0:
        _resolve_captcha(handle)


def _keep_logged_on(handle: amazhist.handle.Handle):
    driver, wait = handle.get_selenium_driver()

    if not re.match("Amazonサインイン", driver.title):
        return

    logging.info("ログインを試みます")

    def _try_login():
        _execute_login(handle)
        if re.match("Amazonサインイン", driver.title):
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), handle.config.debug_dir_path
            )
            raise LoginError("ログイン失敗")

    try:
        my_lib.selenium_util.with_retry(
            _try_login,
            max_retries=amazhist.const.RETRY_LOGIN,
            exceptions=(LoginError,),
            on_retry=lambda attempt, e: logging.info("ログインを再試行します"),
        )
        logging.info("ログインに成功しました")
    except LoginError:
        logging.error("ログインを諦めました")
        raise Exception("ログインに失敗しました．")


def gen_hist_url(year: int, page: int) -> str:
    """履歴ページのURLを生成"""
    return amazhist.const.HIST_URL_BY_YEAR.format(
        year=year, start=amazhist.const.ORDER_COUNT_PER_PAGE * (page - 1)
    )


def gen_order_url(no: str) -> str:
    """注文詳細ページのURLを生成"""
    return amazhist.const.HIST_URL_BY_ORDER_NO.format(no=no)


def _gen_target_text(year: int) -> str:
    return f"{year}年"


def _gen_status_label_by_year(year):
    return _STATUS_ORDER_ITEM_BY_TARGET.format(target=_gen_target_text(year))


def visit_url(handle: amazhist.handle.Handle, url, caller_name):
    """URLにアクセス

    TimeoutException が発生した場合はリトライします。
    """
    driver, wait = handle.get_selenium_driver()

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


def _fetch_item_list_by_order(handle: amazhist.handle.Handle, order: amazhist.order.Order):
    driver, wait = handle.get_selenium_driver()

    try:
        visit_url(handle, order.url, _get_caller_name())
        _keep_logged_on(handle)
    except TimeoutException as e:
        logging.warning(f"注文ページの取得に失敗しました（タイムアウト）: {order.no}")
        handle.record_or_update_error(
            url=order.url,
            error_type=amazhist.const.ERROR_TYPE_TIMEOUT,
            context="order",
            message=str(e),
            order_no=order.no,
            order_year=order.time_filter,
            order_page=order.page,
        )
        time.sleep(1)
        return False

    if not amazhist.order.parse_order(handle, order):
        logging.warning("注文のパースに失敗しました: {no}".format(no=order.no))
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), handle.config.debug_dir_path
        )
        handle.record_or_update_error(
            url=order.url,
            error_type="parse_error",
            context="order",
            message="注文のパースに失敗しました",
            order_no=order.no,
            order_year=order.time_filter,
            order_page=order.page,
        )
        time.sleep(1)
        return False

    return True


def _fetch_order_list_by_year_page(handle: amazhist.handle.Handle, year, page, retry=0):
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = handle.get_selenium_driver()

    total_page = math.ceil(
        handle.get_order_count(year) / amazhist.const.ORDER_COUNT_PER_PAGE
    )

    handle.set_status(
        f"🔍 注文履歴を解析しています... {_gen_target_text(year)} {page}/{total_page} ページ",
    )

    visit_url(handle, gen_hist_url(year, page), _get_caller_name())
    _keep_logged_on(handle)

    logging.info(
        f"{year}年 {page}/{total_page} ページの注文を確認しています"
    )
    logging.info(f"URL: {driver.current_url}")

    is_skipped = False
    order_list = []
    order_card_count = len(driver.find_elements(By.XPATH, ORDER_XPATH))
    for i in range(order_card_count):
        order_xpath = ORDER_XPATH + f"[{i + 1}]"
        progress_updated = False

        try:
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
                    return _fetch_order_list_by_year_page(handle, year, page, retry=retry + 1)
                else:
                    continue

            # キャンセル済みの注文はスキップ（プログレスバーは更新する）
            if (
                len(
                    driver.find_elements(
                        By.XPATH,
                        order_xpath + "//div[contains(@class, 'yohtmlc-shipment-status-primaryText')]"
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
                handle.get_progress_bar(_gen_status_label_by_year(year)).update()
                handle.get_progress_bar(_STATUS_ORDER_ITEM_ALL).update()
                progress_updated = True
                continue

            # 日付を取得
            date_text = driver.find_element(
                By.XPATH,
                order_xpath + "//li[contains(@class, 'order-header__header-list-item')]"
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
                    url=gen_hist_url(year, page),
                    error_type=amazhist.const.ERROR_TYPE_NO_ORDER_NO,
                    context="order",
                    message=f"注文番号が取得できませんでした（{i + 1}番目）",
                    order_no=None,
                    order_year=year,
                    order_page=page,
                    order_index=i,
                )
                handle.get_progress_bar(_gen_status_label_by_year(year)).update()
                handle.get_progress_bar(_STATUS_ORDER_ITEM_ALL).update()
                progress_updated = True
                continue

            no = order_no_elems[0].text

            # order-details リンクを取得
            order_details_xpath = (
                order_xpath + "//li[contains(@class, 'yohtmlc-order-level-connections')]"
                + "//a[contains(@href, 'order-details')]"
            )
            order_details_elems = driver.find_elements(By.XPATH, order_details_xpath)

            if order_details_elems:
                url = order_details_elems[0].get_attribute("href")
                if url is None:
                    # リンク要素はあるが href が取得できない場合 → URLを構築
                    logging.info(f"詳細リンクの URL が取得できないため、URLを構築します: {no}")
                    url = gen_order_url(no)
            else:
                # 詳細リンクがない場合 → URLを構築
                logging.info(f"詳細リンクがないため、URLを構築して取得を試みます: {no}")
                url = gen_order_url(no)

            order_list.append(amazhist.order.Order(date=date, no=no, url=url, time_filter=year, page=page))
        except Exception as e:
            # 注文カード解析中に予期しない例外が発生した場合
            logging.warning(f"注文カードの解析中にエラーが発生しました（{year}年 {page}ページ {i + 1}番目）: {e}")
            handle.record_or_update_error(
                url=gen_hist_url(year, page),
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
            handle.get_progress_bar(_gen_status_label_by_year(year)).update()
            handle.get_progress_bar(_STATUS_ORDER_ITEM_ALL).update()

    time.sleep(1)

    for order in order_list:
        try:
            if not handle.get_order_stat(order.no):
                is_skipped |= not _fetch_item_list_by_order(handle, order)
            else:
                logging.info(
                    "注文処理済み: {date} - {no} [キャッシュ]".format(
                        date=order.date.strftime("%Y-%m-%d"), no=order.no
                    )
                )
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
        finally:
            # 成功・失敗に関わらずプログレスバーを更新
            handle.get_progress_bar(_gen_status_label_by_year(year)).update()
            handle.get_progress_bar(_STATUS_ORDER_ITEM_ALL).update()

        # デバッグモードでは1件だけ処理して終了
        if handle.debug_mode:
            logging.info("デバッグモード: 1件の注文を処理したため終了します")
            return (is_skipped, True)

        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            logging.info("シャットダウンリクエストにより処理を中断します")
            handle.store_order_info()
            return (True, True)

        if year == datetime.datetime.now().year:
            last_item = handle.get_last_item(year)
            if (
                handle.get_year_checked(year)
                and (last_item is not None)
                and (last_item.no == order.no)
            ):
                logging.info("最新の注文を見つけました。以降のページの解析をスキップします")
                for i in range(total_page):
                    handle.set_page_checked(year, i + 1)

    return (is_skipped, page >= total_page)


def fetch_year_list(handle: amazhist.handle.Handle):
    """年リストを取得"""
    driver, wait = handle.get_selenium_driver()

    visit_url(handle, amazhist.const.HIST_URL, _get_caller_name())

    _keep_logged_on(handle)

    driver.find_element(
        By.XPATH, "//form[@action='/your-orders/orders']//span[contains(@class, 'a-dropdown-prompt')]"
    ).click()

    _wait_for_loading(handle)

    year_str_list = list(
        map(
            lambda elem: elem.text,
            driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'a-popover-wrapper')]//li",
            ),
        )
    )

    year_list = list(
        reversed(
            list(
                map(
                    lambda label: int(label.replace("年", "")),
                    filter(lambda label: re.match(r"\d+年", label), year_str_list),
                )
            )
        )
    )

    handle.set_year_list(year_list)

    return year_list


def _skip_order_item_list_by_year_page(handle: amazhist.handle.Handle, year, page):
    logging.info(f"{year}年 {page} ページの注文をスキップしました [キャッシュ]")
    incr_order = min(
        handle.get_order_count(year)
        - handle.get_progress_bar(_gen_status_label_by_year(year)).count,
        amazhist.const.ORDER_COUNT_PER_PAGE,
    )
    handle.get_progress_bar(_gen_status_label_by_year(year)).update(incr_order)
    handle.get_progress_bar(_STATUS_ORDER_ITEM_ALL).update(incr_order)

    # NOTE: これ，状況によっては最終ページで成り立たないので，良くない
    return incr_order != amazhist.const.ORDER_COUNT_PER_PAGE


def _fetch_order_list_by_year(handle: amazhist.handle.Handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page), _get_caller_name())

    _keep_logged_on(handle)

    year_list = handle.get_year_list()

    logging.info(
        f"{year}年の注文を確認しています ({year_list.index(year) + 1}/{len(year_list)})"
    )

    handle.set_progress_bar(
        _gen_status_label_by_year(year),
        handle.get_order_count(year),
    )

    page = start_page
    is_skipped = False
    while True:
        if not handle.get_page_checked(year, page):
            is_skipped_page, is_last = _fetch_order_list_by_year_page(handle, year, page)

            if not is_skipped_page:
                handle.set_page_checked(year, page)

            is_skipped |= is_skipped_page
            time.sleep(1)
        else:
            is_last = _skip_order_item_list_by_year_page(handle, year, page)

        handle.store_order_info()

        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            break

        if is_last:
            break

        # デバッグモードでは1ページだけ処理して終了
        if handle.debug_mode:
            break

        page += 1

    if not is_skipped and not is_shutdown_requested() and not handle.debug_mode:
        handle.set_year_checked(year)


def _fetch_order_count_by_year(handle: amazhist.handle.Handle, year):
    handle.set_status(
        f"🔍 注文件数を調べています... {_gen_target_text(year)}",
    )

    return amazhist.order.parse_order_count(handle, year)


def _fetch_order_count(handle: amazhist.handle.Handle):
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


def _fetch_order_list_all_year(handle: amazhist.handle.Handle):
    driver, wait = handle.get_selenium_driver()

    year_list = fetch_year_list(handle)
    _fetch_order_count(handle)

    handle.set_progress_bar(
        _STATUS_ORDER_ITEM_ALL, handle.get_total_order_count()
    )

    for year in year_list:
        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            break

        if (
            (year == datetime.datetime.now().year)
            or (year == handle.get_cache_last_modified().year)
            or (type(year) is str)
            or (not handle.get_year_checked(year))
        ):
            _fetch_order_list_by_year(handle, year)

            # デバッグモードでは1年だけ処理して終了
            if handle.debug_mode:
                break
        else:
            logging.info(
                f"{year}年の注文処理済み ({year_list.index(year) + 1}/{len(year_list)}) [キャッシュ]"
            )
            handle.get_progress_bar(_STATUS_ORDER_ITEM_ALL).update(
                handle.get_order_count(year)
            )


def fetch_order_list(handle: amazhist.handle.Handle):
    """注文履歴を収集

    Args:
        handle: アプリケーションハンドル
    """
    global _current_handle

    handle.set_status("🤖 巡回ロボットの準備をします...")
    driver, wait = handle.get_selenium_driver()

    # シグナルハンドラを設定（handle を保存してシグナルハンドラからアクセス可能にする）
    _current_handle = handle
    setup_signal_handler()
    reset_shutdown_flag()

    handle.set_status("📥 注文履歴の収集を開始します...")

    try:
        _fetch_order_list_all_year(handle)
    except Exception:
        if not is_shutdown_requested():
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), handle.config.debug_dir_path
            )
        raise

    if is_shutdown_requested():
        handle.set_status("🛑 注文履歴の収集を中断しました")
    else:
        handle.set_status("✅ 注文履歴の収集が完了しました")


def _retry_order_from_list_page(
    handle: amazhist.handle.Handle, error_info: dict
) -> bool:
    """注文一覧ページから詳細リンクを取得して再取得を試みる

    Args:
        handle: アプリケーションハンドル
        error_info: エラー情報（order_year, order_page, order_index を含む）

    Returns:
        成功した場合 True
    """
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'
    driver, wait = handle.get_selenium_driver()

    year = error_info["order_year"]
    page = error_info["order_page"]
    index = error_info.get("order_index")
    order_no = error_info.get("order_no")

    # 注文一覧ページにアクセス
    visit_url(handle, gen_hist_url(year, page), _get_caller_name())
    _keep_logged_on(handle)

    # 注文番号がない場合（NO_ORDER_NO エラー）はインデックスで注文を特定
    if order_no is None and index is not None:
        order_elems = driver.find_elements(By.XPATH, ORDER_XPATH)
        if index >= len(order_elems):
            logging.warning(f"注文が見つかりませんでした（インデックス超過）: {year}年 {page}ページ {index + 1}番目")
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

    # 注文番号から注文を特定
    order_xpath = None
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
        order_xpath + "//li[contains(@class, 'order-header__header-list-item')]"
        + "//span[contains(@class, 'a-color-secondary') and contains(@class, 'aok-break-word')]",
    ).text
    date = amazhist.parser.parse_date(date_text)

    # 詳細リンクを取得
    order_details_xpath = (
        order_xpath + "//li[contains(@class, 'yohtmlc-order-level-connections')]"
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

    visit_url(handle, order.url, _get_caller_name())
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
    years = sorted(set(error["order_year"] for error in failed_years if error["order_year"]))

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
                if error["order_year"] == year:
                    handle.mark_error_resolved(error["id"])

            logging.info(f"{year}年の再巡回が完了しました")
            success_count += 1
        except Exception as e:
            logging.warning(f"{year}年の再巡回をスキップしました: {e}")
            fail_count += 1

        handle.get_progress_bar("[再取得] 年").update()
        time.sleep(1)

    return (success_count, fail_count)


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

    current_year = datetime.datetime.now().year
    success_count = 0
    fail_count = 0

    for error_info in failed_orders:
        if is_shutdown_requested():
            break

        order_no = error_info.get("order_no")
        order_year = error_info.get("order_year")
        error_id = error_info["error_id"]

        display_name = order_no or f"{order_year}年 {error_info.get('order_page')}ページ"
        handle.set_status(f"🔄 注文を再取得しています: {display_name}")

        try:
            success = False

            if order_year is not None and order_year != current_year:
                # 過去の年: 注文一覧ページから詳細リンクを取得して再取得
                logging.info(f"過去の年の注文を一覧ページから再取得します: {display_name}")
                success = _retry_order_from_list_page(handle, error_info)
            else:
                # 現在の年または年情報がない場合: 構築したURLで直接取得
                if order_no:
                    logging.info(f"構築したURLで直接取得します: {order_no}")
                    order = amazhist.order.Order(
                        date=datetime.datetime.now(),
                        no=order_no,
                        url=gen_order_url(order_no),
                        time_filter=order_year,
                        page=error_info.get("order_page"),
                    )

                    visit_url(handle, order.url, _get_caller_name())
                    _keep_logged_on(handle)

                    success = amazhist.order.parse_order(handle, order)
                elif order_year is not None:
                    # 現在の年で注文番号がない場合も一覧ページから再取得を試みる
                    logging.info(f"現在の年の注文を一覧ページから再取得します: {display_name}")
                    success = _retry_order_from_list_page(handle, error_info)

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

        name = item.get("name") or "不明"
        url = item["url"]

        handle.set_status(f"🔄 カテゴリを再取得しています: {name[:30]}")

        try:
            # record_error=False でエラー記録を抑制（既にエラーログに記録されているため）
            category = amazhist.item.fetch_item_category(handle, url, record_error=False)
            if category:
                handle.update_item_category(url, category)
                handle.mark_error_resolved(item["error_id"])
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

        name = item.get("name") or "不明"
        thumb_url = item["thumb_url"]
        asin = item.get("asin")

        if not asin:
            logging.warning(f"ASIN が不明のためスキップしました: {name}")
            handle.get_progress_bar("[再取得] サムネイル").update()
            fail_count += 1
            continue

        handle.set_status(f"🔄 サムネイルを再取得しています: {name[:30]}")

        try:
            amazhist.item._save_thumbnail(handle, asin, thumb_url)
            handle.mark_error_resolved(item["error_id"])
            logging.info(f"サムネイルの再取得に成功しました: {name}")
            success_count += 1
        except Exception as e:
            logging.warning(f"サムネイルの再取得をスキップしました: {name} ({e})")
            fail_count += 1

        handle.get_progress_bar("[再取得] サムネイル").update()
        time.sleep(0.5)

    return (success_count, fail_count)


def retry_failed_items(handle: amazhist.handle.Handle):
    """エラーが発生したアイテムを再取得"""
    global _current_handle

    handle.set_status("🤖 巡回ロボットの準備をします...")
    driver, wait = handle.get_selenium_driver()

    # シグナルハンドラを設定
    _current_handle = handle
    setup_signal_handler()
    reset_shutdown_flag()

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
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), handle.config.debug_dir_path
            )
        raise

    if is_shutdown_requested():
        handle.set_status("🛑 再取得を中断しました")
    else:
        handle.set_status("✅ 再取得が完了しました")


if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    assert __doc__ is not None
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
            handle.set_progress_bar(_STATUS_ORDER_ITEM_ALL, count)

            _fetch_order_list_by_year(handle, year, start_page)
    except Exception:
        driver, wait = handle.get_selenium_driver()
        logging.error(traceback.format_exc())
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), handle.config.debug_dir_path
        )
