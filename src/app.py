#!/usr/bin/env python3
"""
Amazon.co.jp の購入履歴情報を収集して，Excel ファイルとして出力します．

Usage:
  amazhist.py [-c CONFIG] [-e] [-f] [-N] [-D] [-R]
  amazhist.py [-c CONFIG] -r [-i ID]
  amazhist.py [-c CONFIG] -E [-a | -i ID]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e            : データ収集は行わず，Excel ファイルの出力のみ行います．
  -f            : キャッシュを使わず，強制的にデータを収集し直します．
  -r            : エラーが発生した注文・カテゴリ・サムネイルを再取得します．
  -N            : サムネイル画像を含めないようにします．
  -D            : デバッグモードで動作します（1件のみ収集，キャッシュ無視，終了待ち無し）．
  -R            : ブラウザ起動失敗時にプロファイルを削除します．
  -E            : エラーログを表示します．
  -a            : -E と共に使用し，解決済みエラーも含めて表示します．
  -i ID         : 指定IDのエラー詳細を表示（-E時），または指定IDのみ再取得（-r時）．
"""

import logging
import pathlib
import random
import sys

import my_lib.selenium_util
import rich.console
import rich.table
import selenium.common.exceptions

import amazhist.config
import amazhist.crawler
import amazhist.handle
import amazhist.history

NAME = "amazhist"
VERSION = "0.1.0"

SCHEMA_CONFIG = "schema/config.schema"

_MAX_SESSION_RETRY_COUNT = 1


def execute_fetch(handle: amazhist.handle.Handle) -> None:
    try:
        amazhist.crawler.fetch_order_list(handle)
    except selenium.common.exceptions.InvalidSessionIdException:
        # セッションエラーはドライバーが壊れているのでダンプを試みず re-raise
        logging.warning("セッションエラーが発生しました（ブラウザがクラッシュした可能性があります）")
        raise
    except Exception:
        # シャットダウン要求時はダンプをスキップ（ドライバーが既に閉じている可能性が高い）
        if not amazhist.crawler.is_shutdown_requested():
            driver, wait = handle.get_selenium_driver()
            my_lib.selenium_util.dump_page(driver, int(random.random() * 100), handle.config.debug_dir_path)
        raise


def execute_retry(handle: amazhist.handle.Handle) -> None:
    """エラーが発生したアイテムを再取得"""
    try:
        amazhist.crawler.retry_failed_items(handle)
    except selenium.common.exceptions.InvalidSessionIdException:
        # セッションエラーはドライバーが壊れているのでダンプを試みず re-raise
        logging.warning("セッションエラーが発生しました（ブラウザがクラッシュした可能性があります）")
        raise
    except Exception:
        if not amazhist.crawler.is_shutdown_requested():
            driver, wait = handle.get_selenium_driver()
            my_lib.selenium_util.dump_page(driver, int(random.random() * 100), handle.config.debug_dir_path)
        raise


def execute_retry_single(
    config,
    error_id: int,
    clear_profile_on_browser_error: bool = False,
) -> int:
    """特定のエラーIDを再取得

    Args:
        config: 設定
        error_id: 再取得するエラーID
        clear_profile_on_browser_error: ブラウザエラー時にプロファイルを削除するか

    Returns:
        int: 終了コード（0: 成功、1: エラー）
    """
    handle = amazhist.handle.Handle(
        config=amazhist.config.Config.load(config),
        clear_profile_on_browser_error=clear_profile_on_browser_error,
    )
    exit_code = 0

    try:
        try:
            success = amazhist.crawler.retry_error_by_id(handle, error_id)
            if not success:
                exit_code = 1
        except selenium.common.exceptions.InvalidSessionIdException:
            logging.warning("セッションエラーが発生しました（ブラウザがクラッシュした可能性があります）")
            handle.set_status("❌ セッションエラー", is_error=True)
            return 1
        except my_lib.selenium_util.SeleniumError as e:
            logging.exception("Selenium の起動に失敗しました")
            handle.set_status(f"❌ {e}", is_error=True)
            return 1
        except Exception:
            if not amazhist.crawler.is_shutdown_requested():
                logging.exception("エラーの再取得に失敗しました")
                handle.set_status("❌ エラーが発生しました", is_error=True)
                exit_code = 1
        finally:
            handle.quit_selenium()
    finally:
        handle.finish()

    handle.pause_live()
    input("完了しました．エンターを押すと終了します．")

    return exit_code


