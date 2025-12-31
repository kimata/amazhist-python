#!/usr/bin/env python3
# ruff: noqa: S101
"""
共通テストフィクスチャ

テスト全体で使用する共通のフィクスチャとヘルパーを定義します。
"""
import datetime
import logging
import pathlib
import unittest.mock

import pytest

# === 定数 ===
# プロジェクトルートの tests/evidence/ に画像を保存
EVIDENCE_DIR = pathlib.Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# === 環境モック ===
@pytest.fixture(scope="session", autouse=True)
def env_mock():
    """テスト環境用の環境変数モック"""
    with unittest.mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    """Slack API のモック"""
    with (
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
            return_value={"ok": True, "ts": "1234567890.123456"},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_upload_v2",
            return_value={"ok": True, "files": [{"id": "test_file_id"}]},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_getUploadURLExternal",
            return_value={"ok": True, "upload_url": "https://example.com"},
        ) as fixture,
    ):
        yield fixture


@pytest.fixture(autouse=True)
def _clear():
    """各テスト前にステートをクリア"""
    import my_lib.notify.slack

    my_lib.notify.slack._interval_clear()
    my_lib.notify.slack._hist_clear()


# === アイテムフィクスチャ ===
@pytest.fixture
def sample_item():
    """サンプル商品フィクスチャ"""
    return {
        "no": "503-1234567-8901234",
        "date": datetime.datetime(2025, 1, 15, 10, 30),
        "name": "テスト商品",
        "url": "https://www.amazon.co.jp/dp/B0123456789",
        "asin": "B0123456789",
        "count": 1,
        "price": 1500,
        "seller": "アマゾンジャパン合同会社",
        "condition": "新品",
        "category": ["本", "コンピュータ・IT", "プログラミング"],
    }


@pytest.fixture
def sample_order_info():
    """サンプル注文情報フィクスチャ"""
    return {
        "no": "503-1234567-8901234",
        "date": datetime.datetime(2025, 1, 15),
        "url": "https://www.amazon.co.jp/gp/your-account/order-details?orderID=503-1234567-8901234",
    }


# === Slack 通知検証 ===
@pytest.fixture
def slack_checker():
    """Slack 通知検証ヘルパーを返す"""
    import my_lib.notify.slack

    class SlackChecker:
        def assert_notified(self, message, index=-1):
            notify_hist = my_lib.notify.slack._hist_get(is_thread_local=False)
            assert len(notify_hist) != 0, "通知がされていません。"
            assert notify_hist[index].find(message) != -1, f"「{message}」が通知されていません。"

        def assert_not_notified(self):
            notify_hist = my_lib.notify.slack._hist_get(is_thread_local=False)
            assert notify_hist == [], "通知がされています。"

    return SlackChecker()


# === ロギング設定 ===
logging.getLogger("selenium.webdriver.remote").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.common").setLevel(logging.DEBUG)
