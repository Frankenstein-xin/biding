# rounding.py — Rounding/truncation helpers for the Quoting Calculator.
#
# Responsibility: provide a single quantize() function that applies the
# user-selected rounding mode (ROUND_HALF_UP or ROUND_DOWN/truncate) to a
# Decimal value at a given number of decimal places.
#
# This module has no side effects at import time and no I/O.

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal


def quantize(value: Decimal, decimals: int, rounding_on: bool) -> Decimal:
    """Round or truncate *value* to *decimals* decimal places.

    Args:
        value:       The Decimal to be rounded/truncated.
        decimals:    Number of decimal places to keep (>= 0).
        rounding_on: True  → ROUND_HALF_UP (standard business rounding).
                     False → ROUND_DOWN   (truncate, drop excess digits).

    Returns:
        A new Decimal with exactly *decimals* digits after the decimal point.

    Examples:
        >>> quantize(Decimal("1.235"), 2, True)
        Decimal('1.24')
        >>> quantize(Decimal("1.235"), 2, False)
        Decimal('1.23')
        >>> quantize(Decimal("7"), 0, True)
        Decimal('7')
    """
    # Build the quantization target string, e.g. decimals=2 → "0.01", decimals=0 → "1"
    if decimals == 0:
        quant_str = "1"
    else:
        quant_str = "0." + "0" * decimals

    rounding_mode = ROUND_HALF_UP if rounding_on else ROUND_DOWN
    return value.quantize(Decimal(quant_str), rounding=rounding_mode)
