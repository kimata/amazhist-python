#!/usr/bin/env python3
"""
注文情報の取得・解析を行う関数群

注文ページの解析、注文件数の取得などを行います。
"""
from __future__ import annotations

import inspect
import logging
import re
import time

import my_lib.selenium_util
from selenium.webdriver.common.by import By

import amazhist.const
import amazhist.crawler
import amazhist.handle
import amazhist.item
import amazhist.parser


def _get_caller_name() -> str:
    """呼び出し元の関数名を取得"""
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        return "unknown"
    return frame.f_back.f_code.co_name


def _parse_order_digital(handle, order_info: dict) -> bool:
    """デジタル注文をパース

    Args:
        handle: アプリケーションハンドル
        order_info: 注文情報

    Returns:
        パースに成功したか
    """
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    date_text = driver.find_element(By.XPATH, '//td/b[contains(text(), "デジタル注文")]').text.split()[1]
    date = amazhist.parser.parse_date_digital(date_text)

    no = driver.find_element(By.XPATH, '//ul/li/b[contains(text(), "注文番号")]/..').text.split(": ")[1]

    item_xpath = "//tr[td[b[contains(text(), '注文商品')]]]/following-sibling::tr[1]"

    if len(driver.find_elements(By.XPATH, item_xpath + "/td[1]//a")) != 0:
        link = driver.find_element(By.XPATH, item_xpath + "/td[1]//a")
        name = link.text
        url = link.get_attribute("href") or ""
        asin_match = re.match(r".*/dp/([^/]+)/", url) if url else None
        asin = asin_match.group(1) if asin_match else None
        category = amazhist.item.fetch_item_category(handle, url) if url else []
    else:
        # NOTE: もう販売ページが存在しない場合．
        name = driver.find_element(By.XPATH, item_xpath + "/td[1]//b").text
        url = None
        asin = None
        category = []

    count = 1

    price_text = driver.find_element(By.XPATH, item_xpath + "/td[2]").text
    price = amazhist.parser.parse_price(price_text) or 0

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


def _parse_order_default(handle, order_info: dict) -> bool:
    """通常の注文をパース

    Args:
        handle: アプリケーションハンドル
        order_info: 注文情報

    Returns:
        パースに成功したか（1つ以上の商品を取得できたか）
    """
    ITEM_XPATH = '//div[@data-component="purchasedItems"]'

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    date_text = driver.find_element(
        By.XPATH, '//div[@data-component="orderDate"]//span'
    ).text.strip().split()[0]
    date = amazhist.parser.parse_date(date_text)

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
        # シャットダウン要求時は終了
        if amazhist.crawler.is_shutdown_requested():
            break

        item_xpath = "(" + ITEM_XPATH + f")[{i + 1}]"

        item = amazhist.item.parse_item(handle, item_xpath)
        if item is None:
            # シャットダウン要求により中断
            break

        item |= item_base

        logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))

        amazhist.handle.record_item(handle, item)
        is_unempty = True

    return is_unempty


def parse_order(handle, order_info: dict) -> bool:
    """注文をパース

    注文の種類（デジタル/通常）を判別し、適切なパース関数を呼び出します。

    Args:
        handle: アプリケーションハンドル
        order_info: 注文情報

    Returns:
        パースに成功したか
    """
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    date_str = order_info["date"].strftime("%Y-%m-%d")
    logging.info(f"注文をパースしています: {date_str} - {order_info['no']}")

    if len(driver.find_elements(By.XPATH, "//b[contains(text(), 'デジタル注文')]")) != 0:
        is_unempty = _parse_order_digital(handle, order_info)
    else:
        is_unempty = _parse_order_default(handle, order_info)

    return is_unempty


def parse_order_count(handle, year) -> int:
    """指定年の注文件数を取得

    Args:
        handle: アプリケーションハンドル
        year: 年（または amazhist.const.ARCHIVE_LABEL）

    Returns:
        注文件数
    """
    ORDER_COUNT_XPATH = "//span[contains(@class, 'num-orders')]"
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    caller_name = _get_caller_name()

    # NOTE: 注文数が多い場合，実際の注文数は最初の方のページには表示されないので，
    # あり得ないページ数を指定する．
    amazhist.crawler.visit_url(
        handle, amazhist.crawler.gen_hist_url(year, 10000), caller_name
    )

    if my_lib.selenium_util.xpath_exists(driver, ORDER_COUNT_XPATH):
        order_count_text = driver.find_element(By.XPATH, ORDER_COUNT_XPATH).text

        match = re.match(r"(\d+)", order_count_text)
        return int(match.group(1)) if match else 0
    else:
        time.sleep(1)

        # NOTE: 注文数が表示されない場合，注文数が少ない可能性が高いので，先頭のページを表示する．
        amazhist.crawler.visit_url(
            handle, amazhist.crawler.gen_hist_url(year, 1), caller_name
        )

        if my_lib.selenium_util.xpath_exists(driver, ORDER_XPATH):
            count = len(driver.find_elements(By.XPATH, ORDER_XPATH))
            logging.info(count)
            return count
        else:
            logging.warning("注文件数の取得に失敗しました")
            return 0
