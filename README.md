# Biding — Quoting Calculator

A Python CLI tool that finds the **fewest-rounds** price-reduction sequence
from a starting price down to a target price, obeying two per-step constraints:

- Each reduction must be **at least** a configured minimum absolute amount.
- Each reduction must be **at most** a configured percentage of the current price.

Results are appended to an **xlsx workbook**, one sheet per calendar day, with
the newest run always prepended at the top of the sheet.

---

## Why This Exists

In competitive quoting scenarios, a seller must reduce their price over multiple
rounds. Two constraints apply simultaneously:

1. You cannot cut by less than a fixed floor (e.g. ¥10) — signals seriousness.
2. You cannot cut by more than a percentage cap (e.g. 5 %) — protects margin.

A naive "always take the maximum cut" strategy can land you in a **dead zone**
where the remaining gap to the target is smaller than the minimum allowed
reduction — making the target unreachable without violating a constraint.
This tool finds the provably shortest path that avoids dead zones.

---

## Project Structure

```
biding/
├── src/
│   └── biding/
│       ├── __init__.py        # Package marker
│       ├── __main__.py        # python -m biding entry point
│       ├── cli.py             # argparse wiring → CalculationParams
│       ├── models.py          # Immutable data classes (no logic)
│       ├── rounding.py        # quantize(): ROUND_HALF_UP or ROUND_DOWN
│       ├── calculator.py      # Fewest-rounds search algorithm
│       ├── excel_writer.py    # xlsx read + prepend-at-top writer
│       └── main.py            # Orchestrates cli → calculator → excel_writer
├── tests/
│   ├── test_rounding.py
│   ├── test_models.py
│   ├── test_calculator.py
│   ├── test_excel_writer.py
│   └── test_main.py
├── plan/                      # Architecture & algorithm design docs
├── requirements/
│   └── prd.md                 # Product requirements document
├── pyproject.toml
└── README.md
```

### Module Dependency Graph

```
              main.py
            /    |    \
         cli  calc   excel_writer
          |    |  \       |
       models  |  rounding
               |
             models
```

**Separation of concerns:**

- `calculator.py` — pure function, no I/O, no argparse, fully unit-testable.
- `excel_writer.py` — only module that imports `openpyxl`; no console output.
- `cli.py` — only module that imports `argparse`.
- `main.py` — only place that touches `stdout`/`stderr`; contains no business logic.
- All monetary values use `decimal.Decimal` throughout — never `float`.

---

## Algorithm

Given start price **S**, target **T**, max-percentage **P %**, and min-reduction **M**:

### Feasibility Zones

At any current price **x**, the next price **y** falls into one of three zones:

| Zone | Condition on x | Meaning |
|------|---------------|---------|
| **Direct** | `T + M ≤ x ≤ T / (1 − P/100)` | One step can land exactly on T |
| **Continue** | `x > T / (1 − P/100)` and `x·P/100 ≥ M` | Keep reducing; not close enough to go direct yet |
| **Dead** | `T < x < T + M` | Cannot reduce by M without going below T — infeasible |

The classic pitfall (PRD §7): a greedy max-reduction step can land in the
dead zone. This tool's lookahead detects that before committing to a step.

### Search Strategy

At each step from current price **x**, four candidates are considered in order:

1. **Target directly** — finish in one move if constraints allow.
2. **Max-percentage reduction** — `quantize(x × (1 − P/100))` — fastest progress.
3. **Safe minimum** — `quantize(T + M)` — leaves exactly one direct step remaining.
4. **Min-reduction fallback** — `quantize(x − M)` — smallest valid step.

The first candidate that is both a **valid step** (satisfies both constraints)
and **feasible** (can still reach T from there) is taken.

If no greedy candidate works (rare, near rounding boundaries), a **memoised
depth-first search** finds the optimal next move.

### Auto-Target

When `--target-price 0` is passed, the floor is computed automatically:

```
T_auto = quantize( 100 × min_reduction / max_pct , decimals, rounding )
```

At any price below this, the maximum allowed reduction (`price × P/100`)
would fall below the minimum required reduction (`M`), making further
progress impossible.

