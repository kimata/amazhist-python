#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import re
import math
import datetime
import random
import logging
import inspect
import time
import traceback
import platform

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import my_lib.selenium_util
import amazhist.const
import amazhist.handle

STATUS_ORDER_COUNT = "[collect] Count of year"
STATUS_ORDER_ITEM_ALL = "[collect] All orders"
STATUS_ORDER_ITEM_BY_TARGET = "[collect] {target} orders"

CAPTCHA_RETRY_COUNT = 2
LOGIN_RETRY_COUNT = 2
FETCH_RETRY_COUNT = 1

DEBUG_USE_DUMP = False
DEBUG_DUMP = True


def wait_for_loading(handle, sec=2):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    time.sleep(sec)


def resolve_captcha(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    logging.info("画像認証の解決を試みます")

    for i in range(CAPTCHA_RETRY_COUNT):
        if i != 0:
            logging.info("画像認証の解決を再試行します")

        captcha_img_path = amazhist.handle.get_captcha_file_path(handle)
        captcha_png_data = driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png

        logging.info("画像を保存しました: {path}".format(path=captcha_img_path))

        with open(captcha_img_path, "wb") as f:
            f.write(captcha_png_data)

        captcha_text = input("「{img_file}」に書かれているテキストを入力してくだい: ".format(img_file=captcha_img_path))

        driver.find_element(By.XPATH, '//input[@name="cvf_captcha_input"]').send_keys(captcha_text.strip())
        driver.find_element(By.XPATH, '//input[@type="submit"]').click()

        wait_for_loading(handle)

        if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) == 0:
            return

        logging.warning("画像認証の解決に失敗しました")
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
        time.sleep(1)

    logging.error("画像認証の解決を諦めました")
    raise "画像認証を解決できませんでした．"


def execute_login(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    time.sleep(1)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_email" and @type!="hidden"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(
            amazhist.handle.get_login_user(handle)
        )

        if len(driver.find_elements(By.XPATH, '//input[@id="continue"]')) != 0:
            driver.find_element(By.XPATH, '//input[@id="continue"]').click()
            wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_password"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').send_keys(
            amazhist.handle.get_login_pass(handle)
        )

    if len(driver.find_elements(By.XPATH, '//input[@id="rememberMe"]')) != 0:
        if not driver.find_element(By.XPATH, '//input[@name="rememberMe"]').get_attribute("checked"):
            driver.find_element(By.XPATH, '//input[@name="rememberMe"]').click()

    driver.find_element(By.XPATH, '//input[@id="signInSubmit"]').click()

    wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) != 0:
        resolve_captcha(handle)


def keep_logged_on(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    if not re.match("Amazonサインイン", driver.title):
        return

    logging.info("ログインを試みます")

    for i in range(LOGIN_RETRY_COUNT):
        if i != 0:
            logging.info("ログインを再試行します")

        execute_login(handle)

        if not re.match("Amazonサインイン", driver.title):
            logging.info("ログインに成功しました")
            return

        logging.warning("ログインに失敗しました")
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )

    logging.error("ログインを諦めました")
    raise "ログインに失敗しました．"


def gen_hist_url(year, page):
    if year == amazhist.const.ARCHIVE_LABEL:
        return amazhist.const.HIST_URL_IN_ARCHIVE.format(
            start=amazhist.const.ORDER_COUNT_PER_PAGE * (page - 1)
        )
    else:
        return amazhist.const.HIST_URL_BY_YEAR.format(
            year=year, start=amazhist.const.ORDER_COUNT_PER_PAGE * (page - 1)
        )


def gen_order_url(no):
    return amazhist.const.HIST_URL_BY_ORDER_NO.format(no=no)


def gen_target_text(year):
    if year == amazhist.const.ARCHIVE_LABEL:
        return "Archive"
    else:
        return "Year {year}".format(year=year)


def gen_status_label_by_yeart(year):
    return STATUS_ORDER_ITEM_BY_TARGET.format(target=gen_target_text(year))


def visit_url(handle, url, file_name):
    driver, wait = amazhist.handle.get_selenium_driver(handle)
    driver.get(url)

    wait_for_loading(handle)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")


def parse_date_digital(date_text):
    return datetime.datetime.strptime(date_text, "%Y/%m/%d")


