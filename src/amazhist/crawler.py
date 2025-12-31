#!/usr/bin/env python3
"""
Amazon の購入履歴情報を取得します．

Usage:
  crawler.py [-c CONFIG] [-y YEAR] [-s PAGE] [-n ORDER_NO]
  crawler.py [-c CONFIG] -n ORDER_NO

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -y YEAR       : 購入年．
  -s PAGE       : 開始ページ．[default: 1]
  -n ORDER_NO   : 注文番号．
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
from selenium.webdriver.common.by import By

import amazhist.const
import amazhist.handle
import amazhist.order
import amazhist.parser

_STATUS_ORDER_COUNT = "[収集] 年数"
_STATUS_ORDER_ITEM_ALL = "[収集] 全注文"
_STATUS_ORDER_ITEM_BY_TARGET = "[収集] {target}"

_CAPTCHA_RETRY_COUNT = 2
_LOGIN_RETRY_COUNT = 2
_FETCH_RETRY_COUNT = 1

# Graceful shutdown 用のフラグ
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Ctrl+C シグナルハンドラ"""
    global _shutdown_requested

    # 既にシャットダウンリクエスト中の場合は強制終了
    if _shutdown_requested:
        logging.warning("強制終了します")
        sys.exit(1)

    try:
        response = input("\n終了しますか？(y/N): ").strip().lower()
        if response == "y":
            _shutdown_requested = True
            logging.info("終了リクエストを受け付けました。現在の処理が完了次第終了します...")
        else:
            logging.info("処理を継続します")
    except EOFError:
        # 入力が取得できない場合は継続
        logging.info("処理を継続します")


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


def _resolve_captcha(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    logging.info("画像認証の解決を試みます")

    for i in range(_CAPTCHA_RETRY_COUNT):
        if i != 0:
            logging.info("画像認証の解決を再試行します")

        captcha_img_path = amazhist.handle.get_captcha_file_path(handle)
        captcha_png_data = driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png

        logging.info(f"画像を保存しました: {captcha_img_path}")

        with open(captcha_img_path, "wb") as f:
            f.write(captcha_png_data)

        captcha_text = input(f"「{captcha_img_path}」に書かれているテキストを入力してくだい: ")

        driver.find_element(By.XPATH, '//input[@name="cvf_captcha_input"]').send_keys(captcha_text.strip())
        driver.find_element(By.XPATH, '//input[@type="submit"]').click()

        _wait_for_loading(handle)

        if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) == 0:
            return

        logging.warning("画像認証の解決に失敗しました")
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
        time.sleep(1)

    logging.error("画像認証の解決を諦めました")
    raise Exception("画像認証を解決できませんでした．")


def _execute_login(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    time.sleep(1)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_email" and @type!="hidden"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(
            amazhist.handle.get_login_user(handle)
        )

        if len(driver.find_elements(By.XPATH, '//input[@id="continue"]')) != 0:
            driver.find_element(By.XPATH, '//input[@id="continue"]').click()
            _wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_password"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').send_keys(
            amazhist.handle.get_login_pass(handle)
        )

    if len(driver.find_elements(By.XPATH, '//input[@id="rememberMe"]')) != 0:
        if not driver.find_element(By.XPATH, '//input[@name="rememberMe"]').get_attribute("checked"):
            driver.find_element(By.XPATH, '//input[@name="rememberMe"]').click()

    driver.find_element(By.XPATH, '//input[@id="signInSubmit"]').click()

    _wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) != 0:
        _resolve_captcha(handle)


def _keep_logged_on(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    if not re.match("Amazonサインイン", driver.title):
        return

    logging.info("ログインを試みます")

    for i in range(_LOGIN_RETRY_COUNT):
        if i != 0:
            logging.info("ログインを再試行します")

        _execute_login(handle)

        if not re.match("Amazonサインイン", driver.title):
            logging.info("ログインに成功しました")
            return

        logging.warning("ログインに失敗しました")
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )

    logging.error("ログインを諦めました")
    raise Exception("ログインに失敗しました．")


def gen_hist_url(year, page):
    """履歴ページのURLを生成"""
    if year == amazhist.const.ARCHIVE_LABEL:
        return amazhist.const.HIST_URL_IN_ARCHIVE.format(
            start=amazhist.const.ORDER_COUNT_PER_PAGE * (page - 1)
        )
    else:
        return amazhist.const.HIST_URL_BY_YEAR.format(
            year=year, start=amazhist.const.ORDER_COUNT_PER_PAGE * (page - 1)
        )


def gen_order_url(no):
    """注文詳細ページのURLを生成"""
    return amazhist.const.HIST_URL_BY_ORDER_NO.format(no=no)


def _gen_target_text(year):
    if year == amazhist.const.ARCHIVE_LABEL:
        return "過去"
    else:
        return f"{year}年"


def _gen_status_label_by_year(year):
    return _STATUS_ORDER_ITEM_BY_TARGET.format(target=_gen_target_text(year))


def visit_url(handle, url, caller_name):
    """URLにアクセス"""
    driver, wait = amazhist.handle.get_selenium_driver(handle)
    driver.get(url)

    _wait_for_loading(handle)