---

## Installation

Requires Python ≥ 3.10 and [uv](https://github.com/astral-sh/uv).

```bash
cd biding

# Create virtual environment and install runtime + dev dependencies
uv sync --dev
```

---

## Usage

### Basic invocation

```bash
uv run python -m biding \
  --start-price 100 \
  --target-price 45 \
  --max-pct 50 \
  --min-reduction 10 \
  --decimals 2 \
  --rounding true \
  --output ./out/quotes.xlsx
```

**Console output:**

```
Found sequence in 2 rounds.
Start: 100.00  ->  End: 45.00
Output: /abs/path/out/quotes.xlsx (sheet: 2026-04-19)
```

### Auto-compute target

Pass `--target-price 0` to derive the lowest feasible target automatically:

```bash
uv run python -m biding \
  --start-price 1000 \
  --target-price 0 \
  --max-pct 10 \
  --min-reduction 5 \
  --decimals 2 \
  --rounding true \
  --output ./out/quotes.xlsx
```

### Flag reference

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--start-price` | Decimal | yes | Starting price (must be > 0) |
| `--target-price` | Decimal | yes | Target price (< start-price), or `0` to auto-compute |
| `--max-pct` | Decimal | yes | Max % reduction per round — e.g. `5` means 5 % |
| `--min-reduction` | Decimal | yes | Min absolute reduction per round (must be > 0) |
| `--decimals` | int | yes | Decimal places for price arithmetic (e.g. `2`) |
| `--rounding` | bool | yes | `true` = round-half-up, `false` = truncate |
| `--output` | path | yes | Destination xlsx file (created if it does not exist) |

Boolean flags accept: `true/false`, `yes/no`, `1/0`, `y/n`, `on/off` (case-insensitive).

---

## Excel Output Format

Each run writes one block to today's sheet (`YYYY-MM-DD`).
Multiple runs on the same day are stacked newest-first, separated by two blank rows.

```
┌─────────────────────┬──────────────────────┐
│ Overview            │                      │  ← bold
│ Calculation Time    │ 2026-04-19 10:30:00  │
│ Start Price         │ 100.00               │
│ Target Price        │ 45.00                │
│ Max Reduction Pct   │ 50.00 %              │
│ Min Reduction       │ 10.00                │
│ Decimals            │ 2                    │
│ Rounding            │ true                 │
│                     │                      │  ← blank separator
├───────┬─────────────┬──────────┬───────────┬────────────┐
│ Round │ Start Amt   │ End Amt  │ Reduction │ Pct        │  ← bold
│ 1     │ 100.00      │ 55.00    │ 45.00     │ 45.00 %    │
│ 2     │ 55.00       │ 45.00    │ 10.00     │ 18.18 %    │
└───────┴─────────────┴──────────┴───────────┴────────────┘
```

New runs are inserted at the top; previous runs shift down automatically.

---

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_calculator.py -v
```

---

## Exit Codes

| Code | Meaning | Trigger |
|------|---------|---------|
| `0` | Success | Sequence found and written to xlsx |
| `2` | Argument error | Missing or malformed CLI flag (argparse) |
| `3` | Validation error | Invalid parameter values (e.g. negative price) |
| `4` | Infeasible | No valid sequence exists for the given inputs |
| `5` | I/O error | xlsx file could not be read or written |
| `1` | Unexpected error | Internal bug — full traceback printed to stderr |

---

## Design Notes

| Decision | Rationale |
|----------|-----------|
| `decimal.Decimal` for all prices | Avoids binary-float drift across many chained multiplications; precision set to 50 |
| Frozen dataclasses | `CalculationParams`, `QuoteStep`, `CalculationResult` are immutable — no hidden mutation |
| One module per concern | `calculator.py` has zero I/O; `excel_writer.py` has zero argparse; enables isolated unit testing |
| Insert-at-top via `insert_rows()` | openpyxl shifts existing cells down; previous sheet content is preserved exactly |
| Lookahead before greedy commit | Checks feasibility of candidate before taking the step — avoids dead-zone traps |
