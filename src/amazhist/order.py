#!/usr/bin/env python3
"""
注文情報の取得・解析を行う関数群

注文ページの解析、注文件数の取得などを行います。

Usage:
  order.py [-c CONFIG] -n ORDER_NO

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -n ORDER_NO   : 注文番号．
"""
from __future__ import annotations

import datetime
import inspect
import logging
import re
import time
from dataclasses import dataclass

import my_lib.selenium_util
from selenium.webdriver.common.by import By

import amazhist.config
import amazhist.const
import amazhist.crawler
import amazhist.handle
import amazhist.item
import amazhist.parser


@dataclass(frozen=True)
class Order:
    """注文情報"""

    date: datetime.datetime
    no: str
    url: str
    time_filter: int | None = None  # _retry_failed_orders で None
    page: int | None = None  # _retry_failed_orders で None


def _get_caller_name() -> str:
    """呼び出し元の関数名を取得"""
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        return "unknown"
    return frame.f_back.f_code.co_name


def _parse_order_digital(handle: amazhist.handle.Handle, order: Order) -> bool:
    """デジタル注文をパース

    Args:
        handle: アプリケーションハンドル
        order: 注文情報

    Returns:
        パースに成功したか
    """
    driver, wait = handle.get_selenium_driver()

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

    item = amazhist.item.Item(
        name=name,
        date=date,
        no=no,
        url=url,
        asin=asin,
        count=count,
        price=price,
        category=tuple(category),
        seller=seller,
        condition=condition,
        kind=kind,
        order_time_filter=order.time_filter,
        order_page=order.page,
    )

    logging.info("{name} {price:,}円".format(name=item.name, price=item.price))

    handle.record_item(item)

    return True


def _parse_order_default(handle: amazhist.handle.Handle, order: Order) -> bool:
    """通常の注文をパース

    Args:
        handle: アプリケーションハンドル
        order: 注文情報

    Returns:
        パースに成功したか（1つ以上の商品を取得できたか）
    """
    ITEM_XPATH = '//div[@data-component="purchasedItems"]'

    driver, wait = handle.get_selenium_driver()

    is_unempty = False
    for i in range(len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        # シャットダウン要求時は終了
        if amazhist.crawler.is_shutdown_requested():
            break

        item_xpath = "(" + ITEM_XPATH + f")[{i + 1}]"

        item = amazhist.item.parse_item(handle, item_xpath, order)
        if item is None:
            # シャットダウン要求により中断
            break

        logging.info("{name} {price:,}円".format(name=item.name, price=item.price))

        handle.record_item(item)
        is_unempty = True

    return is_unempty


def parse_order(handle: amazhist.handle.Handle, order: Order) -> bool:
    """注文をパース

    注文の種類（デジタル/通常）を判別し、適切なパース関数を呼び出します。

    Args:
        handle: アプリケーションハンドル
        order: 注文情報

    Returns:
        パースに成功したか
    """
    driver, wait = handle.get_selenium_driver()

    date_str = order.date.strftime("%Y-%m-%d")
    logging.info(f"注文をパースしています: {date_str} - {order.no}")

    if len(driver.find_elements(By.XPATH, "//b[contains(text(), 'デジタル注文')]")) != 0:
        is_unempty = _parse_order_digital(handle, order)
    else:
        is_unempty = _parse_order_default(handle, order)

    return is_unempty


def _extract_order_count_from_page(driver) -> int | None:
    """ページ内の注文件数を抽出

    <span class="num-orders">64件</span> のような要素から件数を取得します。

    Args:
        driver: Selenium WebDriver

    Returns:
        注文件数（見つからない場合は None）
    """
    ORDER_COUNT_TEXT_XPATH = "//span[contains(@class, 'num-orders')]"

    elems = driver.find_elements(By.XPATH, ORDER_COUNT_TEXT_XPATH)
    for elem in elems:
        text = elem.text
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def parse_order_count(handle: amazhist.handle.Handle, year: int) -> int:
    """指定年の注文件数を取得

    Args:
        handle: アプリケーションハンドル
        year: 年

    Returns:
        注文件数
    """
    ORDER_COUNT_XPATH = "//span[contains(@class, 'num-orders')]"
    ORDER_XPATH = '//div[contains(@class, "order-card js-order-card")]'

    driver, wait = handle.get_selenium_driver()

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

        # まずページ内の「○件の注文」テキストから件数を取得
        page_count_text = _extract_order_count_from_page(driver)
        if page_count_text is not None:
            return page_count_text

        # テキストが見つからない場合は注文カードを数える（フォールバック）
        if my_lib.selenium_util.xpath_exists(driver, ORDER_XPATH):
            count = len(driver.find_elements(By.XPATH, ORDER_XPATH))

            # 1ページあたりの最大件数の場合、次のページがあるか確認
            if count == amazhist.const.ORDER_COUNT_PER_PAGE:
                page = 2
                while True:
                    amazhist.crawler.visit_url(
                        handle, amazhist.crawler.gen_hist_url(year, page), caller_name
                    )
                    page_count = len(driver.find_elements(By.XPATH, ORDER_XPATH))
                    if page_count == 0:
                        break
                    count += page_count
                    if page_count < amazhist.const.ORDER_COUNT_PER_PAGE:
                        break
                    page += 1

            # フォールバックで注文カードを数えた場合はエラーとして記録
            # 後から年単位で再巡回可能にする
            logging.warning(f"{year}年: 注文件数要素が見つからず、注文カードを数えました（{count}件）")
            handle.record_or_update_error(
                url=amazhist.crawler.gen_hist_url(year, 1),
                error_type=amazhist.const.ERROR_TYPE_ORDER_COUNT_FALLBACK,
                context="year",
                message=f"注文件数要素が見つからず、注文カードを数えました（{count}件）",
                order_year=year,
            )

            return count
        else:
            logging.warning("注文件数の取得に失敗しました")
            return 0


######################################################################
if __name__ == "__main__":
    import random
    import traceback

    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    assert __doc__ is not None
    args = docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    handle = amazhist.handle.Handle(config=amazhist.config.Config.load(config))

    try:
        no = args["-n"]
        amazhist.crawler.visit_url(handle, amazhist.crawler.gen_order_url(no), "main")
        amazhist.crawler._keep_logged_on(handle)

        parse_order(handle, Order(date=datetime.datetime.now(), no=no, url=amazhist.crawler.gen_order_url(no), page=1, time_filter=None))
    except Exception:
        driver, wait = handle.get_selenium_driver()
        logging.error(traceback.format_exc())
        my_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), handle.config.debug_dir_path
        )
