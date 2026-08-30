#!/usr/bin/env python3
"""ブラウザ抽象層（my_lib.browser）向けの共通ヘルパー。

`Page` / `FrameScope` / `Element` はいずれも `find` / `find_all` を持つため、
Selenium の `find_element`（存在必須）相当のヘルパーをここに集約する。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeAlias, TypeVar

from my_lib.browser import Element, FrameScope, Page, Xpath

import amazhist.exceptions

_T = TypeVar("_T")

# find 系ヘルパーのスコープ（Page / FrameScope / Element はいずれも find/find_all を持つ）
_Findable: TypeAlias = Page | FrameScope | Element


def find(scope: _Findable, xpath: str) -> Element:
    """要素を 1 つ取得する（存在しなければ例外）。Selenium の find_element 相当。"""
    element = scope.find(Xpath(xpath))
    if element is None:
        raise amazhist.exceptions.PageParseError("要素が見つかりません", xpath)
    return element


def text(scope: _Findable, xpath: str) -> str:
    """要素のテキストを取得する。"""
    return find(scope, xpath).text


def with_retry(
    func: Callable[[], _T],
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], bool | None] | None = None,
) -> _T:
    """リトライ付きで関数を実行する。

    全て失敗した場合は最後の例外を再スローする。

    Args:
        func: 実行する関数。
        max_retries: 最大試行回数。
        delay: リトライ間の待機秒数。
        exceptions: リトライ対象の例外タプル。
        on_retry: リトライ時のコールバック (attempt, exception)。
            False を返すとリトライを中止して例外を再スローする。

    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                if on_retry is not None:
                    should_continue = on_retry(attempt + 1, e)
                    if should_continue is False:
                        raise
                time.sleep(delay)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Unexpected state in with_retry")  # pragma: no cover
