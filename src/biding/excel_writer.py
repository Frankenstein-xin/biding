"""xlsx writer for ``CalculationResult`` objects.

Implements plan/04-excel-format:

* one sheet per calendar day, named ``YYYY-MM-DD``
* each calculation renders an Overview block and a Quoting Sequence table
* multiple runs on the same day are prepended at row 1, with two blank
  rows separating them (newest at top)
* creates the workbook and any missing parent directories automatically
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from biding.models import CalculationResult


_BOLD = Font(bold=True)
_BLANK_SEPARATOR_ROWS = 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_result(result: CalculationResult, output_path: Path) -> None:
    """Append ``result`` to the xlsx at ``output_path``.

    Creates the file (and parent directories) if needed, otherwise opens
    the existing workbook and prepends the new block in today's sheet.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sheet_name = result.calculation_time.strftime("%Y-%m-%d")

    if output_path.exists():
        wb = load_workbook(output_path)
    else:
        wb = Workbook()
        # Remove the default "Sheet" that openpyxl creates so callers
        # always see deterministic sheet ordering.
        default = wb.active
        wb.remove(default)

    # Find or create today's sheet.
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(title=sheet_name)

    block = _render_block(result)
    _prepend_block(ws, block)
    _set_default_widths(ws)

    wb.save(output_path)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _format_decimal(value: Decimal) -> str:
    """Render a Decimal using fixed-point notation, preserving scale.

    Emitting strings keeps Excel from re-interpreting the number as a
    binary float; the already-quantised scale is preserved verbatim.
    """
    return format(value, "f")


def _format_pct(value: Decimal) -> str:
    """Render a percentage as ``"N.NN %"``."""
    return f"{_format_decimal(value)} %"


def _render_block(result: CalculationResult) -> list[list[tuple[object, bool]]]:
    """Produce the rows for one run as a list of (value, bold) cell tuples.

    Rows may have fewer cells than their peers; openpyxl leaves the rest
    blank.  Bold is tracked per cell so only headers are bolded.
    """
    p = result.params
    timestamp = result.calculation_time.strftime("%Y-%m-%d %H:%M:%S")

    rows: list[list[tuple[object, bool]]] = [
        [("Overview", True)],
        [("Calculation Time", False), (timestamp, False)],
        [("Start Price", False), (_format_decimal(p.start_price), False)],
        [("Target Price", False), (_format_decimal(result.effective_target), False)],
        [("Max Reduction Pct", False), (_format_pct(p.max_pct), False)],
        [("Min Reduction", False), (_format_decimal(p.min_reduction), False)],
        [("Decimals", False), (p.decimals, False)],
        [("Rounding", False), ("true" if p.rounding else "false", False)],
        [],  # blank separator between overview and sequence
    ]

    rows.append(
        [
            ("Round", True),
            ("Start Amount", True),
            ("End Amount", True),
            ("Reduction Amount", True),
            ("Reduction Pct", True),
        ]
    )

    for step in result.steps:
        rows.append(
            [
                (step.round_no, False),
                (_format_decimal(step.start_amount), False),
                (_format_decimal(step.end_amount), False),
                (_format_decimal(step.reduction_amount), False),
                (_format_pct(step.reduction_pct), False),
            ]
        )

    return rows


def _prepend_block(
    ws: Worksheet, block: Sequence[Sequence[tuple[object, bool]]]
) -> None:
    """Insert ``block`` at row 1, shifting any prior content down.

    When the sheet is empty we simply write starting at row 1.  When it
    already has data we make room for ``len(block) + 2`` rows (the
    block itself plus two blank separator rows per PRD §11) via
    ``insert_rows`` and then write the block at the top.
    """
    sheet_has_content = ws.max_row > 1 or any(
        cell.value is not None for cell in ws[1]
    )

    if sheet_has_content:
        ws.insert_rows(idx=1, amount=len(block) + _BLANK_SEPARATOR_ROWS)

    for r_offset, row in enumerate(block, start=1):
        for c_offset, (value, bold) in enumerate(row, start=1):
            cell = ws.cell(row=r_offset, column=c_offset, value=value)
            if bold:
                cell.font = _BOLD


def _set_default_widths(ws: Worksheet) -> None:
    """Widen A–E to a readable default if they are still at factory width."""
    for letter in ("A", "B", "C", "D", "E"):
        dim = ws.column_dimensions[letter]
        if dim.width is None:
            dim.width = 20


__all__ = ["write_result"]
