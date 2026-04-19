# 04 — Excel Output Format

This document specifies exactly what `excel_writer.write_result` produces
so the implementation, the tests, and any future downstream reader agree.

## 1. File-Level Rules

- Format: **xlsx** (Open Office XML) via `openpyxl`.
- Target file = `params.output_path`.
- If the file does **not** exist: create a new workbook, remove the default empty sheet, create today's sheet, write the block.
- If the file **exists**: open it, find today's sheet (create if missing), and **prepend** the new block at the top (row 1), pushing any existing rows down. Preserve every other sheet untouched.
- Concurrent writers are not supported (single-process CLI).

## 2. Sheet Naming

- Name = `calculation_time.strftime("%Y-%m-%d")`, e.g. `2026-04-19`.
- If a sheet of that name already exists, the new block is prepended inside it.
- One sheet per calendar day, no suffixing logic.

## 3. Block Layout (single run)

A "block" occupies a contiguous set of rows in today's sheet and has two
sub-sections: *Overview* and *Quoting Sequence*. Column A is used for
labels; column B onward for values or column headers.

### 3.1 Overview sub-section (9 rows)

| Row | Col A | Col B |
|-----|-------|-------|
| 1 | `Overview` (bold header cell) | |
| 2 | `Calculation Time` | `2026-04-19 10:30:00` |
| 3 | `Start Price` | `100.00` |
| 4 | `Target Price` | `45.00` |
| 5 | `Max Reduction Pct` | `50.00 %` |
| 6 | `Min Reduction` | `10.00` |
| 7 | `Decimals` | `2` |
| 8 | `Rounding` | `true` |
| 9 | *(blank separator row)* | |

### 3.2 Quoting Sequence sub-section (variable rows)

Row 10 — header:

| Col A | Col B | Col C | Col D | Col E |
|-------|-------|-------|-------|-------|
| `Round` | `Start Amount` | `End Amount` | `Reduction Amount` | `Reduction Pct` |

Rows 11 .. 10+n — one per `QuoteStep` (columns follow PRD §11 order):

| Col A | Col B | Col C | Col D | Col E |
|-------|-------|-------|-------|-------|
| `1` | `100.00` | `55.00` | `45.00` | `45.00 %` |
| `2` | `55.00` | `45.00` | `10.00` | `18.18 %` |

### 3.3 Total rows per block

`overview (8 rows) + 1 blank + 1 header + n sequence rows = 10 + n`.

## 4. Multi-Run Same Day — Insert-at-Top

PRD §11: newest calculation at the top, separated from the previous one
by **two blank rows**.

Procedure (`excel_writer.prepend_block`):

```
1. If sheet is empty, write block starting at row 1. Done.

2. Otherwise:
   a. Let block_rows = render_block_rows(result)      # list of row tuples
   b. Let shift = len(block_rows) + 2                 # 2 blank rows below new block
   c. ws.insert_rows(idx=1, amount=shift)             # shift existing rows down
   d. Write block_rows starting at row 1.
   e. Rows (len(block_rows)+1) and (len(block_rows)+2) remain blank.
```

`openpyxl.worksheet.Worksheet.insert_rows` handles the shift; cell values
remain intact, including any previous formatting.

## 5. Cell Formatting

| Cell | Format |
|------|--------|
| Section headers (`Overview`, column header row) | `Font(bold=True)` |
| Date / timestamp cells | Plain string (human-readable on any viewer) |
| Numeric cells | Plain string from `format(decimal_value, "f")` so Excel does not re-interpret as float |
| Boolean cells | `"true"` / `"false"` (lowercase) |
| Percentage cells | `format(value, "f") + " %"` |

## 6. Column Widths

Optional polish: after writing the block, set `ws.column_dimensions[letter].width = 20` for columns A–E if the current width is default. Not required for functional correctness.

## 7. Error Handling

- If `output_path`'s parent directory does not exist: `mkdir(parents=True, exist_ok=True)`.
- If `output_path` points to a non-xlsx or corrupt file: propagate `openpyxl.utils.exceptions.InvalidFileException`; `main.py` converts it to a user-friendly error.
- If a write fails mid-way: `openpyxl`'s `save` writes to a temp file and renames on success. The PRD does not require crash-safety beyond that.

## 8. Round-Trip Test Plan

Covered in [06-task-breakdown.md](./06-task-breakdown.md). Summary:

- Write to a fresh file → assert sheet count, sheet name, block contents.
- Write a second block same day → assert block 2 starts at row 1, block 1 shifted by `len(block2) + 2`, exactly 2 blank rows between them.
- Write on a new day → assert a new sheet is created, previous sheet untouched.
