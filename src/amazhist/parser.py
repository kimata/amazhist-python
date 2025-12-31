#!/usr/bin/env python3
"""
HTMLテキストを解析するパース関数群

Selenium で取得したテキストデータを解析し、適切な型に変換します。
これらの関数は Selenium に依存せず、純粋なロジックとしてテスト可能です。
"""
from __future__ import annotations

import datetime
import re


def parse_date(date_text: str) -> datetime.datetime:
    """日付テキストをパース

    Args:
        date_text: 日付テキスト（例: "2025年01月15日"）

    Returns:
        datetime オブジェクト
    """
    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")


def parse_date_digital(date_text: str) -> datetime.datetime:
    """デジタル注文の日付テキストをパース

    Args:
        date_text: 日付テキスト（例: "2025/01/15"）

    Returns:
        datetime オブジェクト
    """
    return datetime.datetime.strptime(date_text, "%Y/%m/%d")


def parse_price(text: str) -> int | None:
    """価格テキストから数値を抽出

    Args:
        text: 価格テキスト（例: "￥1,500", "1,500円"）

    Returns:
        価格（整数）。パースできない場合は None
    """
    match = re.match(r".*?(\d{1,3}(?:,\d{3})*)", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None
