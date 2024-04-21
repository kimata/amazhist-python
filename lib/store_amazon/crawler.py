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

import local_lib.selenium_util
import store_amazon.const
import store_amazon.handle

STATUS_ORDER_COUNT = "[collect] Count of year"
STATUS_ORDER_ITEM_ALL = "[collect] All orders"
STATUS_ORDER_ITEM_BY_TARGET = "[collect] {target} orders"

CAPTCHA_RETRY_COUNT = 2
LOGIN_RETRY_COUNT = 2
FETCH_RETRY_COUNT = 1

DEBUG_USE_DUMP = False
DEBUG_DUMP = True


def wait_for_loading(handle, sec=2):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    time.sleep(sec)


def resolve_captcha(handle):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    logging.info("Try to resolve CAPTCHA")

    for i in range(CAPTCHA_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to resolve CAPTCHA")

        captcha_img_path = store_amazon.handle.get_captcha_file_path(handle)
        captcha_png_data = driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png

        logging.info("Save image: {path}".format(path=captcha_img_path))

        with open(captcha_img_path, "wb") as f:
            f.write(captcha_png_data)

        captcha_text = input("「{img_file}」に書かれているテキストを入力してくだい: ".format(img_file=captcha_img_path))

        driver.find_element(By.XPATH, '//input[@name="cvf_captcha_input"]').send_keys(captcha_text.strip())
        driver.find_element(By.XPATH, '//input[@type="submit"]').click()

        wait_for_loading(handle)

        if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) == 0:
            return

        logging.warning("Failed to resolve CAPTCHA")
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), store_amazon.handle.get_debug_dir_path(handle)
        )
        time.sleep(1)

    logging.error("Give up to resolve CAPTCHA")
    raise "画像認証を解決できませんでした．"


def execute_login(handle):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    time.sleep(1)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_email" and @type!="hidden"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(
            store_amazon.handle.get_login_user(handle)
        )

        if len(driver.find_elements(By.XPATH, '//input[@id="continue"]')) != 0:
            driver.find_element(By.XPATH, '//input[@id="continue"]').click()
            wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_password"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').send_keys(
            store_amazon.handle.get_login_pass(handle)
        )

    if len(driver.find_elements(By.XPATH, '//input[@id="rememberMe"]')) != 0:
        if not driver.find_element(By.XPATH, '//input[@name="rememberMe"]').get_attribute("checked"):
            driver.find_element(By.XPATH, '//input[@name="rememberMe"]').click()

    driver.find_element(By.XPATH, '//input[@id="signInSubmit"]').click()

    wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) != 0:
        resolve_captcha(handle)


def keep_logged_on(handle):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    if not re.match("Amazonサインイン", driver.title):
        return

    logging.info("Try to login")

    for i in range(LOGIN_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to login")

        execute_login(handle)

        if not re.match("Amazonサインイン", driver.title):
            logging.info("Login sccessful!")
            return

        logging.warning("Failed to login")
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), store_amazon.handle.get_debug_dir_path(handle)
        )

    logging.error("Give up to login")
    raise "ログインに失敗しました．"


def gen_hist_url(year, page):
    if year == store_amazon.const.ARCHIVE_LABEL:
        return store_amazon.const.HIST_URL_IN_ARCHIVE.format(
            start=store_amazon.const.ORDER_COUNT_PER_PAGE * (page - 1)
        )
    else:
        return store_amazon.const.HIST_URL_BY_YEAR.format(
            year=year, start=store_amazon.const.ORDER_COUNT_PER_PAGE * (page - 1)
        )


def gen_order_url(no):
    return store_amazon.const.HIST_URL_BY_ORDER_NO.format(no=no)


def gen_target_text(year):
    if year == store_amazon.const.ARCHIVE_LABEL:
        return "Archive"
    else:
        return "Year {year}".format(year=year)


