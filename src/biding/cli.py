"""Command-line interface for the quoting calculator.

This module is the only place that imports ``argparse``.  It builds the
parser, coerces string inputs to the right types, and returns a typed,
validated :class:`biding.models.CalculationParams`.  Validation of field
values (e.g. ``start-price > 0``) is delegated to the dataclass's
``__post_init__``; this file only handles type coercion and argparse
error surfacing.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

from biding.models import CalculationParams


_BOOL_TRUE = {"true", "yes", "1", "y", "on"}
_BOOL_FALSE = {"false", "no", "0", "n", "off"}


def _decimal_type(value: str) -> Decimal:
    """Parse a CLI string into a Decimal without going through float.

    Rejects scientific notation and NaN/Inf because money values are
    always decimal.  Raises argparse's dedicated error type so the
    message is surfaced cleanly by the parser.
    """
    lowered = value.strip().lower()
    if "e" in lowered or "nan" in lowered or "inf" in lowered:
        raise argparse.ArgumentTypeError(
            f"invalid decimal value: {value!r}"
        )
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(
            f"invalid decimal value: {value!r}"
        ) from exc


def _bool_type(value: str) -> bool:
    """Parse a CLI string into a bool, accepting the usual English tokens."""
    lowered = value.strip().lower()
    if lowered in _BOOL_TRUE:
        return True
    if lowered in _BOOL_FALSE:
        return False
    raise argparse.ArgumentTypeError(
        f"invalid boolean value: {value!r} (expected true/false)"
    )


def _path_type(value: str) -> Path:
    """Expand ``~`` and resolve to an absolute path."""
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argparse parser.

    Kept public so tests can introspect the argument set without firing
    a full parse.
    """
    parser = argparse.ArgumentParser(
        prog="biding",
        description=(
            "Find the fewest-rounds price reduction sequence from a "
            "start price to a target price under a max-percent and "
            "min-absolute reduction constraint, and append the result "
            "to an xlsx workbook."
        ),
        epilog=(
            "Example:\n"
            "  python -m biding \\\n"
            "    --start-price 100 --target-price 45 --max-pct 50 \\\n"
            "    --min-reduction 10 --decimals 2 --rounding true \\\n"
            "    --output ./out/quotes.xlsx"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # All arguments are required per PRD §3.
    parser.add_argument(
        "--start-price",
        type=_decimal_type,
        required=True,
        help="Starting price (Decimal, > 0).",
    )
    parser.add_argument(
        "--target-price",
        type=_decimal_type,
        required=True,
        help=(
            "Target price (Decimal, >= 0). Use 0 to auto-compute from "
            "--max-pct and --min-reduction."
        ),
    )
    parser.add_argument(
        "--max-pct",
        type=_decimal_type,
        required=True,
        help="Max percentage reduction per quote, e.g. 5 for 5 %% (0 < v < 100).",
    )
    parser.add_argument(
        "--min-reduction",
        type=_decimal_type,
        required=True,
        help="Minimum absolute reduction per quote (Decimal, > 0).",
    )
    parser.add_argument(
        "--decimals",
        type=int,
        required=True,
        help="Number of decimal places to keep in price math (>= 0).",
    )
    parser.add_argument(
        "--rounding",
        type=_bool_type,
        required=True,
        help="true = round-half-up, false = truncate.",
    )
    parser.add_argument(
        "--output",
        type=_path_type,
        required=True,
        help="Destination xlsx file path (parent dirs created if missing).",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> CalculationParams:
    """Parse ``argv`` into a validated :class:`CalculationParams`.

    Standard argparse errors (missing arg, bad format) raise
    ``SystemExit(2)`` — that behavior is inherited from argparse.  Field
    validation errors (e.g. ``start-price <= 0``) raise ``ValueError``
    from the dataclass, which ``main`` converts to exit code 3.
    """
    parser = build_parser()
    ns = parser.parse_args(argv)
    return CalculationParams(
        start_price=ns.start_price,
        target_price=ns.target_price,
        max_pct=ns.max_pct,
        min_reduction=ns.min_reduction,
        decimals=ns.decimals,
        rounding=ns.rounding,
        output_path=ns.output,
    )


__all__ = ["build_parser", "parse_args"]
