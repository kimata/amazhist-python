#!/usr/bin/env python3
# ruff: noqa: S101
"""
handle.py のテスト
"""
import datetime
import unittest.mock

import pytest

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

        with unittest.mock.patch("amazhist.handle._init_database"):
            handle = amazhist.handle.create(mock_config)

            assert handle is not None
            assert handle["config"] == mock_config
            assert handle["force_mode"] is False

            amazhist.handle.finish(handle)

    def test_create_handle_force_mode(self, mock_config, tmp_path):
        """Handle の作成（強制モード）"""
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

        with unittest.mock.patch("amazhist.handle._init_database"):
            handle = amazhist.handle.create(mock_config, force_mode=True)

            assert handle["force_mode"] is True

            amazhist.handle.finish(handle)


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

        with unittest.mock.patch("amazhist.handle._init_database"):
            h = amazhist.handle.create(mock_config)
            yield h
            amazhist.handle.finish(h)

    def test_get_cache_file_path(self, handle, tmp_path):
        """キャッシュファイルパス取得"""
        path = amazhist.handle.get_cache_file_path(handle)
        assert path == tmp_path / "cache" / "order.db"

    def test_get_excel_file_path(self, handle, tmp_path):
        """Excel ファイルパス取得"""
        path = amazhist.handle.get_excel_file_path(handle)
        assert path == tmp_path / "output" / "amazhist.xlsx"

    def test_get_thumb_dir_path(self, handle, tmp_path):
        """サムネイルディレクトリパス取得"""
        path = amazhist.handle.get_thumb_dir_path(handle)
        assert path == tmp_path / "thumb"

    def test_get_debug_dir_path(self, handle, tmp_path):
        """デバッグディレクトリパス取得"""
        path = amazhist.handle.get_debug_dir_path(handle)
        assert path == tmp_path / "debug"

    def test_get_thumb_path(self, handle, tmp_path):
        """サムネイルパス取得"""
        item = {"asin": "B0123456789"}
        path = amazhist.handle.get_thumb_path(handle, item)
        assert path == tmp_path / "thumb" / "B0123456789.png"

    def test_get_thumb_path_no_asin(self, handle):
        """ASIN がない場合は None"""
        item = {}
        path = amazhist.handle.get_thumb_path(handle, item)
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

        with unittest.mock.patch("amazhist.handle._init_database"):
            h = amazhist.handle.create(mock_config)
            yield h
            amazhist.handle.finish(h)

    def test_get_login_user(self, handle):
        """ログインユーザー取得"""
        user = amazhist.handle.get_login_user(handle)
        assert user == "test@example.com"

    def test_get_login_pass(self, handle):
        """ログインパスワード取得"""
        password = amazhist.handle.get_login_pass(handle)
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

        with unittest.mock.patch("amazhist.handle._init_database"):
            h = amazhist.handle.create(mock_config)
            yield h
            amazhist.handle.finish(h)

    def test_set_progress_bar(self, handle):
        """プログレスバーの設定"""
        amazhist.handle.set_progress_bar(handle, "テスト", 100)

        progress_bar = amazhist.handle.get_progress_bar(handle, "テスト")
        assert progress_bar is not None
        assert progress_bar.total == 100

    def test_progress_bar_update(self, handle):
        """プログレスバーの更新"""
        amazhist.handle.set_progress_bar(handle, "テスト", 100)
        progress_bar = amazhist.handle.get_progress_bar(handle, "テスト")

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

        with unittest.mock.patch("amazhist.handle._init_database"):
            h = amazhist.handle.create(mock_config)
            yield h
            amazhist.handle.finish(h)

    def test_set_status(self, handle):
        """ステータスの設定"""
        amazhist.handle.set_status(handle, "処理中...")

        assert handle["rich"]["status_text"] == "処理中..."
        assert handle["rich"]["status_is_error"] is False

    def test_set_status_error(self, handle):
        """エラーステータスの設定"""
        amazhist.handle.set_status(handle, "エラー発生", is_error=True)

        assert handle["rich"]["status_text"] == "エラー発生"
        assert handle["rich"]["status_is_error"] is True