def _fetch_order_item_list_by_order_info(handle, order_info):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    visit_url(handle, order_info["url"], inspect.currentframe().f_code.co_name)
    _keep_logged_on(handle)

    if not amazhist.order.parse_order(handle, order_info):
        logging.warning("注文のパースに失敗しました: {no}".format(no=order_info["no"]))
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
        time.sleep(1)
        return False

    return True


def _fetch_order_item_list_by_year_page(handle, year, page, retry=0):
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    total_page = math.ceil(
        amazhist.handle.get_order_count(handle, year) / amazhist.const.ORDER_COUNT_PER_PAGE
    )

    amazhist.handle.set_status(
        handle,
        f"注文履歴を解析しています... {_gen_target_text(year)} {page}/{total_page} ページ",
    )

    visit_url(handle, gen_hist_url(year, page), inspect.currentframe().f_code.co_name)
    _keep_logged_on(handle)

    logging.info(
        f"{year}年 {page}/{total_page} ページの注文を確認しています"
    )
    logging.info(f"URL: {driver.current_url}")

    is_skipped = False
    order_list = []
    for i in range(len(driver.find_elements(By.XPATH, ORDER_XPATH))):
        order_xpath = ORDER_XPATH + f"[{i + 1}]"

        if (
            len(
                driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "a-alert-content")]//span[contains(text(), "問題が発生")]',
                )
            )
            != 0
        ):
            if retry < _FETCH_RETRY_COUNT:
                logging.warning("問題が発生しました。再試行します...")
                time.sleep(1)
                return _fetch_order_item_list_by_year_page(handle, year, page, retry=0)
            else:
                continue

        # キャンセル済みの注文はスキップ
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
            continue

        date_text = driver.find_element(
            By.XPATH,
            order_xpath + "//li[contains(@class, 'order-header__header-list-item')]"
            + "//span[contains(@class, 'a-color-secondary') and contains(@class, 'aok-break-word')]",
        ).text
        date = amazhist.parser.parse_date(date_text)

        no = driver.find_element(
            By.XPATH,
            order_xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[@dir='ltr']",
        ).text

        url = driver.find_element(
            By.XPATH,
            order_xpath + "//li[contains(@class, 'yohtmlc-order-level-connections')]"
            + "//a[contains(@href, 'order-details')]",
        ).get_attribute("href")

        order_list.append({"date": date, "no": no, "url": url, "time_filter": year, "page": page})

    time.sleep(1)

    for order_info in order_list:
        if not amazhist.handle.get_order_stat(handle, order_info["no"]):
            is_skipped |= not _fetch_order_item_list_by_order_info(handle, order_info)
        else:
            logging.info(
                "注文処理済み: {date} - {no} [キャッシュ]".format(
                    date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"]
                )
            )
        amazhist.handle.get_progress_bar(handle, _gen_status_label_by_year(year)).update()
        amazhist.handle.get_progress_bar(handle, _STATUS_ORDER_ITEM_ALL).update()

        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            logging.info("シャットダウンリクエストにより処理を中断します")
            amazhist.handle.store_order_info(handle)
            return (True, True)

        if year in [datetime.datetime.now().year, amazhist.const.ARCHIVE_LABEL]:
            last_item = amazhist.handle.get_last_item(handle, year)
            if (
                amazhist.handle.get_year_checked(handle, year)
                and (last_item is not None)
                and (last_item["no"] == order_info["no"])
            ):
                logging.info("最新の注文を見つけました。以降のページの解析をスキップします")
                for i in range(total_page):
                    amazhist.handle.set_page_checked(handle, year, i + 1)

    return (is_skipped, page >= total_page)


def fetch_year_list(handle):
    """年リストを取得"""
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    visit_url(handle, amazhist.const.HIST_URL, inspect.currentframe().f_code.co_name)

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

    if "非表示にした注文" in year_str_list:
        year_list.append(amazhist.const.ARCHIVE_LABEL)

    amazhist.handle.set_year_list(handle, year_list)

    return year_list


def _skip_order_item_list_by_year_page(handle, year, page):
    logging.info(f"{year}年 {page} ページの注文をスキップしました [キャッシュ]")
    incr_order = min(
        amazhist.handle.get_order_count(handle, year)
        - amazhist.handle.get_progress_bar(handle, _gen_status_label_by_year(year)).count,
        amazhist.const.ORDER_COUNT_PER_PAGE,
    )
    amazhist.handle.get_progress_bar(handle, _gen_status_label_by_year(year)).update(incr_order)
    amazhist.handle.get_progress_bar(handle, _STATUS_ORDER_ITEM_ALL).update(incr_order)

    # NOTE: これ，状況によっては最終ページで成り立たないので，良くない
    return incr_order != amazhist.const.ORDER_COUNT_PER_PAGE