def parse_item_giftcard(handle, item_xpath):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    count = 1

    price_text = driver.find_element(
        By.XPATH,
        item_xpath + "//div[contains(@class, 'gift-card-instance')]/div[contains(@class, 'a-column')][1]",
    ).text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    seller = "アマゾンジャパン合同会社"
    condition = "新品"

    return {
        "count": count,
        "price": price,
        "seller": seller,
        "condition": condition,
        "kind": "Gift card",
    }


def parse_item_default(handle, item_xpath):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    count = int(
        my_lib.selenium_util.get_text(
            driver, item_xpath + '/..//span[contains(@class, "item-view-qty")]', "1"
        )
    )

    price_text = driver.find_element(By.XPATH, item_xpath + "//span[contains(@class, 'a-color-price')]").text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))
    price *= count

    seller = my_lib.selenium_util.get_text(
        driver,
        item_xpath + "//span[contains(@class, 'a-size-small') and contains(text(), '販売:')]",
        " アマゾンジャパン合同会社",
    ).split(" ", 2)[1]

    condition = my_lib.selenium_util.get_text(
        driver,
        item_xpath
        + "//span[contains(@class, 'a-color-secondary') and contains(text(), 'コンディション：')]/following-sibling::span[1]",
        "新品",
    )

    return {
        "count": count,
        "price": price,
        "seller": seller,
        "condition": condition,
        "kind": "Normal",
    }


def fetch_item_category(handle, item_link):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    actions = ActionChains(driver)

    if platform.system() == "Darwin":
        actions.key_down(Keys.COMMAND)
    else:
        actions.key_down(Keys.CONTROL)

    actions.click(item_link)
    actions.perform()

    driver.switch_to.window(driver.window_handles[-1])

    breadcrumb_list = driver.find_elements(By.XPATH, "//div[contains(@class, 'a-breadcrumb')]//li//a")
    category = list(map(lambda x: x.text, breadcrumb_list))

    time.sleep(1)
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    return category


def save_thumbnail(handle, item, thumb_url):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    with my_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(By.XPATH, "//img").screenshot_as_png

        with open(amazhist.handle.get_thumb_path(handle, item), "wb") as f:
            f.write(png_data)


def parse_item(handle, item_xpath):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    # 商品名とリンク
    link = driver.find_element(
        By.XPATH,
        item_xpath + "//div[@data-component='itemTitle']//a",
    )
    name = link.text
    url = link.get_attribute("href")

    # ASIN を URL から抽出（/dp/XXXX または /gp/product/XXXX 形式）
    asin_match = re.match(r".*/(?:dp|gp/product)/([^/?]+)", url)
    asin = asin_match.group(1) if asin_match else None

    time.sleep(0.5)
    category = fetch_item_category(handle, link)

    item = {
        "name": name,
        "url": url,
        "asin": asin,
        "category": category,
    }

    # サムネイル画像
    try:
        thumb_url = driver.find_element(
            By.XPATH, item_xpath + "//div[@data-component='itemImage']//img"
        ).get_attribute("src")
        save_thumbnail(handle, item, thumb_url)
    except Exception as e:
        logging.warning("サムネイル画像の取得に失敗しました: {name} ({error})".format(name=name, error=str(e)))

    # 価格
    price_elem = driver.find_elements(
        By.XPATH, item_xpath + "//div[@data-component='unitPrice']//span[contains(@class, 'a-offscreen')]"
    )
    if price_elem:
        # NOTE: a-offscreen クラスの要素は .text では空になることがあるため textContent を使用
        price_text = price_elem[0].get_attribute("textContent")
        price_match = re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text)
        if price_match:
            price = int(price_match.group(1).replace(",", ""))
        else:
            logging.warning("価格のパースに失敗しました: {text}".format(text=price_text))
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
            )
            price = 0
    else:
        logging.warning("価格が見つかりませんでした: {name}".format(name=name))
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
        price = 0

    # 数量（デフォルト1）
    count = 1

    # 販売者
    seller_elem = driver.find_elements(
        By.XPATH, item_xpath + "//div[@data-component='orderedMerchant']//a"
    )
    if seller_elem:
        seller = seller_elem[0].text
    else:
        seller = "アマゾンジャパン合同会社"

    # コンディション（デフォルト新品）
    condition = "新品"

    return item | {
        "count": count,
        "price": price,
        "seller": seller,
        "condition": condition,
        "kind": "Normal",
    }


