#!/usr/bin/env python3
# ruff: noqa: S101
"""
cli.py のテスト
"""

import unittest.mock

import pytest

import amazhist.cli as app
import amazhist.config
import amazhist.crawler
import amazhist.database
import amazhist.handle


class TestExecuteFetch:
    """execute_fetch のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        # 必要なディレクトリを作成
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))  # type: ignore[method-assign]
            yield h
            h.finish()

    def test_execute_fetch_success(self, handle):
        """正常にフェッチ実行"""
        with unittest.mock.patch("amazhist.crawler.fetch_order_list") as mock_fetch:
            amazhist.cli.execute_fetch(handle)
            mock_fetch.assert_called_once_with(handle)

    def test_execute_fetch_error_dumps_page(self, handle):
        """エラー時にページダンプ"""
        with (
            unittest.mock.patch(
                "amazhist.crawler.fetch_order_list",
                side_effect=Exception("フェッチエラー"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="フェッチエラー"),
        ):
            amazhist.cli.execute_fetch(handle)
            mock_dump.assert_called_once()


class TestExecute:
    """execute のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_export_mode_only(self, mock_config, tmp_path):
        """エクスポートモードのみ"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("amazhist.cli.execute_fetch") as mock_fetch,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            app.execute(mock_config, is_export_mode=True)

            mock_fetch.assert_not_called()
            mock_excel.assert_called_once()

    def test_execute_full_mode(self, mock_config, tmp_path):
        """フルモード（フェッチ＋エクスポート）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("amazhist.cli.execute_fetch") as mock_fetch,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            app.execute(mock_config, is_export_mode=False)

            mock_fetch.assert_called_once()
            mock_excel.assert_called_once()


class TestShowErrorLog:
    """show_error_log のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_show_error_log_no_errors(self, mock_config, tmp_path, capsys):
        """エラーがない場合"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_unresolved_errors", return_value=[]),
        ):
            app.show_error_log(mock_config, show_all=False)

    def test_show_error_log_with_errors(self, mock_config, tmp_path):
        """エラーがある場合"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_errors = [
            amazhist.database.ErrorLog(
                id=1,
                url="https://example.com/order/1",
                error_type="timeout",
                context="order",
                retry_count=0,
                resolved=False,
                error_message="タイムアウトしました",
                order_no="ORDER-001",
                item_name="テスト商品",
                created_at=datetime.datetime(2025, 1, 15, 10, 30, 0),
            ),
            amazhist.database.ErrorLog(
                id=2,
                url="https://example.com/thumb/2",
                error_type="fetch",
                context="thumbnail",
                retry_count=0,
                resolved=True,
                error_message=None,
                order_no=None,
                item_name="商品2",
                created_at=datetime.datetime(2025, 1, 15, 11, 0, 0),
            ),
        ]

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(
                amazhist.handle.Handle, "get_unresolved_errors", return_value=mock_errors
            ),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_count", return_value=1),
        ):
            app.show_error_log(mock_config, show_all=False)

    def test_show_error_log_all_errors(self, mock_config, tmp_path):
        """全エラー表示"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_errors = [
            amazhist.database.ErrorLog(
                id=1,
                url="https://example.com/category/1",
                error_type="timeout",
                context="category",
                retry_count=0,
                resolved=True,
                error_message="カテゴリ取得失敗",
                order_no="ORDER-001",
                item_name="テスト商品",
                created_at=datetime.datetime(2025, 1, 15, 10, 30, 0),
            ),
        ]

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_all_errors", return_value=mock_errors),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_count", return_value=0),
        ):
            app.show_error_log(mock_config, show_all=True)


