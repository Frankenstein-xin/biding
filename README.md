# biding — Quoting Calculator

A Python CLI that finds the **fewest-rounds** price-reduction sequence
from a starting price down to a target price under two per-step
constraints, and appends the result to an `.xlsx` workbook.

## Overview

Given:

- a starting price,
- a target price (or `0` to auto-compute),
- a maximum **percentage** reduction per quote,
- a minimum **absolute** reduction per quote,
- a rounding policy (round-half-up or truncate) and decimal precision,

`biding` finds the shortest sequence of quotes that reaches the target
without violating either constraint on any step, then saves the
overview + sequence to an xlsx file (one sheet per day, newest run at
the top).

The naive "always reduce by the maximum percentage" strategy can dead-
end in the interval `(target, target + min_reduction)` where no further
reduction of at least `min_reduction` is allowed. The algorithm uses
lookahead-greedy search over a small ordered set of candidate next
prices, guarded by a feasibility predicate, to avoid that trap.

## Architecture

```
┌──────────┐
│  main    │  orchestrates the pipeline, maps errors to exit codes
└────┬─────┘
     │
 ┌───┴────────────┬────────────────┐
 ▼                ▼                ▼
┌───────┐   ┌───────────┐   ┌──────────────┐
│ cli   │──▶│ calculator│   │ excel_writer │
└───────┘   └─────┬─────┘   └──────┬───────┘
                  │                │
                  ▼                ▼
              ┌──────┐         ┌────────┐
              │round.│         │ models │
              └──────┘         └────────┘
```

Module responsibilities:

| Module | Responsibility |
|--------|----------------|
| `cli.py` | argparse parsing, string→Decimal/bool/Path coercion |
| `models.py` | Frozen dataclasses: `CalculationParams`, `QuoteStep`, `CalculationResult`; `InfeasibleError` |
| `rounding.py` | `Decimal` quantise with round-half-up vs truncate |
| `calculator.py` | Fewest-rounds search; auto-target when `target=0` |
| `excel_writer.py` | xlsx read/write; prepend blocks inside today's sheet |
| `main.py` | glue + exit codes + console summary |
| `__main__.py` | `python -m biding` entry |

Design docs: [`plan/`](./plan/). Requirements: [`requirements/prd.md`](./requirements/prd.md).

## Installation

The project uses [`uv`](https://github.com/astral-sh/uv) for virtual-env
and dependency management.

```bash
# Clone the repo and cd into it
uv venv --python 3.12
uv sync --dev
```

This creates `.venv/`, installs `openpyxl` (runtime) and `pytest`
(dev), and performs an editable install of the `biding` package.

## Usage

```bash
# Direct explicit target:
uv run python -m biding \
  --start-price 100 \
  --target-price 45 \
  --max-pct 50 \
  --min-reduction 10 \
  --decimals 2 \
  --rounding true \
  --output ./out/quotes.xlsx

# Auto-compute target from the two constraints:
uv run python -m biding \
  --start-price 1000 \
  --target-price 0 \
  --max-pct 10 \
  --min-reduction 5 \
  --decimals 2 \
  --rounding true \
  --output ./out/quotes.xlsx
```

After install you can also use the `biding` console script:

```bash
uv run biding --help
```

### Arguments

All arguments are required.

| Flag | Type | Notes |
|------|------|-------|
| `--start-price` | Decimal | > 0 |
| `--target-price` | Decimal | `0` means auto-compute from `--max-pct` and `--min-reduction` |
| `--max-pct` | Decimal | percent units, e.g. `5` for 5 %. Must be in `(0, 100)` |
| `--min-reduction` | Decimal | > 0, absolute floor per step |
| `--decimals` | int | ≥ 0, decimal places kept in price math |
| `--rounding` | bool | `true` = round-half-up, `false` = truncate |
| `--output` | path | xlsx result file (parents auto-created) |

### Output workbook

- One sheet per day, named `YYYY-MM-DD` (e.g. `2026-04-19`).
- Each run writes an **Overview** block (calculation time, parameters)
  and a **Quoting Sequence** table (round, start amount, end amount,
  reduction amount, reduction percentage).
- Same-day runs are prepended at the top of the sheet, separated from
  the previous run by two blank rows — **newest first**.
- Different days produce additional sheets; previous sheets are
  untouched.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | argparse error (missing/malformed arg) |
| `3` | Validation error (e.g. `start-price <= 0`) |
| `4` | Infeasible (no sequence satisfies the constraints) |
| `5` | xlsx read/write failed |
| `1` | Unexpected (bug; traceback on stderr) |

## Development

```bash
# Run tests
uv run pytest -q
```

## Project layout

```
biding/
├── plan/                   # design docs (architecture, algorithm, cli, xlsx, tasks)
├── requirements/
│   └── prd.md              # original product spec
├── src/biding/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── models.py
│   ├── rounding.py
│   ├── calculator.py
│   ├── excel_writer.py
│   └── main.py
├── tests/
│   └── test_biding.py
├── pyproject.toml
└── README.md
```

## License

See [LICENSE](./LICENSE).
