#!/usr/bin/env python3
# ruff: noqa: S101
"""
order.py のテスト
"""
import amazhist.order


class TestGetCallerName:
    """_get_caller_name のテスト"""

    def test_get_caller_name(self):
        """呼び出し元の関数名を取得"""
        result = amazhist.order._get_caller_name()

        assert result == "test_get_caller_name"

    def test_get_caller_name_from_nested(self):
        """ネストした関数から呼び出した場合"""

        def inner_function():
            return amazhist.order._get_caller_name()

        result = inner_function()

        assert result == "inner_function"
