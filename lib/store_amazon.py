#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amazon の購入履歴情報を取得します．

Usage:
  store_amazon.py [-c CONFIG] [-y YEAR] [-s PAGE] [-n ORDER_NO]
  store_amazon.py [-c CONFIG] -n ORDER_NO

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -y YEAR      : 購入年．
  -s PAGE      : 開始ページ．[default: 1]
  -n ORDER_NO  : 注文番号
"""

import os
import re
import math
import pathlib
import datetime
import io
import random
import logging
import inspect
import time
import traceback
import PIL.Image

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from selenium_util import clean_dump, clear_cache, dump_page, get_text

import crawl_handle

CAPTCHA_RETRY_COUNT = 2
LOGIN_RETRY_COUNT = 2
CAPTCHA_IMAGE_FILE = "captcha.png"

DEBUG_USE_DUMP = False
DEBUG_DUMP = True

HIST_URL = "https://www.amazon.co.jp/your-orders/orders"
HIST_URL_BY_YEAR_PAGE = (
    "https://www.amazon.co.jp/your-orders/orders?timeFilter=year-{year}&startIndex={start}"
)
HIST_URL_BY_ORDER_NO = "https://www.amazon.co.jp/gp/your-account/order-details/?orderID={no}"


def wait_for_loading(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    wait.until(EC.presence_of_all_elements_located)
    time.sleep(0.1)


def resolve_captcha(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    logging.info("Try to resolve CAPTCHA")

    for i in range(CAPTCHA_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to resolve CAPTCHA")

        captcha = PIL.Image.open(
            io.BytesIO(driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png)
        )
        captcha_img_path = pathlib.Path(pathlib.Path(os.path.dirname(__file__))).parent / CAPTCHA_IMAGE_FILE

        logging.info("Save image: {path}".format(path=captcha_img_path))
        captcha.save(captcha_img_path)

        captcha_text = input("{img_file} に書かれているテキストを入力してくだい: ".format(img_file=CAPTCHA_IMAGE_FILE))

        driver.find_element(By.XPATH, '//input[@name="cvf_captcha_input"]').send_keys(captcha_text.strip())
        driver.find_element(By.XPATH, '//input[@type="submit"]').click()

        wait_for_loading(handle)

        if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) == 0:
            return

        logging.info("Failed to resolve CAPTCHA")
        time.sleep(1)

    logging.error("Give up to resolve CAPTCHA")
    raise "画像認証を解決できませんでした．"


def execute_login(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_email" and @type!="hidden"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(handle["config"]["login"]["user"])

        if len(driver.find_elements(By.XPATH, '//input[@id="continue"]')) != 0:
            driver.find_element(By.XPATH, '//input[@id="continue"]').click()
            wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_password"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_password"]').send_keys(
            handle["config"]["login"]["pass"]
        )

    if len(driver.find_elements(By.XPATH, '//input[@id="rememberMe"]')) != 0:
        if not driver.find_element(By.XPATH, '//input[@name="rememberMe"]').get_attribute("checked"):
            driver.find_element(By.XPATH, '//input[@name="rememberMe"]').click()

    driver.find_element(By.XPATH, '//input[@id="signInSubmit"]').click()

    wait_for_loading(handle)

    if len(driver.find_elements(By.XPATH, '//input[@name="cvf_captcha_input"]')) != 0:
        resolve_captcha(handle)


def keep_logged_on(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

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

        logging.info("Failed to login")
        time.sleep(1)

    logging.error("Give up to login")
    raise "ログインに失敗しました．"


def gen_hist_url(year, page):
    return HIST_URL_BY_YEAR_PAGE.format(year=year, start=10 * (page - 1))


def gen_order_url(no):
    return HIST_URL_BY_ORDER_NO.format(no=no)


def visit_url(handle, url, file_name):
    driver, wait = crawl_handle.get_queue_dirver(handle)
    driver.get(url)

    wait_for_loading(handle)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")


def parse_item_giftcard(handle, item_xpath):
    driver, wait = crawl_handle.get_queue_dirver(handle)

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
    }


def parse_item_default(handle, item_xpath):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    count = int(get_text(driver, item_xpath + "//span[contains(@class, 'item-view-qty')]", "1"))

    price_text = driver.find_element(By.XPATH, item_xpath + "//span[contains(@class, 'a-color-price')]").text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    seller = get_text(
        driver,
        item_xpath + "//span[contains(@class, 'a-size-small') and contains(text(), '販売:')]",
        " アマゾンジャパン合同会社",
    ).split(" ", 2)[1]

    condition = get_text(
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
    }


def parse_item(handle, item_xpath):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    link = driver.find_element(
        By.XPATH,
        item_xpath + "//a[contains(@class, 'a-link-normal')]",
    )
    name = link.text
    url = link.get_attribute("href")
    asin = re.match(r".*/gp/product/([^/]+)/", url).group(1)

    item = {
        "name": name,
        "url": url,
        "asin": asin,
    }

    if len(driver.find_elements(By.XPATH, item_xpath + "//div[contains(@class, 'gift-card-instance')]")) != 0:
        return item | parse_item_giftcard(handle, item_xpath)
    else:
        return item | parse_item_default(handle, item_xpath)


def parse_order_kindle(handle, date, no):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    # //*[@id="digitalOrderSummaryContainer"]/div[1]/table[2]/tbody/tr[2]/td/table/tbody/tr/td[3]/table/tbody/tr[1]/td/table/tbody/tr[2]/td[1]

    # link = driver.find_element(
    #     By.XPATH,
    #     item_xpath + "//a[contains(@class, 'a-link-normal')]",
    # )
    # name = link.text
    # url = link.get_attribute("href")
    # asin = re.match(r".*/gp/product/([^/]+)/", url).group(1)

    # count = int(get_text(driver, item_xpath + "//span[contains(@class, 'item-view-qty')]", "1"))

    # price_text = driver.find_element(By.XPATH, item_xpath + "//span[contains(@class, 'a-color-price')]").text
    # price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    # seller = get_text(
    #     driver,
    #     item_xpath + "//span[contains(@class, 'a-size-small') and contains(text(), '販売:')]",
    #     " アマゾンジャパン合同会社",
    # ).split(" ", 2)[1]

    # condition = "新品"

    # return {
    #     "name": name,
    #     "url": url,
    #     "asin": asin,
    #     "count": count,
    #     "price": price,
    #     "seller": seller,
    #     "condition": condition,
    # }
    return False


def parse_order_default(handle, date, no):
    ITEM_XPATH = '//div[contains(@data-component, "shipments")]//div[contains(@class, "yohtmlc-item")]'

    driver, wait = crawl_handle.get_queue_dirver(handle)

    date_text = driver.find_element(
        By.XPATH, '//span[contains(@class, "order-date-invoice-item")][1]'
    ).text.split()[1]
    date = parse_date(date_text)

    no = driver.find_element(By.XPATH, '//span[contains(@class, "order-date-invoice-item")]/bdi').text

    order = {"date": date, "no": no}

    is_unempty = False
    for i in range(len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        item_xpath = "(" + ITEM_XPATH + ")[{index}]".format(index=i + 1)

        item = parse_item(handle, item_xpath)
        item |= order

        logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))

        crawl_handle.record_item(handle, item)
        is_unempty = True

    return is_unempty


def parse_order(handle, date, no):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    logging.info("Parse order: {date} - {no}".format(date=date.strftime("%Y-%m-%d"), no=no))

    if len(driver.find_elements(By.XPATH, "//b[contains(text(), 'デジタル注文')]")) != 0:
        is_unempty = parse_order_kindle(handle, date, no)
    else:
        is_unempty = parse_order_default(handle, date, no)

    return is_unempty


def get_order_count_by_year(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    order_count_text = driver.find_element(By.XPATH, "//span[contains(@class, 'num-orders')]").text

    return int(re.match(r"(\d+)", order_count_text).group(1))


def get_total_page_by_year(handle):
    ORDER_PER_PAGE = 10

    return math.ceil(float(get_order_count_by_year(handle)) / ORDER_PER_PAGE)


def fetch_order_item_list_by_year_page(handle, year, page):
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = crawl_handle.get_queue_dirver(handle)

    visit_url(handle, gen_hist_url(year, page), inspect.currentframe().f_code.co_name)
    keep_logged_on(handle)

    total_page = get_total_page_by_year(handle)

    logging.info(
        "Check order of {year} page {page}/{total_page}".format(year=year, page=page, total_page=total_page)
    )
    logging.info("URL: {url}".format(url=driver.current_url))

    is_skipped = False
    for i in range(len(driver.find_elements(By.XPATH, ORDER_XPATH))):
        order_xpath = ORDER_XPATH + "[{index}]".format(index=i + 1)

        date_text = driver.find_element(
            By.XPATH, order_xpath + "//div[contains(@class, 'a-row')]/span[contains(@class, 'value')]"
        ).text
        date = parse_date(date_text)

        no = driver.find_element(
            By.XPATH,
            order_xpath + "//div[contains(@class, 'yohtmlc-order-id')]/span[contains(@class, 'value')]",
        ).text

        if not crawl_handle.get_order_stat(handle, no):
            link = driver.find_element(
                By.XPATH, order_xpath + "//a[contains(@class, 'yohtmlc-order-details-link')]"
            )

            current_url = driver.current_url

            link.click()
            wait_for_loading(handle)

            keep_logged_on(handle)

            if not parse_order(handle, date, no):
                logging.warning("Failed to parse order of {no}".format(no=no))
                is_skipped = True

            # NOTE: Kindle 購入の場合，注文詳細アクセス時にログイン処理が行われている可能性があり，
            # その場合は driver.back() では都合が悪いので，明示的に元の URL に戻す．
            visit_url(handle, current_url, inspect.currentframe().f_code.co_name)

            time.sleep(0.5)
        else:
            logging.info("Done order: {date} - {no} [cached]".format(date=date.strftime("%Y-%m-%d"), no=no))

        crawl_handle.get_progress_bar(handle, "Year {year}".format(year=year)).update()
        crawl_handle.get_progress_bar(handle, "All").update()

    crawl_handle.store_order_info(handle)

    return (is_skipped, page == total_page)


def fetch_year_list(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    driver.find_element(
        By.XPATH, "//form[@action='/your-orders/orders']//span[contains(@class, 'a-dropdown-prompt')]"
    ).click()

    wait_for_loading(handle)

    year_list = list(
        reversed(
            list(
                map(
                    lambda label: int(label.replace("年", "")),
                    filter(
                        lambda label: re.match(r"\d+年", label),
                        map(
                            lambda elem: elem.text,
                            driver.find_elements(
                                By.XPATH,
                                "//div[contains(@class, 'a-popover-wrapper')]//li",
                            ),
                        ),
                    ),
                )
            )
        )
    )

    crawl_handle.set_year_list(handle, year_list)

    return year_list


def fetch_order_item_list_by_year(handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page), inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    year_list = crawl_handle.get_year_list(handle)

    logging.info(
        "Check order of {year} ({year_index}/{total_year})".format(
            year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
        )
    )

    crawl_handle.set_progress_bar(
        handle, "Year {year}".format(year=year), crawl_handle.get_order_count(handle, year)
    )

    page = start_page
    is_skipped = False
    while True:
        is_skipped_page, is_last = fetch_order_item_list_by_year_page(handle, year, page)
        is_skipped |= is_skipped_page

        if is_last:
            break

        page += 1

    crawl_handle.get_progress_bar(handle, "Year {year}".format(year=year)).update()

    if not is_skipped:
        crawl_handle.set_year_checked(handle, year)


def fetch_order_count_by_year(handle, year):
    # NOTE: 注文数が多い場合，実際の注文数は最初の方のページには表示されないので，
    # あり得ないページ数を指定する．
    visit_url(handle, gen_hist_url(year, 10000), inspect.currentframe().f_code.co_name)

    return get_order_count_by_year(handle)


def fetch_order_count(handle):
    year_list = crawl_handle.get_year_list(handle)

    logging.info("Collect order count")

    crawl_handle.set_progress_bar(handle, "Collect order count", len(year_list))

    total_count = 0
    for year in year_list:
        if year >= crawl_handle.get_cache_last_modified(handle).year:
            count = fetch_order_count_by_year(handle, year)
            crawl_handle.set_order_count(handle, year, count)
            logging.info("Year {year}: {count:,} orders".format(year=year, count=count))
            time.sleep(0.5)
        else:
            count = crawl_handle.get_order_count(handle, year)
            logging.info("Year {year}: {count:,} orders [cached]".format(year=year, count=count))

        total_count += count
        crawl_handle.get_progress_bar(handle, "Collect order count").update()

    logging.info("Total order is {total_count:,}".format(total_count=total_count))

    crawl_handle.get_progress_bar(handle, "Collect order count").update()
    crawl_handle.store_order_info(handle)


def get_order_item_list_impl(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    visit_url(handle, HIST_URL, inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    year_list = fetch_year_list(handle)
    fetch_order_count(handle)

    crawl_handle.set_progress_bar(handle, "All", crawl_handle.get_total_order_count(handle))

    for year in year_list:
        if not crawl_handle.get_year_checked(handle, year):
            fetch_order_item_list_by_year(handle, year)
        else:
            logging.info(
                "Done order of {year} ({year_index}/{total_year}) [cached]".format(
                    year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
                )
            )
            crawl_handle.get_progress_bar(handle, "All").update(crawl_handle.get_order_count(handle, year))

    crawl_handle.get_progress_bar(handle, "All").update()


def get_order_item_list(handle):
    driver, wait = crawl_handle.get_queue_dirver(handle)

    try:
        get_order_item_list_impl(handle)
    except:
        dump_page(driver, int(random.random() * 100))
        raise


if __name__ == "__main__":
    import logger
    from config import load_config
    from docopt import docopt

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])
    handle = crawl_handle.create(config)

    try:
        if args["-n"] is not None:
            no = args["-n"]
            visit_url(handle, gen_order_url(no), inspect.currentframe().f_code.co_name)
            parse_order(handle, datetime.datetime.now(), no)
        elif args["-y"] is None:
            get_order_item_list(handle)
        else:
            year = int(args["-y"])
            start_page = int(args["-s"])

            crawl_handle.set_year_list(handle, [year])

            count = fetch_order_count_by_year(handle, year)
            crawl_handle.set_order_count(handle, year, count)
            crawl_handle.set_progress_bar(handle, "All", count)

            fetch_order_item_list_by_year(handle, year, start_page)
    except:
        driver, wait = crawl_handle.get_queue_dirver(handle)
        logging.error(traceback.format_exc())
        dump_page(driver, int(random.random() * 100))