def gen_status_label_by_yeart(year):
    return STATUS_ORDER_ITEM_BY_TARGET.format(target=gen_target_text(year))


def visit_url(handle, url, file_name):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)
    driver.get(url)

    wait_for_loading(handle)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")


def parse_date_digital(date_text):
    return datetime.datetime.strptime(date_text, "%Y/%m/%d")


def parse_item_giftcard(handle, item_xpath):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

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
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    count = int(
        local_lib.selenium_util.get_text(
            driver, item_xpath + '/..//span[contains(@class, "item-view-qty")]', "1"
        )
    )

    price_text = driver.find_element(By.XPATH, item_xpath + "//span[contains(@class, 'a-color-price')]").text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))
    price *= count

    seller = local_lib.selenium_util.get_text(
        driver,
        item_xpath + "//span[contains(@class, 'a-size-small') and contains(text(), '販売:')]",
        " アマゾンジャパン合同会社",
    ).split(" ", 2)[1]

    condition = local_lib.selenium_util.get_text(
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
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

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
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(By.XPATH, "//img").screenshot_as_png

        with open(store_amazon.handle.get_thumb_path(handle, item), "wb") as f:
            f.write(png_data)


def parse_item(handle, item_xpath):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    link = driver.find_element(
        By.XPATH,
        item_xpath + "//a[contains(@class, 'a-link-normal')]",
    )
    name = link.text
    url = link.get_attribute("href")
    asin = re.match(r".*/gp/product/([^/]+)/", url).group(1)

    time.sleep(0.5)
    category = fetch_item_category(handle, link)

    item = {
        "name": name,
        "url": url,
        "asin": asin,
        "category": category,
    }

    thumb_url = driver.find_element(By.XPATH, item_xpath + "/preceding-sibling::div//a/img").get_attribute(
        "src"
    )
    save_thumbnail(handle, item, thumb_url)

    if len(driver.find_elements(By.XPATH, item_xpath + "//div[contains(@class, 'gift-card-instance')]")) != 0:
        return item | parse_item_giftcard(handle, item_xpath)
    else:
        return item | parse_item_default(handle, item_xpath)


def parse_order_digital(handle, order_info):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

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

    store_amazon.handle.record_item(handle, item)

    return True


def parse_order_default(handle, order_info):
    ITEM_XPATH = '//div[contains(@data-component, "shipments")]//div[contains(@class, "yohtmlc-item")]'

    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    date_text = driver.find_element(
        By.XPATH, '//span[contains(@class, "order-date-invoice-item")][1]'
    ).text.split()[1]
    date = parse_date(date_text)

    no = driver.find_element(By.XPATH, '//span[contains(@class, "order-date-invoice-item")]/bdi').text

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

        store_amazon.handle.record_item(handle, item)
        is_unempty = True

    return is_unempty


def parse_order(handle, order_info):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    logging.info(
        "Parse order: {date} - {no}".format(date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"])
    )

    if len(driver.find_elements(By.XPATH, "//b[contains(text(), 'デジタル注文')]")) != 0:
        is_unempty = parse_order_digital(handle, order_info)
    else:
        is_unempty = parse_order_default(handle, order_info)

    return is_unempty


def parse_order_count(handle):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    order_count_text = driver.find_element(By.XPATH, "//span[contains(@class, 'num-orders')]").text

    return int(re.match(r"(\d+)", order_count_text).group(1))


def fetch_order_item_list_by_order_info(handle, order_info):
    visit_url(handle, order_info["url"], inspect.currentframe().f_code.co_name)
    keep_logged_on(handle)

    if not parse_order(handle, order_info):
        logging.warning("Failed to parse order of {no}".format(no=order_info["no"]))
        time.sleep(1)
        return False

    return True


def fetch_order_item_list_by_year_page(handle, year, page, retry=0):
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    total_page = math.ceil(
        store_amazon.handle.get_order_count(handle, year) / store_amazon.const.ORDER_COUNT_PER_PAGE
    )

    store_amazon.handle.set_status(
        handle,
        "注文履歴を解析しています... {target} {page}/{total_page} ページ".format(
            target=gen_target_text(year), page=page, total_page=total_page
        ),
    )

    visit_url(handle, gen_hist_url(year, page), inspect.currentframe().f_code.co_name)
    keep_logged_on(handle)

    logging.info(
        "Check order of {year} page {page}/{total_page}".format(year=year, page=page, total_page=total_page)
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
                logging.warning("Something went wrong. Try retying...")
                time.sleep(1)
                return fetch_order_item_list_by_year_page(handle, year, page, retry=0)
            else:
                continue

        date_text = driver.find_element(
            By.XPATH, order_xpath + "//div[contains(@class, 'a-row')]/span[contains(@class, 'value')]"
        ).text
        date = parse_date(date_text)

        no = driver.find_element(
            By.XPATH,
            order_xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[contains(@class, 'value')]",
        ).text

        url = driver.find_element(
            By.XPATH, order_xpath + "//a[contains(@class, 'yohtmlc-order-details-link')]"
        ).get_attribute("href")

        order_list.append({"date": date, "no": no, "url": url, "time_filter": year, "page": page})

    time.sleep(1)

    for order_info in order_list:
        if not store_amazon.handle.get_order_stat(handle, order_info["no"]):
            is_skipped |= not fetch_order_item_list_by_order_info(handle, order_info)
        else:
            logging.info(
                "Done order: {date} - {no} [cached]".format(
                    date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"]
                )
            )
        store_amazon.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).update()
        store_amazon.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()

        if year in [datetime.datetime.now().year, store_amazon.const.ARCHIVE_LABEL]:
            last_item = store_amazon.handle.get_last_item(handle, year)
            if (
                store_amazon.handle.get_year_checked(handle, year)
                and (last_item != None)
                and (last_item["no"] == order_info["no"])
            ):
                logging.info("Latest order found, skipping analysis of subsequent pages")
                for i in range(total_page):
                    store_amazon.handle.set_page_checked(handle, year, i + 1)

    return (is_skipped, page >= total_page)


def fetch_year_list(handle):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    visit_url(handle, store_amazon.const.HIST_URL, inspect.currentframe().f_code.co_name)

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
        year_list.append(store_amazon.const.ARCHIVE_LABEL)

    store_amazon.handle.set_year_list(handle, year_list)

    return year_list


def skip_order_item_list_by_year_page(handle, year, page):
    logging.info("Skip check order of {year} page {page} [cached]".format(year=year, page=page))
    incr_order = min(
        store_amazon.handle.get_order_count(handle, year)
        - store_amazon.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).count,
        store_amazon.const.ORDER_COUNT_PER_PAGE,
    )
    store_amazon.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).update(incr_order)
    store_amazon.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(incr_order)

    # NOTE: これ，状況によっては最終ページで成り立たないので，良くない
    return incr_order != store_amazon.const.ORDER_COUNT_PER_PAGE


