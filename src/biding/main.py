# main.py — Orchestration layer for the Quoting Calculator.
#
# Responsibility: wire cli.parse_args → calculator.calculate →
# excel_writer.write_result, handle all exceptions with appropriate exit codes,
# and emit human-readable console output (stdout on success, stderr on error).
#
# Exit codes (design doc 05-cli-interface.md §4):
#   0 — success
#   2 — argparse error (SystemExit raised by argparse itself)
#   3 — validation error (ValueError from CalculationParams.__post_init__)
#   4 — infeasible (InfeasibleError from calculator)
#   5 — I/O error (OSError or openpyxl InvalidFileException)
#   1 — unexpected error (bug; full traceback printed to stderr)

from __future__ import annotations

import sys
import traceback
from typing import Sequence

from biding.calculator import calculate
from biding.cli import parse_args
from biding.excel_writer import write_result
from biding.models import InfeasibleError

# Import openpyxl's exception for targeted I/O error handling
try:
    from openpyxl.utils.exceptions import InvalidFileException
except ImportError:
    # Defensive fallback: if openpyxl is absent, use a placeholder that won't match
    InvalidFileException = OSError  # type: ignore[misc, assignment]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Quoting Calculator end-to-end and return an integer exit code.

    Args:
        argv: CLI argument list (e.g. sys.argv[1:]). None → argparse reads sys.argv[1:].

    Returns:
        Integer exit code (0 = success, 2–5 = handled errors, 1 = unexpected bug).
    """
    # --- Step 1: Parse and validate CLI arguments ---
    # argparse raises SystemExit(2) on its own for missing/malformed flags; let it propagate.
    # ValueError comes from CalculationParams.__post_init__ cross-field validation.
    try:
        params = parse_args(list(argv) if argv is not None else None)
    except SystemExit:
        raise  # argparse already printed its error; do not suppress
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    # --- Step 2: Run the quoting algorithm ---
    try:
        result = calculate(params)
    except InfeasibleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except Exception:
        # Unexpected calculator error — treat as a bug and show full traceback
        traceback.print_exc()
        return 1

    # --- Step 3: Write the result to the xlsx workbook ---
    try:
        write_result(result, params.output_path)
    except (OSError, InvalidFileException) as exc:
        print(f"error: failed to write xlsx: {exc}", file=sys.stderr)
        return 5
    except Exception:
        traceback.print_exc()
        return 1

    # --- Step 4: Print success summary to stdout ---
    sheet_name = result.calculation_time.strftime("%Y-%m-%d")
    n = len(result.steps)
    print(f"Found sequence in {n} round{'s' if n != 1 else ''}.")
    if result.steps:
        print(
            f"Start: {result.steps[0].start_amount}  ->  "
            f"End: {result.steps[-1].end_amount}"
        )
    else:
        print(f"Start price already equals target: {result.effective_target}")
    print(f"Output: {params.output_path} (sheet: {sheet_name})")

    return 0