def execute_retry_mode(
    config,
    clear_profile_on_browser_error: bool = False,
) -> int:
    """エラーが発生したアイテムを再取得

    Returns:
        int: 終了コード（0: 成功、1: エラー）
    """
    handle = amazhist.handle.Handle(
        config=amazhist.config.Config.load(config),
        clear_profile_on_browser_error=clear_profile_on_browser_error,
    )
    exit_code = 0

    try:
        for retry in range(_MAX_SESSION_RETRY_COUNT + 1):
            try:
                execute_retry(handle)
                break  # 成功したらループを抜ける
            except selenium.common.exceptions.InvalidSessionIdException:
                # quit_selenium() は finally で呼ばれる
                if retry < _MAX_SESSION_RETRY_COUNT and clear_profile_on_browser_error:
                    logging.warning(
                        "セッションエラーが発生しました。プロファイルを削除してリトライします（%d/%d）",
                        retry + 1,
                        _MAX_SESSION_RETRY_COUNT,
                    )
                    handle.set_status(
                        f"🔄 セッションエラー、リトライ中... ({retry + 1}/{_MAX_SESSION_RETRY_COUNT})"
                    )
                    my_lib.selenium_util.delete_profile("Amazhist", handle.config.selenium_data_dir_path)
                else:
                    # リトライ限度を超えた、または clear_profile_on_browser_error=False
                    logging.exception("セッションエラーが発生しました（リトライ不可）")
                    handle.set_status("❌ セッションエラー", is_error=True)
                    return 1
            except my_lib.selenium_util.SeleniumError as e:
                logging.exception("Selenium の起動に失敗しました")
                handle.set_status(f"❌ {e}", is_error=True)
                return 1
            except Exception:
                # シャットダウン要求時は正常終了扱い（tracebackを出さない）
                if not amazhist.crawler.is_shutdown_requested():
                    logging.exception("エラーアイテムの再取得に失敗しました")
                    handle.set_status("❌ エラーが発生しました", is_error=True)
                    exit_code = 1
                break  # 他の例外ではリトライしない
            finally:
                handle.quit_selenium()
    finally:
        handle.finish()

    handle.pause_live()
    input("完了しました．エンターを押すと終了します．")

    return exit_code


