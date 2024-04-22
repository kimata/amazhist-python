#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amazon の購入履歴情報をエクセルファイルに書き出します．

Usage:
  order_history.py [-c CONFIG] [-o EXCEL]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o EXCEL      : CONFIG を設定ファイルとして読み込んで実行します．[default: amazhist.xlsx]
"""

import logging

import openpyxl
import openpyxl.utils
import openpyxl.styles
import openpyxl.drawing.image
import openpyxl.drawing.xdr
import openpyxl.drawing.spreadsheet_drawing

import local_lib.openpyxl_util
import store_amazon.handle
import store_amazon.crawler

STATUS_INSERT_ITEM = "[generate] Insert item"
STATUS_ALL = "[generate] Excel file"

SHEET_DEF = {
    "SHEET_TITLE": "【アマゾン】購入",
    "TABLE_HEADER": {
        "row": {
            "pos": 2,
            "height": 80,
        },
        "col": {
            "date": {
                "label": "日付",
                "pos": 2,
                "width": 23,
                "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
            },
            "name": {
                "label": "商品名",
                "pos": 3,
                "width": 70,
                "wrap": True,
                "format": "@",
            },
            "image": {
                "label": "画像",
                "pos": 4,
                "width": 12,
            },
            "count": {
                "label": "数量",
                "pos": 5,
                "format": "0_ ",
                "width": 8,
            },
            "price": {
                "label": "価格",
                "pos": 6,
                "width": 16,
                "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
            },
            "category": {
                "label": "カテゴリ",
                "pos": 7,
                "length": 3,
                "width": 20,
                "wrap": True,
            },
            "seller": {
                "label": "売り手",
                "pos": 10,
                "width": 29,
                "format": "@",
                "wrap": True,
            },
            "asin": {
                "label": "商品ID(ASIN)",
                "pos": 11,
                "width": 17,
                "format": "@",
                "link_func": lambda item: item["url"],
            },
            "no": {
                "label": "注文番号",
                "pos": 12,
                "width": 28,
                "format": "@",
                "link_func": lambda item: store_amazon.crawler.gen_order_url(item["no"]),
            },
        },
    },
}


def generate_sheet(handle, book):
    item_list = store_amazon.handle.get_item_list(handle)

    store_amazon.handle.set_progress_bar(handle, STATUS_INSERT_ITEM, len(item_list))

    local_lib.openpyxl_util.generate_list_sheet(
        handle,
        book,
        item_list,
        SHEET_DEF,
        lambda item: store_amazon.handle.get_thumb_path(handle, item),
        store_amazon.handle.set_status,
        lambda: store_amazon.handle.get_progress_bar(handle, STATUS_ALL).update(),
        lambda: store_amazon.handle.get_progress_bar(handle, STATUS_INSERT_ITEM).update(),
    )


def generate_table_excel(handle, excel_file):
    store_amazon.handle.set_status(handle, "エクセルファイルの作成を開始します...")
    store_amazon.handle.set_progress_bar(handle, STATUS_ALL, 5)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = store_amazon.handle.get_excel_font(handle)

    store_amazon.handle.get_progress_bar(handle, STATUS_ALL).update()

    generate_sheet(handle, book)

    book.remove(book.worksheets[0])

    store_amazon.handle.set_status(handle, "エクセルファイルを書き出しています...")

    book.save(excel_file)

    store_amazon.handle.get_progress_bar(handle, STATUS_ALL).update()

    book.close()

    store_amazon.handle.get_progress_bar(handle, STATUS_ALL).update()

    store_amazon.handle.set_status(handle, "完了しました！")

    logging.info("Complete to Generate excel file")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    excel_file = args["-o"]

    handle = store_amazon.handle.create(config)

    generate_table_excel(handle, excel_file)

    store_amazon.handle.finish(handle)
