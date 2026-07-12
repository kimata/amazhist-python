#!/usr/bin/env python3
# ruff: noqa: S101
"""
parser.py のテスト
"""

import pytest

import amazhist.parser


class TestParseDate:
    """parse_date のテスト"""

    def test_parse_date_normal(self):
        """通常の日付パース"""
        result = amazhist.parser.parse_date("2025年01月15日")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_single_digit(self):
        """一桁の月日"""
        result = amazhist.parser.parse_date("2025年01月05日")

        assert result.month == 1
        assert result.day == 5

    def test_parse_date_invalid(self):
        """不正な日付"""
        with pytest.raises(ValueError):
            amazhist.parser.parse_date("無効な日付")


class TestParseDateDigital:
    """parse_date_digital のテスト"""

    def test_parse_date_digital_normal(self):
        """通常のデジタル日付パース"""
        result = amazhist.parser.parse_date_digital("2025/01/15")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_digital_single_digit(self):
        """一桁の月日"""
        result = amazhist.parser.parse_date_digital("2025/01/05")

        assert result.month == 1
        assert result.day == 5

    def test_parse_date_digital_invalid(self):
        """不正な日付"""
        with pytest.raises(ValueError):
            amazhist.parser.parse_date_digital("2025-01-15")  # 形式が違う


class TestParseNumber:
    """parse_number のテスト"""

    def test_parse_number_with_comma(self):
        """カンマ区切り"""
        assert amazhist.parser.parse_number("1,234件") == 1234

    def test_parse_number_without_comma(self):
        """カンマなし（4桁以上でも桁落ちしない）"""
        assert amazhist.parser.parse_number("1500件") == 1500

    def test_parse_number_with_text(self):
        """テキスト中の数値"""
        assert amazhist.parser.parse_number("42件の注文") == 42

    def test_parse_number_large_with_comma(self):
        """大きな数値（カンマ複数）"""
        assert amazhist.parser.parse_number("1,234,567") == 1234567

    def test_parse_number_no_digits(self):
        """数値なし"""
        assert amazhist.parser.parse_number("なし") is None


class TestParsePrice:
    """parse_price のテスト"""

    def test_parse_price_yen_symbol(self):
        """円記号付き"""
        result = amazhist.parser.parse_price("￥1,500")

        assert result == 1500

    def test_parse_price_yen_suffix(self):
        """円サフィックス"""
        result = amazhist.parser.parse_price("1,500円")

        assert result == 1500

    def test_parse_price_no_comma(self):
        """カンマなし"""
        result = amazhist.parser.parse_price("￥500")

        assert result == 500

    def test_parse_price_no_comma_four_digits(self):
        """カンマなし4桁以上（桁落ちしないこと）"""
        assert amazhist.parser.parse_price("￥1500") == 1500
        assert amazhist.parser.parse_price("1500円") == 1500
        assert amazhist.parser.parse_price("￥12345") == 12345

    def test_parse_price_large_number(self):
        """大きな金額"""
        result = amazhist.parser.parse_price("￥1,234,567")

        assert result == 1234567

    def test_parse_price_with_text(self):
        """テキスト付き"""
        result = amazhist.parser.parse_price("価格: ￥1,500 (税込)")

        assert result == 1500

    def test_parse_price_invalid(self):
        """パース不可"""
        result = amazhist.parser.parse_price("無料")

        assert result is None

    def test_parse_price_zero(self):
        """ゼロ"""
        result = amazhist.parser.parse_price("￥0")

        assert result == 0