def execute(
    config,
    is_export_mode: bool = False,
    ignore_cache: bool = False,
    is_need_thumb: bool = True,
    debug_mode: bool = False,
    clear_profile_on_browser_error: bool = False,
) -> int:
    """メイン処理を実行する。

    セッションエラー（ブラウザクラッシュ等）が発生した場合、
    clear_profile_on_browser_error=True であればプロファイルを削除してリトライする。

    Returns:
        int: 終了コード（0: 成功、1: エラー）
    """
    # デバッグモードではキャッシュ無視を有効化
    if debug_mode:
        ignore_cache = True

    handle = amazhist.handle.Handle(
        config=amazhist.config.Config.load(config),
        ignore_cache=ignore_cache,
        debug_mode=debug_mode,
        clear_profile_on_browser_error=clear_profile_on_browser_error,
    )
    exit_code = 0

    try:
        if not is_export_mode:
            for retry in range(_MAX_SESSION_RETRY_COUNT + 1):
                try:
                    execute_fetch(handle)
                    break  # 成功したらループを抜ける
                except selenium.common.exceptions.InvalidSessionIdException:
                    # quit_selenium() は finally で呼ばれる
                    if retry < _MAX_SESSION_RETRY_COUNT and clear_profile_on_browser_error:
                        logging.warning(
                            "セッションエラーが発生しました。プロファイルを削除してリトライします（%d/%d）",
                            retry + 1,
                            _MAX_SESSION_RETRY_COUNT,
                        )
                        handle.set_status(
                            f"🔄 セッションエラー、リトライ中... ({retry + 1}/{_MAX_SESSION_RETRY_COUNT})"
                        )
                        my_lib.selenium_util.delete_profile("Amazhist", handle.config.selenium_data_dir_path)
                    else:
                        # リトライ限度を超えた、または clear_profile_on_browser_error=False
                        logging.exception("セッションエラーが発生しました（リトライ不可）")
                        handle.set_status("❌ セッションエラー", is_error=True)
                        return 1
                except my_lib.selenium_util.SeleniumError as e:
                    logging.exception("Selenium の起動に失敗しました")
                    handle.set_status(f"❌ {e}", is_error=True)
                    return 1
                except Exception:
                    # シャットダウン要求時は正常終了扱い（tracebackを出さない）
                    if not amazhist.crawler.is_shutdown_requested():
                        driver, _ = handle.get_selenium_driver()
                        logging.exception("Failed to fetch data: %s", driver.current_url)
                        handle.set_status("❌ データの収集中にエラーが発生しました", is_error=True)
                        exit_code = 1
                    break  # 他の例外ではリトライしない
                finally:
                    handle.quit_selenium()

        try:
            amazhist.history.generate_table_excel(handle, handle.config.excel_file_path, is_need_thumb)
        except Exception:
            handle.set_status("❌ エクセルファイルの生成中にエラーが発生しました", is_error=True)
            logging.exception("Failed to generate Excel file.")
            exit_code = 1
    finally:
        handle.finish()

    if not handle.debug_mode:
        handle.pause_live()
        input("完了しました．エンターを押すと終了します．")

    return exit_code


def show_error_log(config, show_all=False):
    """エラーログを表示

    Args:
        config: 設定
        show_all: True の場合、解決済みエラーも表示
    """
    handle = amazhist.handle.Handle(config=amazhist.config.Config.load(config))

    try:
        console = rich.console.Console()

        if show_all:
            errors = handle.get_all_errors()
            title = "エラーログ（全件）"
        else:
            errors = handle.get_unresolved_errors()
            title = "エラーログ（未解決）"

        if not errors:
            console.print(f"\n[green]{title}: エラーはありません[/green]\n")
            return

        # エラー件数のサマリーを表示
        unresolved_count = handle.get_error_count(resolved=False)
        resolved_count = handle.get_error_count(resolved=True)
        console.print(f"\n[bold]{title}[/bold]")
        console.print(
            f"  未解決: [red]{unresolved_count}[/red] 件  解決済み: [green]{resolved_count}[/green] 件\n"  # noqa: E501
        )

        # テーブルを作成
        table = rich.table.Table(show_header=True, header_style="bold")
        table.add_column("ID", style="dim", width=5)
        table.add_column("日時", width=19)
        table.add_column("種別", width=12)
        table.add_column("コンテキスト", width=10)
        table.add_column("注文番号", width=20)
        table.add_column("メッセージ/商品名", width=40, overflow="ellipsis")
        table.add_column("状態", width=6)
        table.add_column("URL (https://www.amazon.co.jp)", overflow="ellipsis")

        amazon_base_url = "https://www.amazon.co.jp"

        for error in errors:
            created_at = error.created_at.strftime("%Y-%m-%d %H:%M:%S") if error.created_at else ""
            status = "[green]解決[/green]" if error.resolved else "[red]未解決[/red]"
            order_no = error.order_no or ""
            # エラーメッセージまたは商品名を表示（商品名がなければエラーメッセージを優先）
            item_name = error.item_name or error.error_message or ""

            # URLからベースURLを削除
            url = error.url or ""
            if url.startswith(amazon_base_url):
                url = url[len(amazon_base_url) :]

            # コンテキストに応じた色分け
            context = error.context
            if context == "order":
                context_style = "[yellow]order[/yellow]"
            elif context == "thumbnail":
                context_style = "[blue]thumbnail[/blue]"
            elif context == "category":
                context_style = "[cyan]category[/cyan]"
            else:
                context_style = context

            table.add_row(
                str(error.id),
                created_at,
                error.error_type,
                context_style,
                order_no,
                item_name,
                status,
                url,
            )

        console.print(table)

        # エラーメッセージの詳細を表示
        console.print("\n[bold]エラー詳細:[/bold]")
        for error in errors[:10]:  # 最新10件のみ詳細表示
            if error.error_message:
                console.print(f"  [dim]ID {error.id}:[/dim] {error.error_message[:100]}")

        if len(errors) > 10:
            console.print(f"  [dim]... 他 {len(errors) - 10} 件[/dim]")

        console.print()

    finally:
        handle.finish()


