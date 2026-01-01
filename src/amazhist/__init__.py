#!/usr/bin/env python3
"""
amazhist パッケージ

Amazon.co.jp の購入履歴を自動収集し、サムネイル付き Excel ファイルとして出力するツール
"""

from amazhist import config
from amazhist import const
from amazhist import crawler
from amazhist import database
from amazhist import handle
from amazhist import history
from amazhist import item
from amazhist import order
from amazhist import order_list
from amazhist import parser

__all__ = [
    "config",
    "const",
    "crawler",
    "database",
    "handle",
    "history",
    "item",
    "order",
    "order_list",
    "parser",
]
