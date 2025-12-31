#!/usr/bin/env python3
# ruff: noqa: S101
"""
handle.py のテスト
"""
import unittest.mock

import pytest

import amazhist.config
import amazhist.handle


class TestHandleCreation:
    """Handle 作成のテスト"""

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

    def test_create_handle(self, mock_config, tmp_path):
        """Handle の作成"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))

            assert handle is not None
            assert handle.config is not None
            assert handle.force_mode is False

            handle.finish()

    def test_create_handle_force_mode(self, mock_config, tmp_path):
        """Handle の作成（強制モード）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            handle = amazhist.handle.Handle(
                config=amazhist.config.Config.load(mock_config), force_mode=True
            )

            assert handle.force_mode is True

            handle.finish()


class TestHandlePaths:
    """Handle のパス取得テスト"""

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
            yield h
            h.finish()

    def test_get_cache_file_path(self, handle, tmp_path):
        """キャッシュファイルパス取得"""
        path = handle.config.cache_file_path
        assert path == tmp_path / "cache" / "order.db"

    def test_get_excel_file_path(self, handle, tmp_path):
        """Excel ファイルパス取得"""
        path = handle.config.excel_file_path
        assert path == tmp_path / "output" / "amazhist.xlsx"

    def test_get_thumb_dir_path(self, handle, tmp_path):
        """サムネイルディレクトリパス取得"""
        path = handle.config.thumb_dir_path
        assert path == tmp_path / "thumb"

    def test_get_debug_dir_path(self, handle, tmp_path):
        """デバッグディレクトリパス取得"""
        path = handle.config.debug_dir_path
        assert path == tmp_path / "debug"

    def test_get_thumb_path(self, handle, tmp_path):
        """サムネイルパス取得"""
        item = {"asin": "B0123456789"}
        path = handle.get_thumb_path(item)
        assert path == tmp_path / "thumb" / "B0123456789.png"

    def test_get_thumb_path_no_asin(self, handle):
        """ASIN がない場合は None"""
        item = {}
        path = handle.get_thumb_path(item)
        assert path is None


class TestHandleLogin:
    """Handle のログイン情報テスト"""

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
                    "pass": "password123",
                },
            },
        }

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch.object(amazhist.handle.Handle, "_init_database"):
            h = amazhist.handle.Handle(config=amazhist.config.Config.load(mock_config))
            yield h
            h.finish()

    def test_get_login_user(self, handle):
        """ログインユーザー取得"""
        user = handle.get_login_user()
        assert user == "test@example.com"

    def test_get_login_pass(self, handle):
        """ログインパスワード取得"""
        password = handle.get_login_pass()
        assert password == "password123"


class TestHandleProgressBar:
    """Handle のプログレスバーテスト"""

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
            yield h
            h.finish()

    def test_set_progress_bar(self, handle):
        """プログレスバーの設定"""
        handle.set_progress_bar("テスト", 100)

        progress_bar = handle.get_progress_bar("テスト")
        assert progress_bar is not None
        assert progress_bar.total == 100

    def test_progress_bar_update(self, handle):
        """プログレスバーの更新"""
        handle.set_progress_bar("テスト", 100)
        progress_bar = handle.get_progress_bar("テスト")

        progress_bar.update()

        assert progress_bar.count == 1


class TestHandleStatus:
    """Handle のステータステスト"""

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
            yield h
            h.finish()

    def test_set_status(self, handle):
        """ステータスの設定"""
        handle.set_status("処理中...")

        assert handle._status_text == "処理中..."
        assert handle._status_is_error is False

    def test_set_status_error(self, handle):
        """エラーステータスの設定"""
        handle.set_status("エラー発生", is_error=True)

        assert handle._status_text == "エラー発生"
        assert handle._status_is_error is True
