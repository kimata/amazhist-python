#!/usr/bin/env python3
"""
商品情報の取得・解析を行う関数群

サムネイル画像の保存、カテゴリ情報の取得、商品詳細のパースなどを行います。
"""
from __future__ import annotations

import logging
import random
import re
import time

import my_lib.selenium_util
from selenium.webdriver.common.by import By

import amazhist.crawler
import amazhist.handle
import amazhist.parser


def fetch_item_category(handle, item_url: str) -> list[str]:
    """商品ページからカテゴリ情報を取得

    Args:
        handle: アプリケーションハンドル
        item_url: 商品ページのURL

    Returns:
        カテゴリのリスト（パンくずリスト）
    """
    # シャットダウン要求時はスキップ
    if amazhist.crawler.is_shutdown_requested():
        return []

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    category = []
    try:
        with my_lib.selenium_util.browser_tab(driver, item_url):
            breadcrumb_list = driver.find_elements(
                By.XPATH, "//div[contains(@class, 'a-breadcrumb')]//li//a"
            )
            category = [x.text for x in breadcrumb_list]
    except Exception as e:
        logging.warning(f"カテゴリの取得に失敗しました: {item_url}")
        amazhist.handle.record_error(
            handle,
            url=item_url,
            error_type="fetch_error",
            context="category",
            message=str(e),
        )

    return category


def _save_thumbnail(handle, item: dict, thumb_url: str) -> None:
    """サムネイル画像を保存

    Args:
        handle: アプリケーションハンドル
        item: 商品情報（asin を含む）
        thumb_url: サムネイル画像のURL
    """
    # シャットダウン要求時はスキップ
    if amazhist.crawler.is_shutdown_requested():
        return

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    thumb_path = amazhist.handle.get_thumb_path(handle, item)
    if thumb_path is None:
        return

    with my_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(By.XPATH, "//img").screenshot_as_png

        with open(thumb_path, "wb") as f:
            f.write(png_data)


def parse_item(handle, item_xpath: str) -> dict | None:
    """商品情報をパース（新形式）

    Args:
        handle: アプリケーションハンドル
        item_xpath: 商品要素のXPath

    Returns:
        商品情報の辞書、シャットダウン時は None
    """
    # シャットダウン要求時はスキップ
    if amazhist.crawler.is_shutdown_requested():
        return None

    driver, wait = amazhist.handle.get_selenium_driver(handle)

    # 商品名とリンク
    link = driver.find_element(
        By.XPATH,
        item_xpath + "//div[@data-component='itemTitle']//a",
    )
    name = link.text
    url = link.get_attribute("href") or ""

    # ASIN を URL から抽出（/dp/XXXX または /gp/product/XXXX 形式）
    asin_match = re.match(r".*/(?:dp|gp/product)/([^/?]+)", url) if url else None
    asin = asin_match.group(1) if asin_match else None

    time.sleep(0.5)
    category = fetch_item_category(handle, url) if url else []

    item = {
        "name": name,
        "url": url,
        "asin": asin,
        "category": category,
    }

    # サムネイル画像
    thumb_url = driver.find_element(
        By.XPATH, item_xpath + "//div[@data-component='itemImage']//img"
    ).get_attribute("src")

    if thumb_url:
        for retry in range(3):
            try:
                _save_thumbnail(handle, item, thumb_url)
                break
            except Exception as e:
                if retry < 2:
                    time.sleep(1)
                else:
                    logging.warning(f"サムネイル画像の取得に失敗しました: {name} ({str(e)})")
                    amazhist.handle.record_error(
                        handle,
                        url=thumb_url,
                        error_type="fetch_error",
                        context="thumbnail",
                        message=str(e),
                        item_name=name,
                    )

    # 価格
    price_elem = driver.find_elements(
        By.XPATH, item_xpath + "//div[@data-component='unitPrice']//span[contains(@class, 'a-offscreen')]"
    )
    if price_elem:
        # NOTE: a-offscreen クラスの要素は .text では空になることがあるため textContent を使用
        price_text = price_elem[0].get_attribute("textContent") or ""
        price = amazhist.parser.parse_price(price_text)
        if price is None:
            logging.warning(f"価格のパースに失敗しました: {price_text}")
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
            )
            price = 0
    else:
        logging.warning(f"価格が見つかりませんでした: {name}")
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


def _parse_item_giftcard(handle, item_xpath: str) -> dict:
    """ギフトカードの商品情報をパース（旧形式）

    Args:
        handle: アプリケーションハンドル
        item_xpath: 商品要素のXPath

    Returns:
        商品情報の辞書
    """
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    count = 1

    price_text = driver.find_element(
        By.XPATH,
        item_xpath + "//div[contains(@class, 'gift-card-instance')]/div[contains(@class, 'a-column')][1]",
    ).text
    price = amazhist.parser.parse_price(price_text) or 0

    seller = "アマゾンジャパン合同会社"
    condition = "新品"

    return {
        "count": count,
        "price": price,
        "seller": seller,
        "condition": condition,
        "kind": "Gift card",
    }


def _parse_item_default(handle, item_xpath: str) -> dict:
    """デフォルトの商品情報をパース（旧形式）

    Args:
        handle: アプリケーションハンドル
        item_xpath: 商品要素のXPath

    Returns:
        商品情報の辞書
    """
    driver, wait = amazhist.handle.get_selenium_driver(handle)

    count = int(
        my_lib.selenium_util.get_text(
            driver, item_xpath + '/..//span[contains(@class, "item-view-qty")]', "1"
        )
    )

    price_text = driver.find_element(By.XPATH, item_xpath + "//span[contains(@class, 'a-color-price')]").text
    price = amazhist.parser.parse_price(price_text) or 0
    price *= count

    seller = my_lib.selenium_util.get_text(
        driver,
        item_xpath + "//span[contains(@class, 'a-size-small') and contains(text(), '販売:')]",
        " アマゾンジャパン合同会社",
    ).split(" ", 2)[1]

    xpath_condition = (
        item_xpath
        + "//span[contains(@class, 'a-color-secondary') and contains(text(), 'コンディション：')]"
        + "/following-sibling::span[1]"
    )
    condition = my_lib.selenium_util.get_text(driver, xpath_condition, "新品")

    return {
        "count": count,
        "price": price,
        "seller": seller,
        "condition": condition,
        "kind": "Normal",
    }