class TestExecuteFetchExceptions:
    """execute_fetch の例外処理テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))  # type: ignore[method-assign]
            yield h
            h.finish()

    def test_execute_fetch_invalid_session_exception(self, handle):
        """InvalidSessionIdException 時に警告ログを出して再送出"""
        import selenium.common.exceptions

        with (
            unittest.mock.patch(
                "amazhist.crawler.fetch_order_list",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            pytest.raises(selenium.common.exceptions.InvalidSessionIdException),
        ):
            amazhist.cli.execute_fetch(handle)

    def test_execute_fetch_selenium_error(self, handle):
        """SeleniumError 時はダンプせず再送出"""
        import my_lib.selenium_util

        with (
            unittest.mock.patch(
                "amazhist.crawler.fetch_order_list",
                side_effect=my_lib.selenium_util.SeleniumError("driver failed"),
            ),
            pytest.raises(my_lib.selenium_util.SeleniumError),
        ):
            amazhist.cli.execute_fetch(handle)

    def test_execute_fetch_generic_exception_with_shutdown(self, handle):
        """シャットダウン要求時はダンプをスキップ"""
        with (
            unittest.mock.patch(
                "amazhist.crawler.fetch_order_list",
                side_effect=Exception("generic error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="generic error"),
        ):
            amazhist.cli.execute_fetch(handle)
            mock_dump.assert_not_called()

    def test_execute_fetch_generic_exception_no_selenium(self, handle):
        """has_selenium_driver が False の場合はダンプをスキップ"""
        handle.has_selenium_driver = unittest.mock.MagicMock(return_value=False)  # type: ignore[method-assign]

        with (
            unittest.mock.patch(
                "amazhist.crawler.fetch_order_list",
                side_effect=Exception("generic error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="generic error"),
        ):
            amazhist.cli.execute_fetch(handle)
            mock_dump.assert_not_called()


class TestExecuteRetryExceptions:
    """execute_retry の例外処理テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))  # type: ignore[method-assign]
            yield h
            h.finish()

    def test_execute_retry_success(self, handle):
        """正常にリトライ実行"""
        with unittest.mock.patch("amazhist.crawler.retry_failed_items") as mock_retry:
            amazhist.cli.execute_retry(handle)
            mock_retry.assert_called_once_with(handle)

    def test_execute_retry_invalid_session_exception(self, handle):
        """InvalidSessionIdException 時に警告ログを出して再送出"""
        import selenium.common.exceptions

        with (
            unittest.mock.patch(
                "amazhist.crawler.retry_failed_items",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            pytest.raises(selenium.common.exceptions.InvalidSessionIdException),
        ):
            amazhist.cli.execute_retry(handle)

    def test_execute_retry_selenium_error(self, handle):
        """SeleniumError 時はダンプせず再送出"""
        import my_lib.selenium_util

        with (
            unittest.mock.patch(
                "amazhist.crawler.retry_failed_items",
                side_effect=my_lib.selenium_util.SeleniumError("driver failed"),
            ),
            pytest.raises(my_lib.selenium_util.SeleniumError),
        ):
            amazhist.cli.execute_retry(handle)

    def test_execute_retry_generic_exception_with_dump(self, handle):
        """汎用例外時にページダンプを実行"""
        with (
            unittest.mock.patch(
                "amazhist.crawler.retry_failed_items",
                side_effect=Exception("retry error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="retry error"),
        ):
            amazhist.cli.execute_retry(handle)
            mock_dump.assert_called_once()

    def test_execute_retry_generic_exception_with_shutdown(self, handle):
        """シャットダウン要求時はダンプをスキップ"""
        with (
            unittest.mock.patch(
                "amazhist.crawler.retry_failed_items",
                side_effect=Exception("retry error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="retry error"),
        ):
            amazhist.cli.execute_retry(handle)
            mock_dump.assert_not_called()

    def test_execute_retry_generic_exception_no_selenium(self, handle):
        """has_selenium_driver が False の場合はダンプをスキップ"""
        handle.has_selenium_driver = unittest.mock.MagicMock(return_value=False)  # type: ignore[method-assign]

        with (
            unittest.mock.patch(
                "amazhist.crawler.retry_failed_items",
                side_effect=Exception("retry error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="retry error"),
        ):
            amazhist.cli.execute_retry(handle)
            mock_dump.assert_not_called()


class TestExecuteRetrySingle:
    """execute_retry_single のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_retry_single_success(self, mock_config, tmp_path):
        """正常にリトライ成功"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.crawler.retry_error_by_id", return_value=True),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(mock_config, error_id=1)
            assert result == 0

    def test_execute_retry_single_failure(self, mock_config, tmp_path):
        """リトライ失敗時は exit_code=1"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.crawler.retry_error_by_id", return_value=False),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(mock_config, error_id=1)
            assert result == 1

    def test_execute_retry_single_session_error_with_retry(self, mock_config, tmp_path):
        """セッションエラー発生時のリトライ"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        call_count = [0]

        def side_effect_fn(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("session lost")
            return True

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.crawler.retry_error_by_id", side_effect=side_effect_fn),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(
                mock_config, error_id=1, clear_profile_on_browser_error=True
            )
            assert result == 0
            mock_delete.assert_called_once()

    def test_execute_retry_single_session_error_no_retry(self, mock_config, tmp_path):
        """セッションエラーでリトライ不可の場合"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.crawler.retry_error_by_id",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(
                mock_config, error_id=1, clear_profile_on_browser_error=False
            )
            assert result == 1

    def test_execute_retry_single_selenium_error(self, mock_config, tmp_path):
        """SeleniumError 時は exit_code=1"""
        import my_lib.selenium_util

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.crawler.retry_error_by_id",
                side_effect=my_lib.selenium_util.SeleniumError("driver failed"),
            ),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(mock_config, error_id=1)
            assert result == 1

    def test_execute_retry_single_generic_error(self, mock_config, tmp_path):
        """汎用例外時は exit_code=1"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.crawler.retry_error_by_id",
                side_effect=Exception("generic error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(mock_config, error_id=1)
            assert result == 1

    def test_execute_retry_single_shutdown_requested(self, mock_config, tmp_path):
        """シャットダウン要求時は exit_code=0"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.crawler.retry_error_by_id",
                side_effect=Exception("interrupted"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(mock_config, error_id=1)
            assert result == 0


class TestExecuteRetryMode:
    """execute_retry_mode のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_retry_mode_success(self, mock_config, tmp_path):
        """正常にリトライモード実行"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.cli.execute_retry") as mock_retry,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config)
            assert result == 0
            mock_retry.assert_called_once()

    def test_execute_retry_mode_session_error_with_retry(self, mock_config, tmp_path):
        """セッションエラー発生時のリトライ"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        call_count = [0]

        def side_effect_fn(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("session lost")
            return None

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.cli.execute_retry", side_effect=side_effect_fn),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config, clear_profile_on_browser_error=True)
            assert result == 0
            mock_delete.assert_called_once()

    def test_execute_retry_mode_session_error_no_retry(self, mock_config, tmp_path):
        """セッションエラーでリトライ不可の場合"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_retry",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config, clear_profile_on_browser_error=False)
            assert result == 1

    def test_execute_retry_mode_selenium_error(self, mock_config, tmp_path):
        """SeleniumError 時は exit_code=1"""
        import my_lib.selenium_util

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_retry",
                side_effect=my_lib.selenium_util.SeleniumError("driver failed"),
            ),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config)
            assert result == 1

    def test_execute_retry_mode_generic_error(self, mock_config, tmp_path):
        """汎用例外時は exit_code=1"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_retry",
                side_effect=Exception("generic error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config)
            assert result == 1

    def test_execute_retry_mode_shutdown_requested(self, mock_config, tmp_path):
        """シャットダウン要求時は exit_code=0"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_retry",
                side_effect=Exception("interrupted"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config)
            assert result == 0


class TestExecuteAdvanced:
    """execute の高度なテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_debug_mode_enables_ignore_cache(self, mock_config, tmp_path):
        """デバッグモードで ignore_cache が有効化される"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("amazhist.cli.execute_fetch"),
        ):
            # debug_mode=True の場合は input を呼ばない
            result = app.execute(mock_config, is_export_mode=True, debug_mode=True)
            assert result == 0

    def test_execute_session_error_with_retry(self, mock_config, tmp_path):
        """セッションエラー発生時のリトライ"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        call_count = [0]

        def side_effect_fn(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("session lost")
            return None

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch("amazhist.cli.execute_fetch", side_effect=side_effect_fn),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config, clear_profile_on_browser_error=True)
            assert result == 0
            mock_delete.assert_called_once()

    def test_execute_session_error_no_retry(self, mock_config, tmp_path):
        """セッションエラーでリトライ不可の場合"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_fetch",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config, clear_profile_on_browser_error=False)
            assert result == 1

    def test_execute_selenium_error(self, mock_config, tmp_path):
        """SeleniumError 時は exit_code=1"""
        import my_lib.selenium_util

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_fetch",
                side_effect=my_lib.selenium_util.SeleniumError("driver failed"),
            ),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config)
            assert result == 1

    def test_execute_generic_error(self, mock_config, tmp_path):
        """汎用例外時は exit_code=1"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_driver = unittest.mock.MagicMock()
        mock_driver.current_url = "https://example.com"

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_fetch",
                side_effect=Exception("generic error"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch.object(
                amazhist.handle.Handle,
                "get_selenium_driver",
                return_value=(mock_driver, unittest.mock.MagicMock()),
            ),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config)
            assert result == 1

    def test_execute_shutdown_requested(self, mock_config, tmp_path):
        """シャットダウン要求時は exit_code=0"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_fetch",
                side_effect=Exception("interrupted"),
            ),
            unittest.mock.patch("amazhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config)
            assert result == 0

    def test_execute_excel_generation_error(self, mock_config, tmp_path):
        """Excel生成エラー時は exit_code=1"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.history.generate_table_excel",
                side_effect=Exception("Excel error"),
            ),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config, is_export_mode=True)
            assert result == 1


class TestShowErrorLogAdvanced:
    """show_error_log の高度なテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_show_error_log_url_truncation(self, mock_config, tmp_path):
        """Amazon URL がトランケートされる"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_errors = [
            amazhist.database.ErrorLog(
                id=1,
                url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=123",
                error_type="timeout",
                context="order",
                retry_count=0,
                resolved=False,
                error_message="Timeout",
                order_no="ORDER-001",
                item_name="テスト商品",
                created_at=datetime.datetime(2025, 1, 15, 10, 30, 0),
            ),
        ]

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(
                amazhist.handle.Handle, "get_unresolved_errors", return_value=mock_errors
            ),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_count", return_value=1),
        ):
            app.show_error_log(mock_config, show_all=False)

    def test_show_error_log_unknown_context(self, mock_config, tmp_path):
        """不明なコンテキストはそのまま表示"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_errors = [
            amazhist.database.ErrorLog(
                id=1,
                url="https://example.com/unknown",
                error_type="unknown",
                context="unknown_context",
                retry_count=0,
                resolved=False,
                error_message="Unknown error",
                order_no=None,
                item_name=None,
                created_at=datetime.datetime(2025, 1, 15, 10, 30, 0),
            ),
        ]

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(
                amazhist.handle.Handle, "get_unresolved_errors", return_value=mock_errors
            ),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_count", return_value=1),
        ):
            app.show_error_log(mock_config, show_all=False)

    def test_show_error_log_more_than_10_errors(self, mock_config, tmp_path):
        """10件以上のエラーがある場合に省略メッセージを表示"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_errors = [
            amazhist.database.ErrorLog(
                id=i,
                url=f"https://example.com/error/{i}",
                error_type="timeout",
                context="order",
                retry_count=0,
                resolved=False,
                error_message=f"Error message {i}",
                order_no=f"ORDER-{i:03d}",
                item_name=f"商品{i}",
                created_at=datetime.datetime(2025, 1, 15, 10, 30, i),
            )
            for i in range(1, 16)  # 15件のエラーを作成
        ]

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(
                amazhist.handle.Handle, "get_unresolved_errors", return_value=mock_errors
            ),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_count", return_value=15),
        ):
            app.show_error_log(mock_config, show_all=False)


class TestShowErrorDetail:
    """show_error_detail のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_show_error_detail_not_found(self, mock_config, tmp_path):
        """エラーが見つからない場合"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_by_id", return_value=None),
        ):
            app.show_error_detail(mock_config, error_id=999)

    def test_show_error_detail_found(self, mock_config, tmp_path):
        """エラーが見つかった場合"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_error = amazhist.database.ErrorLog(
            id=1,
            url="https://www.amazon.co.jp/gp/your-account/order-details?orderID=123",
            error_type="timeout",
            context="order",
            retry_count=3,
            resolved=False,
            error_message="タイムアウトしました",
            order_no="ORDER-001",
            item_name="テスト商品",
            order_year=2024,
            order_page=1,
            order_index=5,
            created_at=datetime.datetime(2025, 1, 15, 10, 30, 0),
        )

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_by_id", return_value=mock_error),
        ):
            app.show_error_detail(mock_config, error_id=1)

    def test_show_error_detail_resolved(self, mock_config, tmp_path):
        """解決済みエラーの詳細表示"""
        import datetime

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_error = amazhist.database.ErrorLog(
            id=2,
            url="https://example.com/thumb/image.png",
            error_type="fetch",
            context="thumbnail",
            retry_count=1,
            resolved=True,
            error_message=None,  # エラーメッセージなし
            order_no=None,
            item_name="商品名",
            order_year=None,
            order_page=None,
            order_index=None,
            created_at=datetime.datetime(2025, 1, 15, 11, 0, 0),
        )

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_by_id", return_value=mock_error),
        ):
            app.show_error_detail(mock_config, error_id=2)

    def test_show_error_detail_no_url(self, mock_config, tmp_path):
        """URLがないエラーの詳細表示"""

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        mock_error = amazhist.database.ErrorLog(
            id=3,
            url="",  # 空のURL
            error_type="parse_error",
            context="order",
            retry_count=0,
            resolved=False,
            error_message="Parse error",
            order_no=None,
            item_name=None,
            order_year=None,
            order_page=None,
            order_index=None,
            created_at=None,  # created_at も None
        )

        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch.object(amazhist.handle.Handle, "get_error_by_id", return_value=mock_error),
        ):
            app.show_error_detail(mock_config, error_id=3)


class TestRetrySingleExhausted:
    """リトライ回数を使い果たす場合のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_retry_single_exhausts_retries(self, mock_config, tmp_path):
        """リトライ回数を使い果たした場合 exit_code=1"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        # 常に InvalidSessionIdException を発生させる
        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.crawler.retry_error_by_id",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_single(
                mock_config, error_id=1, clear_profile_on_browser_error=True
            )
            assert result == 1


class TestRetryModeExhausted:
    """リトライモードでリトライ回数を使い果たす場合のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_retry_mode_exhausts_retries(self, mock_config, tmp_path):
        """リトライ回数を使い果たした場合 exit_code=1"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        # 常に InvalidSessionIdException を発生させる
        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_retry",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = amazhist.cli.execute_retry_mode(mock_config, clear_profile_on_browser_error=True)
            assert result == 1


class TestExecuteExhausted:
    """execute でリトライ回数を使い果たす場合のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        return {
            "base_dir": str(tmp_path),
            "data": {
                "amazon": {
                    "cache": {
                        "order": "cache/order.db",
                        "thumb": "thumb",
                    },
                },
                "selenium": "selenium",
                "debug": "debug",
            },
            "output": {
                "excel": {
                    "table": "output/amazhist.xlsx",
                    "font": {"name": "Arial", "size": 10},
                },
                "captcha": "captcha.png",
            },
            "login": {
                "amazon": {
                    "user": "test@example.com",
                    "pass": "password",
                },
            },
        }

    def test_execute_exhausts_retries(self, mock_config, tmp_path):
        """リトライ回数を使い果たした場合 exit_code=1"""
        import selenium.common.exceptions

        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        # 常に InvalidSessionIdException を発生させる
        with (
            unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"),
            unittest.mock.patch(
                "amazhist.cli.execute_fetch",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("session lost"),
            ),
            unittest.mock.patch("amazhist.history.generate_table_excel"),
            unittest.mock.patch("my_lib.chrome_util.delete_profile"),
            unittest.mock.patch("builtins.input", return_value=""),
        ):
            result = app.execute(mock_config, clear_profile_on_browser_error=True)
            assert result == 1