def parse_order_digital(handle, order_info):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    date_text = driver.find_element(By.XPATH, '//td/b[contains(text(), "デジタル注文")]').text.split()[1]
    date = parse_date_digital(date_text)

    no = driver.find_element(By.XPATH, '//ul/li/b[contains(text(), "注文番号")]/..').text.split(": ")[1]

    item_xpath = "//tr[td[b[contains(text(), '注文商品')]]]/following-sibling::tr[1]"

    if len(driver.find_elements(By.XPATH, item_xpath + "/td[1]//a")) != 0:
        link = driver.find_element(By.XPATH, item_xpath + "/td[1]//a")
        name = link.text
        url = link.get_attribute("href")
        asin = re.match(r".*/dp/([^/]+)/", url).group(1)
        category = fetch_item_category(handle, link)
    else:
        # NOTE: もう販売ページが存在しない場合．
        name = driver.find_element(By.XPATH, item_xpath + "/td[1]//b").text
        url = None
        asin = None
        category = []

    count = 1

    price_text = driver.find_element(By.XPATH, item_xpath + "/td[2]").text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    seller = "アマゾンジャパン合同会社"
    condition = "新品"
    kind = "Digital"

    item = {
        "date": date,
        "no": no,
        "name": name,
        "url": url,
        "asin": asin,
        "count": count,
        "price": price,
        "category": category,
        "seller": seller,
        "condition": condition,
        "kind": kind,
        "order_time_filter": order_info["time_filter"],
        "order_page": order_info["page"],
    }

    logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))

    amazhist.handle.record_item(handle, item)

    return True


def parse_order_default(handle, order_info):
    ITEM_XPATH = '//div[@data-component="purchasedItems"]'

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    date_text = driver.find_element(
        By.XPATH, '//div[@data-component="orderDate"]//span'
    ).text.strip().split()[0]
    date = parse_date(date_text)

    no = driver.find_element(
        By.XPATH, '//div[@data-component="orderId"]//span'
    ).text.strip()

    item_base = {
        "date": date,
        "no": no,
        "order_time_filter": order_info["time_filter"],
        "order_page": order_info["page"],
    }

    is_unempty = False
    for i in range(len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        item_xpath = "(" + ITEM_XPATH + ")[{index}]".format(index=i + 1)

        item = parse_item(handle, item_xpath)
        item |= item_base

        logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))

        amazhist.handle.record_item(handle, item)
        is_unempty = True

    return is_unempty


