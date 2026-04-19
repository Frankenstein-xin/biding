# cli.py — Command-line argument parsing for the Quoting Calculator.
#
# Responsibility: parse and coerce raw argv strings into a validated
# CalculationParams dataclass. All argparse usage is confined to this module.
#
# Public surface:
#   build_parser() -> argparse.ArgumentParser
#   parse_args(argv)  -> CalculationParams

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path

from biding.models import CalculationParams


# ---------------------------------------------------------------------------
# Type coercion helpers (used as argparse `type=` callbacks)
# ---------------------------------------------------------------------------

def _decimal_type(value: str) -> Decimal:
    """Parse a string into Decimal, rejecting scientific notation and NaN/Inf.

    Raises argparse.ArgumentTypeError on invalid input so argparse can emit
    a clean user-facing error without a Python traceback.
    """
    try:
        d = Decimal(value)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"invalid decimal value: {value!r}")
    if not d.is_finite():
        raise argparse.ArgumentTypeError(
            f"decimal value must be finite, got: {value!r}"
        )
    return d


_BOOL_TRUE_VALUES = {"true", "yes", "1", "y", "on"}
_BOOL_FALSE_VALUES = {"false", "no", "0", "n", "off"}


def _bool_type(value: str) -> bool:
    """Parse a string into bool, case-insensitively.

    Accepted truthy strings:  true, yes, 1, y, on
    Accepted falsy strings:   false, no, 0, n, off
    Anything else → ArgumentTypeError.
    """
    lowered = value.strip().lower()
    if lowered in _BOOL_TRUE_VALUES:
        return True
    if lowered in _BOOL_FALSE_VALUES:
        return False
    raise argparse.ArgumentTypeError(
        f"invalid boolean value: {value!r}. "
        "Use true/false, yes/no, 1/0, y/n, or on/off"
    )


def _path_type(value: str) -> Path:
    """Expand ~ and resolve to an absolute Path."""
    return Path(value).expanduser().resolve()


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argparse parser for the biding CLI."""
    parser = argparse.ArgumentParser(
        prog="biding",
        description=(
            "Find the fewest-rounds price-reduction sequence from a starting "
            "price down to a target price, obeying per-step percentage and "
            "absolute-reduction constraints. Appends the result to an xlsx workbook."
        ),
        epilog=(
            "Example:\n"
            "  python -m biding --start-price 100 --target-price 45 \\\n"
            "    --max-pct 50 --min-reduction 10 --decimals 2 \\\n"
            "    --rounding true --output ./out/quotes.xlsx"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--start-price",
        required=True,
        type=_decimal_type,
        metavar="PRICE",
        help="Starting price (must be > 0)",
    )
    parser.add_argument(
        "--target-price",
        required=True,
        type=_decimal_type,
        metavar="PRICE",
        help=(
            "Target price to reach (must be < start-price). "
            "Pass 0 to auto-compute the lowest feasible target."
        ),
    )
    parser.add_argument(
        "--max-pct",
        required=True,
        type=_decimal_type,
        metavar="PCT",
        help="Maximum percentage reduction per quote round (e.g. 5 for 5%%)",
    )
    parser.add_argument(
        "--min-reduction",
        required=True,
        type=_decimal_type,
        metavar="AMOUNT",
        help="Minimum absolute reduction per quote round (must be > 0)",
    )
    parser.add_argument(
        "--decimals",
        required=True,
        type=int,
        metavar="N",
        help="Number of decimal places to keep in price arithmetic (>= 0; typically 2)",
    )
    parser.add_argument(
        "--rounding",
        required=True,
        type=_bool_type,
        metavar="BOOL",
        help=(
            "Rounding mode: true = round-half-up (business rounding), "
            "false = truncate"
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        type=_path_type,
        metavar="FILE",
        help="Path to the xlsx result file (created if it does not exist)",
    )

    return parser


# ---------------------------------------------------------------------------
# Public parse entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> CalculationParams:
    """Parse argv and return a validated CalculationParams.

    Args:
        argv: list of CLI argument strings (e.g. sys.argv[1:]).
              Pass None to let argparse read sys.argv[1:] automatically.

    Returns:
        CalculationParams with all fields validated.

    Raises:
        SystemExit(2): argparse error — missing flags or bad type coercion.
        ValueError:    cross-field validation failure in CalculationParams.__post_init__.
    """
    parser = build_parser()
    ns = parser.parse_args(argv)

    # Construct the dataclass; __post_init__ performs cross-field validation
    return CalculationParams(
        start_price=ns.start_price,
        target_price=ns.target_price,
        max_pct=ns.max_pct,
        min_reduction=ns.min_reduction,
        decimals=ns.decimals,
        rounding=ns.rounding,
        output_path=ns.output,
    )
