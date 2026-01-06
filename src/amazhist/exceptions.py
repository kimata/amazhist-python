#!/usr/bin/env python3
"""カスタム例外クラス定義"""

from __future__ import annotations


class AmazhistError(Exception):
    """Amazhist 基底例外"""


class LoginError(AmazhistError):
    """ログイン失敗を示す例外"""


class CaptchaError(AmazhistError):
    """CAPTCHA解決失敗を示す例外"""