def parse_order(handle, order_info):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    logging.info(
        "注文をパースしています: {date} - {no}".format(date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"])
    )

    if len(driver.find_elements(By.XPATH, "//b[contains(text(), 'デジタル注文')]")) != 0:
        is_unempty = parse_order_digital(handle, order_info)
    else:
        is_unempty = parse_order_default(handle, order_info)

    return is_unempty


def parse_order_count(handle, year):
    ORDER_COUNT_XPATH = "//span[contains(@class, 'num-orders')]"
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    # NOTE: 注文数が多い場合，実際の注文数は最初の方のページには表示されないので，
    # あり得ないページ数を指定する．
    visit_url(handle, gen_hist_url(year, 10000), inspect.currentframe().f_code.co_name)

    if my_lib.selenium_util.xpath_exists(driver, ORDER_COUNT_XPATH):
        order_count_text = driver.find_element(By.XPATH, ORDER_COUNT_XPATH).text

        return int(re.match(r"(\d+)", order_count_text).group(1))
    else:
        time.sleep(1)

        # NOTE: 注文数が表示されない場合，注文数が少ない可能性が高いので，先頭のページを表示する．
        visit_url(handle, gen_hist_url(year, 1), inspect.currentframe().f_code.co_name)

        if my_lib.selenium_util.xpath_exists(driver, ORDER_XPATH):
            logging.info(int(driver.find_elements(By.XPATH, ORDER_XPATH)))
            return int(driver.find_elements(By.XPATH, ORDER_XPATH))
        else:
            logging.warning("注文件数の取得に失敗しました")
            return 0


def fetch_order_item_list_by_order_info(handle, order_info):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    visit_url(handle, order_info["url"], inspect.currentframe().f_code.co_name)
    keep_logged_on(handle)

    if not parse_order(handle, order_info):
        logging.warning("注文のパースに失敗しました: {no}".format(no=order_info["no"]))
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
        time.sleep(1)
        return False

    return True


def fetch_order_item_list_by_year_page(handle, year, page, retry=0):
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    total_page = math.ceil(
        amazhist.handle.get_order_count(handle, year) / amazhist.const.ORDER_COUNT_PER_PAGE
    )

    amazhist.handle.set_status(
        handle,
        "注文履歴を解析しています... {target} {page}/{total_page} ページ".format(
            target=gen_target_text(year), page=page, total_page=total_page
        ),
    )

    visit_url(handle, gen_hist_url(year, page), inspect.currentframe().f_code.co_name)
    keep_logged_on(handle)

    logging.info(
        "{year}年 {page}/{total_page} ページの注文を確認しています".format(year=year, page=page, total_page=total_page)
    )
    logging.info("URL: {url}".format(url=driver.current_url))

    is_skipped = False
    order_list = []
    for i in range(len(driver.find_elements(By.XPATH, ORDER_XPATH))):
        order_xpath = ORDER_XPATH + "[{index}]".format(index=i + 1)

        if (
            len(
                driver.find_elements(
                    By.XPATH, '//div[contains(@class, "a-alert-content")]//span[contains(text(), "問題が発生")]'
                )
            )
            != 0
        ):
            if retry < FETCH_RETRY_COUNT:
                logging.warning("問題が発生しました。再試行します...")
                time.sleep(1)
                return fetch_order_item_list_by_year_page(handle, year, page, retry=0)
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
            logging.info("キャンセル済みの注文をスキップしました: {no}".format(no=no))
            continue

        date_text = driver.find_element(
            By.XPATH,
            order_xpath + "//li[contains(@class, 'order-header__header-list-item')]"
            + "//span[contains(@class, 'a-color-secondary') and contains(@class, 'aok-break-word')]",
        ).text
        date = parse_date(date_text)

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
            is_skipped |= not fetch_order_item_list_by_order_info(handle, order_info)
        else:
            logging.info(
                "注文処理済み: {date} - {no} [キャッシュ]".format(
                    date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"]
                )
            )
        amazhist.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).update()
        amazhist.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()

        if year in [datetime.datetime.now().year, amazhist.const.ARCHIVE_LABEL]:
            last_item = amazhist.handle.get_last_item(handle, year)
            if (
                amazhist.handle.get_year_checked(handle, year)
                and (last_item != None)
                and (last_item["no"] == order_info["no"])
            ):
                logging.info("最新の注文を見つけました。以降のページの解析をスキップします")
                for i in range(total_page):
                    amazhist.handle.set_page_checked(handle, year, i + 1)

    return (is_skipped, page >= total_page)


def fetch_year_list(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    visit_url(handle, amazhist.const.HIST_URL, inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    driver.find_element(
        By.XPATH, "//form[@action='/your-orders/orders']//span[contains(@class, 'a-dropdown-prompt')]"
    ).click()

    wait_for_loading(handle)

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


def skip_order_item_list_by_year_page(handle, year, page):
    logging.info("{year}年 {page} ページの注文をスキップしました [キャッシュ]".format(year=year, page=page))
    incr_order = min(
        amazhist.handle.get_order_count(handle, year)
        - amazhist.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).count,
        amazhist.const.ORDER_COUNT_PER_PAGE,
    )
    amazhist.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).update(incr_order)
    amazhist.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(incr_order)

    # NOTE: これ，状況によっては最終ページで成り立たないので，良くない
    return incr_order != amazhist.const.ORDER_COUNT_PER_PAGE


def fetch_order_item_list_by_year(handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page), inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    year_list = amazhist.handle.get_year_list(handle)

    logging.info(
        "{year}年の注文を確認しています ({year_index}/{total_year})".format(
            year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
        )
    )

    amazhist.handle.set_progress_bar(
        handle,
        gen_status_label_by_yeart(year),
        amazhist.handle.get_order_count(handle, year),
    )

    page = start_page
    is_skipped = False
    while True:
        if not amazhist.handle.get_page_checked(handle, year, page):
            is_skipped_page, is_last = fetch_order_item_list_by_year_page(handle, year, page)

            if not is_skipped_page:
                amazhist.handle.set_page_checked(handle, year, page)

            is_skipped |= is_skipped_page
            time.sleep(1)
        else:
            is_last = skip_order_item_list_by_year_page(handle, year, page)

        amazhist.handle.store_order_info(handle)

        if is_last:
            break

        page += 1

    amazhist.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).update()

    if not is_skipped:
        amazhist.handle.set_year_checked(handle, year)


