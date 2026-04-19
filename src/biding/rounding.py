"""Rounding helpers for price arithmetic.

All price math in this program uses :class:`decimal.Decimal` to avoid the
binary-float drift that would otherwise make percentage comparisons
unreliable.  This module centralises the single operation that matters
to the rest of the code: quantising a ``Decimal`` to a fixed number of
decimal places either via round-half-up (when the caller wants
"rounding") or truncation (when the caller does not).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


def quantize(value: Decimal, decimals: int, rounding_on: bool) -> Decimal:
    """Quantise ``value`` to exactly ``decimals`` digits after the point.

    Args:
        value: the Decimal to quantise.
        decimals: number of fractional digits to keep; must be >= 0.
        rounding_on: when True use ROUND_HALF_UP, otherwise ROUND_DOWN.

    Returns:
        A Decimal with the requested scale.
    """
    if decimals < 0:
        raise ValueError("decimals must be >= 0")

    # Build the quantiser (e.g. Decimal("0.01") for decimals=2, Decimal("1")
    # for decimals=0).  Using a string keeps the exact desired scale.
    if decimals == 0:
        quantiser = Decimal("1")
    else:
        quantiser = Decimal("1e-{}".format(decimals))

    mode = ROUND_HALF_UP if rounding_on else ROUND_DOWN
    return value.quantize(quantiser, rounding=mode)
