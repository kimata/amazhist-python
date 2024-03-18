#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amazon の購入履歴情報を取得します．

Usage:
  store_amazon.py [-c CONFIG] [-y YEAR] [-s PAGE]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -y YEAR      : 購入年．
  -s PAGE      : 開始ページ．[default: 1]
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
import PIL.Image
import functools
import enlighten

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from selenium_util import clean_dump, clear_cache, create_driver, dump_page, random_sleep, get_text

CAPTCHA_RETRY_COUNT = 2
LOGIN_RETRY_COUNT = 2
CAPTCHA_IMAGE_FILE = "captcha.png"

DEBUG_USE_DUMP = False
DEBUG_DUMP = True

HIST_URL = "https://www.amazon.co.jp/your-orders/orders"
HIST_URL_BY_YEAR_PAGE = (
    "https://www.amazon.co.jp/your-orders/orders?timeFilter=year-{year}&startIndex={start}"
)


def get_queue_dirver(handle):
    return (handle["selenium"]["driver"], handle["selenium"]["wait"])


def record_item(handle, item):
    handle["item_list"].append(item)


def set_year_list(handle, year_list):
    handle["year_list"] = year_list


def set_order_count(handle, year, order_count):
    handle["order_count"][year] = order_count


def get_order_count(handle, year):
    return handle["order_count"][year]


def get_total_order_count(handle):
    return functools.reduce(lambda a, b: a + b, handle["order_count"].values())


def get_year_list(handle):
    return handle["year_list"]


def set_progress_bar(handle, desc, total):
    handle["progress_bar"][desc] = handle["progress_manager"].counter(total=total, desc=desc)


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]


def wait_for_loading(handle):
    driver, wait = get_queue_dirver(handle)

    wait.until(EC.presence_of_all_elements_located)
    time.sleep(0.1)


def resolve_captcha(handle):
    driver, wait = get_queue_dirver(handle)

    logging.info("Try to resolve CAPTCHA")

    for i in range(CAPTCHA_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to resolve CAPTCHA")

        captcha = PIL.Image.open(
            io.BytesIO(driver.find_element(By.XPATH, '//img[@alt="captcha"]').screenshot_as_png)
        )
        captcha_img_path = pathlib.Path(os.path.splitext(__file__)[0]).parent.parent / CAPTCHA_IMAGE_FILE

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
    driver, wait = get_queue_dirver(handle)

    if len(driver.find_elements(By.XPATH, '//input[@id="ap_email" and @type="text"]')) != 0:
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').clear()
        driver.find_element(By.XPATH, '//input[@id="ap_email"]').send_keys(handle["config"]["login"]["user"])

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
    driver, wait = get_queue_dirver(handle)

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


def visit_url(handle, url, file_name):
    driver, wait = get_queue_dirver(handle)
    driver.get(url)

    wait_for_loading(handle)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")


def parse_item(handle, item_xpath):
    driver, wait = get_queue_dirver(handle)

    link = driver.find_element(
        By.XPATH,
        item_xpath + "//a[contains(@class, 'a-link-normal')]",
    )
    name = link.text
    url = link.get_attribute("href")
    asin = re.match(r".*/gp/product/([^/]+)/", url).group(1)

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
        "name": name,
        "url": url,
        "asin": asin,
        "count": count,
        "price": price,
        "seller": seller,
        "condition": condition,
    }


def parse_order(handle, link):
    ITEM_XPATH = '//div[contains(@data-component, "shipments")]//div[contains(@class, "yohtmlc-item")]'

    driver, wait = get_queue_dirver(handle)

    link.click()
    wait_for_loading(handle)

    dump_page(driver, int(random.random() * 100))

    keep_logged_on(handle)

    dump_page(driver, int(random.random() * 100))

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

        record_item(handle, item)
        is_unempty = True

    driver.back()
    wait_for_loading(handle)

    return is_unempty


def get_order_count_by_year(handle):
    driver, wait = get_queue_dirver(handle)

    order_count_text = driver.find_element(By.XPATH, "//span[contains(@class, 'num-orders')]").text

    return int(re.match(r"(\d+)", order_count_text).group(1))