def show_error_detail(config, error_id: int):
    """特定IDのエラー詳細を表示

    Args:
        config: 設定
        error_id: エラーID
    """
    handle = amazhist.handle.Handle(config=amazhist.config.Config.load(config))

    try:
        console = rich.console.Console()

        error = handle.get_error_by_id(error_id)

        if error is None:
            console.print(f"\n[red]エラーID {error_id} は見つかりませんでした[/red]\n")
            return

        console.print(f"\n[bold]エラー詳細 (ID: {error.id})[/bold]\n")

        # 基本情報
        table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("項目", style="bold", width=16)
        table.add_column("値")

        created_at = error.created_at.strftime("%Y-%m-%d %H:%M:%S") if error.created_at else "-"
        status = "[green]解決済み[/green]" if error.resolved else "[red]未解決[/red]"

        table.add_row("ID", str(error.id))
        table.add_row("状態", status)
        table.add_row("作成日時", created_at)
        table.add_row("エラー種別", error.error_type)
        table.add_row("コンテキスト", error.context)
        table.add_row("リトライ回数", str(error.retry_count))
        table.add_row("注文番号", error.order_no or "-")
        table.add_row("注文年", str(error.order_year) if error.order_year else "-")
        table.add_row("注文ページ", str(error.order_page) if error.order_page else "-")
        table.add_row("ページ内インデックス", str(error.order_index) if error.order_index else "-")
        table.add_row("商品名", error.item_name or "-")

        console.print(table)

        # URL（フルで表示）
        console.print("\n[bold]URL:[/bold]")
        console.print(f"  {error.url or '-'}")

        # エラーメッセージ
        console.print("\n[bold]エラーメッセージ:[/bold]")
        if error.error_message:
            console.print(f"  {error.error_message}")
        else:
            console.print("  -")

        console.print()

    finally:
        handle.finish()


######################################################################
if __name__ == "__main__":
    import my_lib.config
    import my_lib.logger
    from docopt import docopt

    assert __doc__ is not None
    args = docopt(__doc__)

    debug_mode: bool = args["-D"]

    # TTY環境ではシンプルなログフォーマットを使用（Rich の表示と干渉しないため）
    log_format = my_lib.logger.SIMPLE_FORMAT if sys.stdout.isatty() else None

    my_lib.logger.init(
        "amazhist",
        level=logging.DEBUG if debug_mode else logging.INFO,
        log_format=log_format,
    )

    config_file = args["-c"]
    is_export_mode = args["-e"]
    ignore_cache = args["-f"]
    is_retry_mode = args["-r"]
    is_need_thumb = not args["-N"]
    clear_profile_on_browser_error: bool = args["-R"]
    is_show_error_log = args["-E"]
    is_show_all_errors = args["-a"]
    error_id_str = args["-i"]

    config = my_lib.config.load(args["-c"], pathlib.Path(SCHEMA_CONFIG))

    if is_show_error_log:
        if error_id_str:
            show_error_detail(config, int(error_id_str))
        else:
            show_error_log(config, show_all=is_show_all_errors)
    elif is_retry_mode:
        if error_id_str:
            sys.exit(execute_retry_single(config, int(error_id_str), clear_profile_on_browser_error))
        else:
            sys.exit(execute_retry_mode(config, clear_profile_on_browser_error))
    else:
        sys.exit(
            execute(
                config,
                is_export_mode,
                ignore_cache,
                is_need_thumb,
                debug_mode,
                clear_profile_on_browser_error,
            )
        )