def fetch_order_item_list_by_year(handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page), inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    year_list = store_amazon.handle.get_year_list(handle)

    logging.info(
        "Check order of {year} ({year_index}/{total_year})".format(
            year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
        )
    )

    store_amazon.handle.set_progress_bar(
        handle,
        gen_status_label_by_yeart(year),
        store_amazon.handle.get_order_count(handle, year),
    )

    page = start_page
    is_skipped = False
    while True:
        if not store_amazon.handle.get_page_checked(handle, year, page):
            is_skipped_page, is_last = fetch_order_item_list_by_year_page(handle, year, page)

            if not is_skipped_page:
                store_amazon.handle.set_page_checked(handle, year, page)

            is_skipped |= is_skipped_page
            time.sleep(1)
        else:
            is_last = skip_order_item_list_by_year_page(handle, year, page)

        store_amazon.handle.store_order_info(handle)

        if is_last:
            break

        page += 1

    store_amazon.handle.get_progress_bar(handle, gen_status_label_by_yeart(year)).update()

    if not is_skipped:
        store_amazon.handle.set_year_checked(handle, year)


def fetch_order_count_by_year(handle, year):
    store_amazon.handle.set_status(
        handle,
        "注文件数を調べています... {target}".format(target=gen_target_text(year)),
    )

    # NOTE: 注文数が多い場合，実際の注文数は最初の方のページには表示されないので，
    # あり得ないページ数を指定する．
    visit_url(handle, gen_hist_url(year, 10000), inspect.currentframe().f_code.co_name)

    return parse_order_count(handle)


