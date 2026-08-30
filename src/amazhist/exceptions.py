#!/usr/bin/env python3
"""カスタム例外クラス定義"""

from __future__ import annotations


class AmazhistError(Exception):
    """Amazhist 基底例外"""


class LoginError(AmazhistError):
    """ログイン失敗を示す例外"""


class CaptchaError(AmazhistError):
    """CAPTCHA解決失敗を示す例外"""


class PageParseError(AmazhistError):
    """ページ解析に必要な要素が見つからないことを示す例外

    Selenium の find_element が要素未検出時に送出していた
    NoSuchElementException 相当を、バックエンド非依存の例外として表現する。
    """

    def __init__(self, message: str, xpath: str = "") -> None:
        super().__init__(message)
        self.xpath = xpath

    def __str__(self) -> str:
        if self.xpath:
            return f"{self.args[0]}: {self.xpath}"
        return str(self.args[0])


class ThumbnailError(AmazhistError):
    """サムネイル画像エラーの基底クラス"""

    def __init__(self, message: str, path: str = "") -> None:
        super().__init__(message)
        self.path = path

    def __str__(self) -> str:
        if self.path:
            return f"{self.args[0]}: {self.path}"
        return str(self.args[0])


class ThumbnailEmptyError(ThumbnailError):
    """サムネイル画像データが空"""


class ThumbnailSizeError(ThumbnailError):
    """サムネイル画像のサイズが0"""


class ThumbnailCorruptError(ThumbnailError):
    """サムネイル画像が破損"""