def _fetch_order_item_list_by_year(handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page), inspect.currentframe().f_code.co_name)

    _keep_logged_on(handle)

    year_list = amazhist.handle.get_year_list(handle)

    logging.info(
        f"{year}年の注文を確認しています ({year_list.index(year) + 1}/{len(year_list)})"
    )

    amazhist.handle.set_progress_bar(
        handle,
        _gen_status_label_by_year(year),
        amazhist.handle.get_order_count(handle, year),
    )

    page = start_page
    is_skipped = False
    while True:
        if not amazhist.handle.get_page_checked(handle, year, page):
            is_skipped_page, is_last = _fetch_order_item_list_by_year_page(handle, year, page)

            if not is_skipped_page:
                amazhist.handle.set_page_checked(handle, year, page)

            is_skipped |= is_skipped_page
            time.sleep(1)
        else:
            is_last = _skip_order_item_list_by_year_page(handle, year, page)

        amazhist.handle.store_order_info(handle)

        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            break

        if is_last:
            break

        page += 1

    amazhist.handle.get_progress_bar(handle, _gen_status_label_by_year(year)).update()

    if not is_skipped and not is_shutdown_requested():
        amazhist.handle.set_year_checked(handle, year)


def _fetch_order_count_by_year(handle, year):
    amazhist.handle.set_status(
        handle,
        f"注文件数を調べています... {_gen_target_text(year)}",
    )

    return amazhist.order.parse_order_count(handle, year)


def _fetch_order_count(handle):
    year_list = amazhist.handle.get_year_list(handle)

    logging.info("注文件数を収集しています")

    amazhist.handle.set_progress_bar(handle, _STATUS_ORDER_COUNT, len(year_list))

    total_count = 0
    for year in year_list:
        if year == amazhist.const.ARCHIVE_LABEL:
            count = _fetch_order_count_by_year(handle, year)
            amazhist.handle.set_order_count(handle, year, count)
            logging.info(f"アーカイブ: {count:4,} 件")
        elif year >= amazhist.handle.get_cache_last_modified(handle).year:
            count = _fetch_order_count_by_year(handle, year)
            amazhist.handle.set_order_count(handle, year, count)
            logging.info(f"{year}年: {count:4,} 件")
        else:
            count = amazhist.handle.get_order_count(handle, year)
            logging.info(f"{year}年: {count:4,} 件 [キャッシュ]")

        total_count += count
        amazhist.handle.get_progress_bar(handle, _STATUS_ORDER_COUNT).update()

    logging.info(f"合計注文数: {total_count:,} 件")

    amazhist.handle.get_progress_bar(handle, _STATUS_ORDER_COUNT).update()
    amazhist.handle.store_order_info(handle)


def _fetch_order_item_list_all_year(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    year_list = fetch_year_list(handle)
    _fetch_order_count(handle)

    amazhist.handle.set_progress_bar(
        handle, _STATUS_ORDER_ITEM_ALL, amazhist.handle.get_total_order_count(handle)
    )

    for year in year_list:
        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            break

        if (
            (year == datetime.datetime.now().year)
            or (year == amazhist.handle.get_cache_last_modified(handle).year)
            or (type(year) is str)
            or (not amazhist.handle.get_year_checked(handle, year))
        ):
            _fetch_order_item_list_by_year(handle, year)
        else:
            logging.info(
                f"{year}年の注文処理済み ({year_list.index(year) + 1}/{len(year_list)}) [キャッシュ]"
            )
            amazhist.handle.get_progress_bar(handle, _STATUS_ORDER_ITEM_ALL).update(
                amazhist.handle.get_order_count(handle, year)
            )

    amazhist.handle.get_progress_bar(handle, _STATUS_ORDER_ITEM_ALL).update()


def fetch_order_item_list(handle):
    """注文履歴を収集"""
    amazhist.handle.set_status(handle, "巡回ロボットの準備をします...")
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    # シグナルハンドラを設定
    setup_signal_handler()
    reset_shutdown_flag()

    amazhist.handle.set_status(handle, "注文履歴の収集を開始します...")

    try:
        _fetch_order_item_list_all_year(handle)
    except Exception:
        if not is_shutdown_requested():
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
            )
        raise

    if is_shutdown_requested():
        amazhist.handle.set_status(handle, "注文履歴の収集を中断しました．")
    else:
        amazhist.handle.set_status(handle, "注文履歴の収集が完了しました．")


if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    args = docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    handle = amazhist.handle.create(config)

    try:
        if args["-n"] is not None:
            no = args["-n"]
            visit_url(handle, gen_order_url(no), inspect.currentframe().f_code.co_name)
            _keep_logged_on(handle)

            amazhist.order.parse_order(
                handle, {"date": datetime.datetime.now(), "no": no, "page": 1, "time_filter": None}
            )
        elif args["-y"] is None:
            fetch_order_item_list(handle)
        else:
            year = int(args["-y"])
            start_page = int(args["-s"])

            amazhist.handle.set_year_list(handle, [year])

            count = _fetch_order_count_by_year(handle, year)
            amazhist.handle.set_order_count(handle, year, count)
            amazhist.handle.set_progress_bar(handle, _STATUS_ORDER_ITEM_ALL, count)

            _fetch_order_item_list_by_year(handle, year, start_page)
    except Exception:
        driver, wait = amazhist.handle.get_selenium_driver(handle)
        logging.error(traceback.format_exc())
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