def fetch_order_count(handle):
    year_list = store_amazon.handle.get_year_list(handle)

    logging.info("Collect order count")

    store_amazon.handle.set_progress_bar(handle, STATUS_ORDER_COUNT, len(year_list))

    total_count = 0
    for year in year_list:
        if year == store_amazon.const.ARCHIVE_LABEL:
            count = fetch_order_count_by_year(handle, year)
            store_amazon.handle.set_order_count(handle, year, count)
            logging.info("Archive: {count:4,} orders".format(count=count))
        elif year >= store_amazon.handle.get_cache_last_modified(handle).year:
            count = fetch_order_count_by_year(handle, year)
            store_amazon.handle.set_order_count(handle, year, count)
            logging.info("Year {year}: {count:4,} orders".format(year=year, count=count))
        else:
            count = store_amazon.handle.get_order_count(handle, year)
            logging.info("Year {year}: {count:4,} orders [cached]".format(year=year, count=count))

        total_count += count
        store_amazon.handle.get_progress_bar(handle, STATUS_ORDER_COUNT).update()

    logging.info("Total order is {total_count:,}".format(total_count=total_count))

    store_amazon.handle.get_progress_bar(handle, STATUS_ORDER_COUNT).update()
    store_amazon.handle.store_order_info(handle)


def fetch_order_item_list_all_year(handle):
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    year_list = fetch_year_list(handle)
    fetch_order_count(handle)

    store_amazon.handle.set_progress_bar(
        handle, STATUS_ORDER_ITEM_ALL, store_amazon.handle.get_total_order_count(handle)
    )

    for year in year_list:
        if (
            (year == datetime.datetime.now().year)
            or (year == store_amazon.handle.get_cache_last_modified(handle).year)
            or (type(year) is str)
            or (not store_amazon.handle.get_year_checked(handle, year))
        ):
            fetch_order_item_list_by_year(handle, year)
        else:
            logging.info(
                "Done order of {year} ({year_index}/{total_year}) [cached]".format(
                    year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
                )
            )
            store_amazon.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(
                store_amazon.handle.get_order_count(handle, year)
            )

    store_amazon.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()


def fetch_order_item_list(handle):
    store_amazon.handle.set_status(handle, "巡回ロボットの準備をします...")
    driver, wait = store_amazon.handle.get_selenium_driver(handle)

    store_amazon.handle.set_status(handle, "注文履歴の収集を開始します...")

    try:
        fetch_order_item_list_all_year(handle)
    except:
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), store_amazon.handle.get_debug_dir_path(handle)
        )
        raise

    store_amazon.handle.set_status(handle, "注文履歴の収集が完了しました．")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    handle = store_amazon.handle.create(config)

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

            store_amazon.handle.set_year_list(handle, [year])

            count = fetch_order_count_by_year(handle, year)
            store_amazon.handle.set_order_count(handle, year, count)
            store_amazon.handle.set_progress_bar(handle, STATUS_ORDER_ITEM_ALL, count)

            fetch_order_item_list_by_year(handle, year, start_page)
    except:
        driver, wait = store_amazon.handle.get_selenium_driver(handle)
        logging.error(traceback.format_exc())
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), store_amazon.handle.get_debug_dir_path(handle)
        )
