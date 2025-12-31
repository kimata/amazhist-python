#!/usr/bin/env python3
"""
Amazon.co.jp の購入履歴情報を収集して，Excel ファイルとして出力します．

Usage:
  amazhist.py [-c CONFIG] [-e] [-f] [-N]
  amazhist.py [-c CONFIG] -r [-N]
  amazhist.py [-c CONFIG] -E [-a]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e            : データ収集は行わず，Excel ファイルの出力のみ行います．
  -f            : キャッシュを使わず，強制的にデータを収集し直します．
  -r            : エラーが発生した注文・カテゴリ・サムネイルを再取得します．
  -N            : サムネイル画像を含めないようにします．
  -E            : エラーログを表示します．
  -a            : -E と共に使用し，解決済みエラーも含めて表示します．
"""

import logging
import pathlib
import random
import sys
import traceback

import my_lib.selenium_util
import rich.console
import rich.table

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


def execute_retry(handle):
    """エラーが発生したアイテムを再取得"""
    try:
        amazhist.crawler.retry_failed_items(handle)
    except Exception:
        if not amazhist.crawler.is_shutdown_requested():
            driver, wait = amazhist.handle.get_selenium_driver(handle)
            my_lib.selenium_util.dump_page(
                driver, int(random.random() * 100), amazhist.handle.get_debug_dir_path(handle)
            )
            raise


def execute_retry_mode(config, is_need_thumb=True):
    """エラーが発生したアイテムを再取得して Excel を出力"""
    handle = amazhist.handle.create(config)

    try:
        execute_retry(handle)

        amazhist.history.generate_table_excel(
            handle, amazhist.handle.get_excel_file_path(handle), is_need_thumb
        )

        amazhist.handle.finish(handle)
    except Exception:
        if amazhist.crawler.is_shutdown_requested():
            amazhist.handle.finish(handle)
        else:
            amazhist.handle.set_status(handle, "❌ エラーが発生しました", is_error=True)
            logging.error(traceback.format_exc())

    amazhist.handle.pause_live(handle)
    input("完了しました．エンターを押すと終了します．")


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


def show_error_log(config, show_all=False):
    """エラーログを表示

    Args:
        config: 設定
        show_all: True の場合、解決済みエラーも表示
    """
    handle = amazhist.handle.create(config)

    try:
        console = rich.console.Console()

        if show_all:
            errors = amazhist.handle.get_all_errors(handle)
            title = "エラーログ（全件）"
        else:
            errors = amazhist.handle.get_unresolved_errors(handle)
            title = "エラーログ（未解決）"

        if not errors:
            console.print(f"\n[green]{title}: エラーはありません[/green]\n")
            return

        # エラー件数のサマリーを表示
        unresolved_count = amazhist.handle.get_error_count(handle, resolved=False)
        resolved_count = amazhist.handle.get_error_count(handle, resolved=True)
        console.print(f"\n[bold]{title}[/bold]")
        console.print(f"  未解決: [red]{unresolved_count}[/red] 件  解決済み: [green]{resolved_count}[/green] 件\n")

        # テーブルを作成
        table = rich.table.Table(show_header=True, header_style="bold")
        table.add_column("ID", style="dim", width=5)
        table.add_column("日時", width=19)
        table.add_column("種別", width=12)
        table.add_column("コンテキスト", width=10)
        table.add_column("注文番号", width=20)
        table.add_column("商品名", width=30, overflow="ellipsis")
        table.add_column("状態", width=6)
        table.add_column("URL", overflow="ellipsis")

        for error in errors:
            created_at = error["created_at"].strftime("%Y-%m-%d %H:%M:%S") if error["created_at"] else ""
            status = "[green]解決[/green]" if error["resolved"] else "[red]未解決[/red]"
            order_no = error["order_no"] or ""
            item_name = error["item_name"] or ""

            # コンテキストに応じた色分け
            context = error["context"]
            if context == "order":
                context_style = "[yellow]order[/yellow]"
            elif context == "thumbnail":
                context_style = "[blue]thumbnail[/blue]"
            elif context == "category":
                context_style = "[cyan]category[/cyan]"
            else:
                context_style = context

            table.add_row(
                str(error["id"]),
                created_at,
                error["error_type"],
                context_style,
                order_no,
                item_name,
                status,
                error["url"],
            )

        console.print(table)

        # エラーメッセージの詳細を表示
        console.print("\n[bold]エラー詳細:[/bold]")
        for error in errors[:10]:  # 最新10件のみ詳細表示
            if error["error_message"]:
                console.print(f"  [dim]ID {error['id']}:[/dim] {error['error_message'][:100]}")

        if len(errors) > 10:
            console.print(f"  [dim]... 他 {len(errors) - 10} 件[/dim]")

        console.print()

    finally:
        amazhist.handle.finish(handle)


######################################################################
if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    assert __doc__ is not None
    args = docopt(__doc__)

    # TTY環境ではシンプルなログフォーマットを使用（Rich の表示と干渉しないため）
    log_format = my_lib.logger.SIMPLE_FORMAT if sys.stdout.isatty() else None

    my_lib.logger.init("amazhist", level=logging.INFO, log_format=log_format)

    config_file = args["-c"]
    is_export_mode = args["-e"]
    is_force_mode = args["-f"]
    is_retry_mode = args["-r"]
    is_need_thumb = not args["-N"]
    is_show_error_log = args["-E"]
    is_show_all_errors = args["-a"]

    config = my_lib.config.load(args["-c"], pathlib.Path(SCHEMA_CONFIG))

    if is_show_error_log:
        show_error_log(config, show_all=is_show_all_errors)
    elif is_retry_mode:
        execute_retry_mode(config, is_need_thumb)
    else:
        execute(config, is_export_mode, is_force_mode, is_need_thumb)
