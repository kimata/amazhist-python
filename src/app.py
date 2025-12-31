#!/usr/bin/env python3
"""
Amazon.co.jp の購入履歴情報を収集して，Excel ファイルとして出力します．

Usage:
  amazhist.py [-c CONFIG] [-e] [-f] [-N]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e            : データ収集は行わず，Excel ファイルの出力のみ行います．
  -f            : キャッシュを使わず，強制的にデータを収集し直します．
  -N            : サムネイル画像を含めないようにします．
"""

import logging
import pathlib
import random
import sys
import traceback

import my_lib.selenium_util

import amazhist.crawler
import amazhist.handle
import amazhist.history

NAME = "amazhist"
VERSION = "0.1.0"

SCHEMA_CONFIG = "schema/config.schema"


def execute_fetch(handle):
    try:
        amazhist.crawler.fetch_order_item_list(handle)
    except Exception:
        # シャットダウン要求時はダンプをスキップ（ドライバーが既に閉じている可能性が高い）
        if not amazhist.crawler.is_shutdown_requested():
            driver, wait = amazhist.handle.get_selenium_driver(handle)
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
            )
            raise


def execute(config, is_export_mode=False, is_force_mode=False, is_need_thumb=True):
    handle = amazhist.handle.create(config, force_mode=is_force_mode)

    try:
        if not is_export_mode:
            execute_fetch(handle)

        amazhist.history.generate_table_excel(
            handle, amazhist.handle.get_excel_file_path(handle), is_need_thumb
        )

        amazhist.handle.finish(handle)
    except Exception:
        # シャットダウン要求時は正常終了扱い（tracebackを出さない）
        if amazhist.crawler.is_shutdown_requested():
            amazhist.handle.finish(handle)
        else:
            amazhist.handle.set_status(handle, "❌ エラーが発生しました", is_error=True)
            logging.error(traceback.format_exc())

    amazhist.handle.pause_live(handle)
    input("完了しました．エンターを押すと終了します．")


######################################################################
if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    args = docopt(__doc__)

    # TTY環境ではシンプルなログフォーマットを使用（Rich の表示と干渉しないため）
    log_format = my_lib.logger.SIMPLE_FORMAT if sys.stdout.isatty() else None

    my_lib.logger.init("amazhist", level=logging.INFO, log_format=log_format)

    config_file = args["-c"]
    is_export_mode = args["-e"]
    is_force_mode = args["-f"]
    is_need_thumb = not args["-N"]

    config = my_lib.config.load(args["-c"], pathlib.Path(SCHEMA_CONFIG))

    execute(config, is_export_mode, is_force_mode, is_need_thumb)