def get_total_page_by_year(handle):
    ORDER_PER_PAGE = 10

    return math.ceil(float(get_order_count_by_year(handle)) / ORDER_PER_PAGE)


def get_order_item_list_by_year_page(handle, year, page):
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = get_queue_dirver(handle)

    visit_url(handle, gen_hist_url(year, page), inspect.currentframe().f_code.co_name)
    keep_logged_on(handle)

    total_page = get_total_page_by_year(handle)

    logging.info(
        "Check order of {year} page {page}/{total_page}".format(year=year, page=page, total_page=total_page)
    )
    logging.info("URL: {url}".format(url=driver.current_url))

    is_unempty = False
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

        logging.info("Parse order: {date} - {no}".format(date=date.strftime("%Y-%m-%d"), no=no))

        link = driver.find_element(
            By.XPATH, order_xpath + "//a[contains(@class, 'yohtmlc-order-details-link')]"
        )

        if not parse_order(handle, link):
            logging.warning("Failed to parse order of {no}".foramt(no=no))
        else:
            is_unempty = True

        get_progress_bar(handle, "Year {year}".format(year=year)).update()
        get_progress_bar(handle, "All").update()

        time.sleep(1)

    return is_unempty and (page != total_page)


def parse_year_list(handle):
    driver, wait = get_queue_dirver(handle)

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

    set_year_list(handle, year_list)

    return year_list


def get_order_item_list_by_year(handle, year, start_page=1):
    visit_url(handle, gen_hist_url(year, start_page), inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    year_list = get_year_list(handle)

    logging.info(
        "Check order of {year} ({year_index}/{total_year})".format(
            year=year, year_index=year_list.index(year) + 1, total_year=len(year_list)
        )
    )

    set_progress_bar(handle, "Year {year}".format(year=year), get_order_count(handle, year))

    page = start_page
    while True:
        is_last = not get_order_item_list_by_year_page(handle, year, page)

        if is_last:
            break

        page += 1

    get_progress_bar(handle, "Year {year}".format(year=year)).update()


def parse_order_count(handle):
    year_list = get_year_list(handle)

    logging.info("Collect order count")

    set_progress_bar(handle, "Collect order count", len(year_list))

    total_count = 0
    for year in year_list:
        visit_url(handle, gen_hist_url(year, 1), inspect.currentframe().f_code.co_name)

        count = get_order_count_by_year(handle)
        total_count += count

        logging.info("Year {year}: {count:,} orders".format(year=year, count=count))

        set_order_count(handle, year, count)
        get_progress_bar(handle, "Collect order count").update()

        time.sleep(1)

    logging.info("Total order is {total_count:,}".format(total_count=total_count))

    get_progress_bar(handle, "Collect order count").update()


def get_order_item_list(handle):
    driver, wait = get_queue_dirver(handle)

    visit_url(handle, HIST_URL, inspect.currentframe().f_code.co_name)

    keep_logged_on(handle)

    year_list = parse_year_list(handle)
    parse_order_count(handle)

    set_progress_bar(handle, "All", get_total_order_count(handle))

    for year in year_list:
        get_order_item_list_by_year(handle, year)

    get_progress_bar(handle, "All").update()


def create_handle(config):
    driver = create_driver(os.path.splitext(__file__)[0], pathlib.Path(config["data"]["selenium"]))
    wait = WebDriverWait(driver, 5)

    clear_cache(driver)

    return {
        "selenium": {
            "driver": driver,
            "wait": wait,
        },
        "progress_manager": enlighten.get_manager(),
        "progress_bar": {},
        "config": config,
        "year_list": [],
        "order_count": {},
        "item_list": [],
    }


if __name__ == "__main__":
    import logger
    from config import load_config
    from docopt import docopt

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])
    handle = create_handle(config)

    if args["-y"] is None:
        get_order_item_list(handle)
    else:
        year = int(args["-y"])
        start_page = int(args["-s"])

        get_order_item_list_by_year(handle, year, start_page)
