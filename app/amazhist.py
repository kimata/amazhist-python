#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amazon.co.jp の購入履歴情報を収集して，Excel ファイルとして出力します．

Usage:
  amazhist.py [-c CONFIG] [-e]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e           : データ収集は行わず，Excel ファイルの出力のみ行います．
"""

import logging
import pathlib
import sys
import random

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import crawl_handle
import store_amazon
import order_history
import selenium_util


def execute(config, is_export_mode=False):
    handle = crawl_handle.create(config)

    if not is_export_mode:
        try:
            store_amazon.fetch_order_item_list(handle)
        except:
            driver, wait = crawl_handle.get_selenium_driver(handle)
            selenium_util.dump_page(driver, int(random.random() * 100))
            raise

    order_history.generate_table_excel(handle, config["output"]["excel"]["table"])

    crawl_handle.finish(handle)


######################################################################
if __name__ == "__main__":
    from docopt import docopt
    import traceback

    import logger
    from config import load_config

    args = docopt(__doc__)

    logger.init("amazhist", level=logging.INFO)

    config_file = args["-c"]
    is_export_mode = args["-e"]

    config = load_config(args["-c"])

    try:
        execute(config, is_export_mode)
    except:
        logging.error(traceback.format_exc())
