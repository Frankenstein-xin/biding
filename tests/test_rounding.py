# test_rounding.py — Unit tests for biding.rounding.quantize.

from decimal import Decimal

import pytest

from biding.rounding import quantize


class TestQuantizeRoundHalfUp:
    """Tests with rounding_on=True (ROUND_HALF_UP)."""

    def test_rounds_half_up_at_midpoint(self):
        # 1.235 rounded to 2 dp with ROUND_HALF_UP → 1.24
        assert quantize(Decimal("1.235"), 2, True) == Decimal("1.24")

    def test_rounds_down_below_midpoint(self):
        assert quantize(Decimal("1.234"), 2, True) == Decimal("1.23")

    def test_rounds_up_above_midpoint(self):
        assert quantize(Decimal("1.236"), 2, True) == Decimal("1.24")

    def test_zero_decimals_integer(self):
        assert quantize(Decimal("1"), 0, True) == Decimal("1")

    def test_zero_decimals_rounds_up(self):
        assert quantize(Decimal("1.6"), 0, True) == Decimal("2")

    def test_preserves_scale(self):
        # Result must have exactly 2 digits after the decimal point
        result = quantize(Decimal("5"), 2, True)
        assert result == Decimal("5.00")
        assert result.as_tuple().exponent == -2

    def test_large_price(self):
        assert quantize(Decimal("9999.995"), 2, True) == Decimal("10000.00")


class TestQuantizeTruncate:
    """Tests with rounding_on=False (ROUND_DOWN / truncate)."""

    def test_truncates_at_midpoint(self):
        # 1.235 truncated to 2 dp → 1.23 (drops the 5)
        assert quantize(Decimal("1.235"), 2, False) == Decimal("1.23")

    def test_truncates_above_midpoint(self):
        # Even if digit is 9, truncation never rounds up
        assert quantize(Decimal("1.239"), 2, False) == Decimal("1.23")

    def test_zero_decimals_truncates(self):
        assert quantize(Decimal("1.9"), 0, False) == Decimal("1")

    def test_preserves_scale(self):
        result = quantize(Decimal("5"), 2, False)
        assert result == Decimal("5.00")
        assert result.as_tuple().exponent == -2

    def test_exact_value_unchanged(self):
        # A value with fewer dp than decimals should be padded, not changed
        assert quantize(Decimal("3.1"), 2, False) == Decimal("3.10")


class TestQuantizeEdgeCases:
    """Edge cases applicable to both modes."""

    def test_zero_value(self):
        assert quantize(Decimal("0"), 2, True) == Decimal("0.00")
        assert quantize(Decimal("0"), 2, False) == Decimal("0.00")

    def test_high_decimals(self):
        val = Decimal("1.23456789")
        assert quantize(val, 4, True) == Decimal("1.2346")
        assert quantize(val, 4, False) == Decimal("1.2345")
