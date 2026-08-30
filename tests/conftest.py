#!/usr/bin/env python3
# ruff: noqa: S101
"""
共通テストフィクスチャ

テスト全体で使用する共通のフィクスチャとヘルパーを定義します。
"""

import datetime
import logging
import unittest.mock

import pytest

# === ブラウザ (my_lib.browser) モックヘルパー ===
#
# プロダクションコードは Selenium の (driver, wait) タプルから
# my_lib.browser の Page 抽象へ移行済み。テストでは以下のヘルパーで
# Page / Element のモックを組み立てる。
#
# - Page / Element の要素検索（find / find_all）は Locator を受け取る。
#   XPath 文字列は locator.value に入るため、xpath ごとに返り値を出し
#   分けたい場合は build_element / build_page の find/find_all に
#   「値の部分文字列 -> 返り値」のマッピングか、値を受け取る関数を渡す。


def _locator_dispatch(spec, default):
    """Locator を受け取る side_effect を生成する。

    spec:
      - None            : 常に default を返す
      - callable(value) : locator.value を渡して結果を得る
      - dict / seq      : (部分文字列, 返り値) のマッピング（最初に一致したもの）
    """
    if spec is None:
        return lambda *a, **k: default
    if callable(spec):
        return lambda locator, *a, **k: spec(locator.value)

    pairs = list(spec.items()) if isinstance(spec, dict) else list(spec)

    def _side_effect(locator, *a, **k):
        for substr, result in pairs:
            if substr in locator.value:
                return result
        return default

    return _side_effect


def build_element(
    *,
    text="",
    attrs=None,
    screenshot=b"\x89PNG\r\n",
    find=None,
    find_all=None,
    href=None,
    evaluate=None,
):
    """my_lib.browser.Element のモックを生成する。"""
    element = unittest.mock.MagicMock(name="element")
    element.text = text

    attr_map = dict(attrs or {})
    if href is not None:
        attr_map.setdefault("href", href)
    element.attr = unittest.mock.MagicMock(side_effect=lambda name: attr_map.get(name))

    element.screenshot = unittest.mock.MagicMock(return_value=screenshot)
    element.click = unittest.mock.MagicMock()
    element.type = unittest.mock.MagicMock()
    element.clear = unittest.mock.MagicMock()
    element.press = unittest.mock.MagicMock()
    if evaluate is not None:
        element.evaluate = unittest.mock.MagicMock(return_value=evaluate)
    else:
        element.evaluate = unittest.mock.MagicMock(return_value=None)
    _set_finders(element, find, find_all)
    return element


def _set_finders(mock, find, find_all):
    """find / find_all をモックに設定する。

    spec が None のときは return_value を使い（テスト側で return_value を
    上書きできる）、spec があるときは side_effect を使う。
    """
    if find is None:
        mock.find = unittest.mock.MagicMock(return_value=None)
    else:
        mock.find = unittest.mock.MagicMock(side_effect=_locator_dispatch(find, None))
    if find_all is None:
        mock.find_all = unittest.mock.MagicMock(return_value=[])
    else:
        mock.find_all = unittest.mock.MagicMock(side_effect=_locator_dispatch(find_all, []))


def build_page(
    *,
    url="https://www.amazon.co.jp/your-orders/orders",
    title="",
    content="<html></html>",
    find=None,
    find_all=None,
    exists=False,
):
    """my_lib.browser.Page のモックを生成する。"""
    page = unittest.mock.MagicMock(name="page")
    page.url = url
    page.title = title
    page.content = content

    _set_finders(page, find, find_all)

    if callable(exists):
        page.exists = unittest.mock.MagicMock(side_effect=lambda locator, *a, **k: exists(locator.value))
    else:
        page.exists = unittest.mock.MagicMock(return_value=exists)

    page.wait_visible = unittest.mock.MagicMock(return_value=build_element())
    page.wait_clickable = unittest.mock.MagicMock(return_value=build_element())
    page.wait_absent = unittest.mock.MagicMock(return_value=None)
    page.wait_text = unittest.mock.MagicMock(return_value=None)
    page.wait_until = unittest.mock.MagicMock(return_value=None)
    page.goto = unittest.mock.MagicMock()
    page.refresh = unittest.mock.MagicMock()
    page.evaluate = unittest.mock.MagicMock(return_value=None)
    page.screenshot = unittest.mock.MagicMock(return_value=b"\x89PNG")
    return page


def attach_browser(handle, *, page=None, tab=None):
    """Handle にブラウザモックを取り付ける。

    - handle.get_page() が page モックを返すようにする。
    - handle.browser_manager.get_browser().tab(url) が
      context manager として tab モックを yield するようにする。

    テストからは handle._test_page / handle._test_tab で参照できる。
    """
    if page is None:
        page = build_page()
    if tab is None:
        tab = build_page()

    handle.get_page = unittest.mock.MagicMock(return_value=page)

    browser_manager = unittest.mock.MagicMock(name="browser_manager")
    browser_manager.has_browser.return_value = True
    tab_cm = browser_manager.get_browser.return_value.tab.return_value
    tab_cm.__enter__.return_value = tab
    tab_cm.__exit__.return_value = False
    handle._browser_manager = browser_manager

    handle._test_page = page
    handle._test_tab = tab
    handle._test_browser_manager = browser_manager
    return page, tab


@pytest.fixture
def make_element():
    """Element モック生成関数を返すフィクスチャ。"""
    return build_element


@pytest.fixture
def make_page():
    """Page モック生成関数を返すフィクスチャ。"""
    return build_page


@pytest.fixture
def browser_mocks():
    """Handle にブラウザモックを取り付ける関数を返すフィクスチャ。"""
    return attach_browser


@pytest.fixture
def by_value():
    """値ベースの関数を Locator ベースの side_effect に変換するヘルパー。

    使用例::

        def find_by_value(value):
            if "order-details" in value:
                return link_element
            return None

        page.find.side_effect = by_value(find_by_value)
    """

    def _wrap(fn):
        def _side_effect(locator, *a, **k):
            return fn(locator.value)

        return _side_effect

    return _wrap


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
