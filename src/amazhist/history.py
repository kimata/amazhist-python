#!/usr/bin/env python3
"""
Amazon の購入履歴情報をエクセルファイルに書き出します．

Usage:
  order_history.py [-c CONFIG] [-o EXCEL] [-N]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o EXCEL      : 生成する Excel ファイルを指定します．[default: amazhist.xlsx]
  -N            : サムネイル画像を含めないようにします．
"""

import logging

import my_lib.openpyxl_util
import openpyxl
import openpyxl.drawing.image
import openpyxl.drawing.spreadsheet_drawing
import openpyxl.drawing.xdr
import openpyxl.styles
import openpyxl.utils

import amazhist.crawler
import amazhist.handle

_STATUS_INSERT_ITEM = "[生成] 注文商品"
_STATUS_ALL = "[生成] Excel"

_SHOP_NAME = "アマゾン"

_SHEET_DEF = {
    "SHEET_TITLE": f"【{_SHOP_NAME}】購入",
    "TABLE_HEADER": {
        "row": {
            "pos": 2,
            "height": {"default": 80, "without_thumb": 25},
        },
        "col": {
            "shop_name": {
                "label": "ショップ",
                "pos": 2,
                "width": 15,
                "format": "@",
                "value": _SHOP_NAME,
            },
            "date": {
                "label": "日付",
                "pos": 3,
                "width": 23,
                "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
            },
            "name": {
                "label": "商品名",
                "pos": 4,
                "width": 70,
                "wrap": True,
                "format": "@",
            },
            "image": {
                "label": "画像",
                "pos": 5,
                "width": 12,
            },
            "count": {
                "label": "数量",
                "pos": 6,
                "format": "0_ ",
                "width": 8,
            },
            "price": {
                "label": "価格",
                "pos": 7,
                "width": 16,
                "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
            },
            "category": {
                "label": "カテゴリ",
                "pos": 8,
                "length": 3,
                "width": 20,
                "wrap": True,
            },
            "seller": {
                "label": "売り手",
                "pos": 11,
                "width": 29,
                "format": "@",
                "wrap": True,
            },
            "id": {
                # NOTE: アマゾン向けでは「id」→「asin」に読み替え
                "formal_key": "asin",
                "label": "商品ID(ASIN)",
                "pos": 12,
                "width": 17,
                "format": "@",
                "link_func": lambda item: item["url"],
            },
            "no": {
                "label": "注文番号",
                "pos": 13,
                "width": 28,
                "format": "@",
                "link_func": lambda item: amazhist.crawler.gen_order_url(item["no"]),
            },
        },
    },
}


def _generate_sheet(handle, book, is_need_thumb=True):
    item_list = amazhist.handle.get_item_list(handle)

    amazhist.handle.set_progress_bar(handle, _STATUS_INSERT_ITEM, len(item_list))

    my_lib.openpyxl_util.generate_list_sheet(
        book,
        item_list,
        _SHEET_DEF,
        is_need_thumb,
        lambda item: amazhist.handle.get_thumb_path(handle, item),
        lambda status: amazhist.handle.set_status(handle, status),
        lambda: amazhist.handle.get_progress_bar(handle, _STATUS_ALL).update(),
        lambda: amazhist.handle.get_progress_bar(handle, _STATUS_INSERT_ITEM).update(),
    )


def generate_table_excel(handle, excel_file, is_need_thumb=True):
    amazhist.handle.set_status(handle, "📊 エクセルファイルの作成を開始します...")

    # プログレスバーのステップ:
    # 1. Workbook作成
    # 2. ヘッダー設定 (generate_list_sheet内)
    # 3. アイテム挿入完了 (generate_list_sheet内)
    # 4. テーブル設定 (generate_list_sheet内)
    # 5. ファイル保存
    # 6. ファイルクローズ
    amazhist.handle.set_progress_bar(handle, _STATUS_ALL, 6)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = amazhist.handle.get_excel_font(handle)

    amazhist.handle.get_progress_bar(handle, _STATUS_ALL).update()  # 1. Workbook作成

    _generate_sheet(handle, book, is_need_thumb)  # 2, 3, 4 は generate_list_sheet 内

    book.remove(book.worksheets[0])

    amazhist.handle.set_status(handle, "💾 エクセルファイルを書き出しています...")

    book.save(excel_file)

    amazhist.handle.get_progress_bar(handle, _STATUS_ALL).update()  # 5. ファイル保存

    book.close()

    amazhist.handle.get_progress_bar(handle, _STATUS_ALL).update()  # 6. ファイルクローズ

    amazhist.handle.set_status(handle, "🎉 完了しました！")

    logging.info("Complete to Generate excel file")


if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    assert __doc__ is not None
    args = docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    excel_file = args["-o"]
    is_need_thumb = not args["-N"]

    handle = amazhist.handle.create(config)

    generate_table_excel(handle, excel_file, is_need_thumb)

    amazhist.handle.finish(handle)