def fetch_order_count_by_year(handle, year):
    amazhist.handle.set_status(
        handle,
        "注文件数を調べています... {target}".format(target=gen_target_text(year)),
    )

    return parse_order_count(handle, year)


def fetch_order_count(handle):
    year_list = amazhist.handle.get_year_list(handle)

    logging.info("注文件数を収集しています")

    amazhist.handle.set_progress_bar(handle, STATUS_ORDER_COUNT, len(year_list))

    total_count = 0
    for year in year_list:
        if year == amazhist.const.ARCHIVE_LABEL:
            count = fetch_order_count_by_year(handle, year)
            amazhist.handle.set_order_count(handle, year, count)
            logging.info("アーカイブ: {count:4,} 件".format(count=count))
        elif year >= amazhist.handle.get_cache_last_modified(handle).year:
            count = fetch_order_count_by_year(handle, year)
            amazhist.handle.set_order_count(handle, year, count)
            logging.info("{year}年: {count:4,} 件".format(year=year, count=count))
        else:
            count = amazhist.handle.get_order_count(handle, year)
            logging.info("{year}年: {count:4,} 件 [キャッシュ]".format(year=year, count=count))

        total_count += count
        amazhist.handle.get_progress_bar(handle, STATUS_ORDER_COUNT).update()

    logging.info("合計注文数: {total_count:,} 件".format(total_count=total_count))

    amazhist.handle.get_progress_bar(handle, STATUS_ORDER_COUNT).update()
    amazhist.handle.store_order_info(handle)


def fetch_order_item_list_all_year(handle):
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    year_list = fetch_year_list(handle)
    fetch_order_count(handle)

    amazhist.handle.set_progress_bar(
        handle, STATUS_ORDER_ITEM_ALL, amazhist.handle.get_total_order_count(handle)
    )

    for year in year_list:
        if (
            (year == datetime.datetime.now().year)
            or (year == amazhist.handle.get_cache_last_modified(handle).year)
            or (type(year) is str)
            or (not amazhist.handle.get_year_checked(handle, year))
        ):
            fetch_order_item_list_by_year(handle, year)
        else:
            logging.info(
                "{year}年の注文処理済み ({year_index}/{total_year}) [キャッシュ]".format(
                    year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
                )
            )
            amazhist.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(
                amazhist.handle.get_order_count(handle, year)
            )

    amazhist.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()


def fetch_order_item_list(handle):
    amazhist.handle.set_status(handle, "巡回ロボットの準備をします...")
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    amazhist.handle.set_status(handle, "注文履歴の収集を開始します...")

    try:
        fetch_order_item_list_all_year(handle)
    except:
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
        raise

    amazhist.handle.set_status(handle, "注文履歴の収集が完了しました．")


if __name__ == "__main__":
    from docopt import docopt

    import my_lib.logger
    import my_lib.config

    args = docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    handle = amazhist.handle.create(config)

    try:
        if args["-n"] is not None:
            no = args["-n"]
            visit_url(handle, gen_order_url(no), inspect.currentframe().f_code.co_name)
            keep_logged_on(handle)

            parse_order(handle, {"date": datetime.datetime.now(), "no": no, "page": 1, "time_filter": None})
        elif args["-y"] is None:
            fetch_order_item_list(handle)
        else:
            year = int(args["-y"])
            start_page = int(args["-s"])

            amazhist.handle.set_year_list(handle, [year])

            count = fetch_order_count_by_year(handle, year)
            amazhist.handle.set_order_count(handle, year, count)
            amazhist.handle.set_progress_bar(handle, STATUS_ORDER_ITEM_ALL, count)

            fetch_order_item_list_by_year(handle, year, start_page)
    except:
        driver, wait = amazhist.handle.get_selenium_driver(handle)
        logging.error(traceback.format_exc())
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
        )
