"""Program orchestrator.

Wires :mod:`biding.cli`, :mod:`biding.calculator`, and
:mod:`biding.excel_writer` together and translates exceptions into the
exit codes documented in plan/05-cli-interface §4:

    0  success
    1  unexpected error (bug; prints traceback)
    2  argparse error (raised by argparse via SystemExit)
    3  validation error (ValueError from CalculationParams)
    4  InfeasibleError from the calculator
    5  xlsx read/write failure
"""

from __future__ import annotations

import sys
import traceback
from typing import Sequence

from openpyxl.utils.exceptions import InvalidFileException

from biding.calculator import calculate
from biding.cli import parse_args
from biding.excel_writer import write_result
from biding.models import CalculationParams, InfeasibleError


EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_VALIDATION = 3
EXIT_INFEASIBLE = 4
EXIT_IO = 5


def main(argv: Sequence[str] | None = None) -> int:
    """Run the program end-to-end and return an integer exit code."""
    # ---- 1. Parse + validate CLI -----------------------------------------
    try:
        params: CalculationParams = parse_args(argv)
    except SystemExit:
        # argparse raises SystemExit(2) on bad args; re-raise so the
        # caller's shell sees the same code argparse chose.
        raise
    except InfeasibleError as exc:
        # Defensive: InfeasibleError cannot fire from parse_args today,
        # but being explicit protects against future refactors.
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INFEASIBLE
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    # ---- 2. Calculate the quoting sequence -------------------------------
    try:
        result = calculate(params)
    except InfeasibleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INFEASIBLE
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except Exception:  # noqa: BLE001 — defensive top-level bug catch
        traceback.print_exc()
        return EXIT_UNEXPECTED

    # ---- 3. Persist to xlsx ---------------------------------------------
    try:
        write_result(result, params.output_path)
    except (OSError, InvalidFileException) as exc:
        print(f"error: failed to write xlsx: {exc}", file=sys.stderr)
        return EXIT_IO
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return EXIT_UNEXPECTED

    # ---- 4. Success summary ---------------------------------------------
    first_price = (
        result.steps[0].start_amount if result.steps else result.effective_target
    )
    last_price = (
        result.steps[-1].end_amount if result.steps else result.effective_target
    )
    sheet_name = result.calculation_time.strftime("%Y-%m-%d")
    print(
        f"Found sequence in {len(result.steps)} rounds.\n"
        f"Start: {first_price}  ->  End: {last_price}\n"
        f"Output: {params.output_path} (sheet: {sheet_name})"
    )
    return EXIT_OK


def cli_entry() -> None:
    """Console-script entry point registered in ``pyproject.toml``."""
    sys.exit(main(sys.argv[1:]))


__all__ = ["main", "cli_entry"]
