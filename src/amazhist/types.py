#!/usr/bin/env python3
"""型定義モジュール

コールバック関数やその他の型定義を提供します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import amazhist.handle


class VisitUrlFunc(Protocol):
    """URL訪問関数の型"""

    def __call__(self, handle: amazhist.handle.Handle, url: str, caller_name: str) -> None: ...


class KeepLoggedOnFunc(Protocol):
    """ログイン維持関数の型"""

    def __call__(self, handle: amazhist.handle.Handle) -> None: ...


class GetCallerNameFunc(Protocol):
    """呼び出し元名取得関数の型"""

    def __call__(self, depth: int = 1) -> str: ...


class GenHistUrlFunc(Protocol):
    """履歴URL生成関数の型"""

    def __call__(self, year: int, page: int) -> str: ...


class GenOrderUrlFunc(Protocol):
    """注文URL生成関数の型"""

    def __call__(self, no: str) -> str: ...


class IsShutdownRequestedFunc(Protocol):
    """シャットダウン要求確認関数の型"""

    def __call__(self) -> bool: ...
