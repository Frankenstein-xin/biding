# Quoting Calculator — Technical Architecture Design

A Python CLI program that finds the **fewest-rounds** price-reduction sequence
from a starting price down to a target price under two per-step constraints,
and appends the result to an xlsx workbook.

## 1. Requirement Restatement

Build a CLI Python program that:

1. Accepts the following **required** parameters (PRD §3):
   - `--start-price` (float) — starting price
   - `--target-price` (float) — target price; if `0`, the program auto-computes it from `--max-pct` and `--min-reduction` (PRD §4)
   - `--max-pct` (float) — maximum percentage reduction per quote (e.g. `5` means 5 %)
   - `--min-reduction` (float) — minimum absolute reduction per quote
   - `--decimals` (int, default `2`) — decimal places to keep in price math (PRD §8)
   - `--rounding` (bool) — `true` → round-half-up, `false` → truncate (PRD §9)
   - `--output` (str) — xlsx result file path
   - `--help` — argparse-provided

2. Finds the **fewest-rounds** quoting sequence from start to target, obeying on every step (PRD §5, §6):
   - `reduction >= min-reduction`
   - `reduction <= current_price * max-pct / 100`
   - Each intermediate price is rounded/truncated to `decimals`
   - The last price must exactly equal the target price
   - Must handle the case PRD §7 warns about: the naive "always maximum reduction" strategy dead-ends before reaching the target

3. Writes results to an xlsx workbook (PRD §10, §11):
   - One sheet per day, sheet name = `YYYY-MM-DD`
   - Multiple runs on the same day **stack in the same sheet**, **newest at the top**, separated by **two blank rows**
   - Each run contains an *Overview* block and a *Quoting Sequence* table

4. **Code must include detailed comments** (PRD §12) and `main` must actually wire the pieces together (PRD §13).

## 2. Document Map

| File | Purpose |
|------|---------|
| [01-architecture.md](./01-architecture.md) | Module layout, data flow, dependencies |
| [02-algorithm.md](./02-algorithm.md) | Quoting algorithm, target auto-calc, rounding rules |
| [03-data-models.md](./03-data-models.md) | Data classes / typed structures |
| [04-excel-format.md](./04-excel-format.md) | Workbook layout, insert-at-top strategy |
| [05-cli-interface.md](./05-cli-interface.md) | CLI argument spec, validation, exit codes |
| [06-task-breakdown.md](./06-task-breakdown.md) | Implementation phases, acceptance criteria |

## 3. Target File Layout (future implementation)

```
biding/
├── plan/                        # this directory
├── requirements/
│   └── prd.md
├── src/
│   └── biding/
│       ├── __init__.py
│       ├── __main__.py          # python -m biding entry
│       ├── cli.py               # argparse wiring
│       ├── models.py            # CalculationParams, QuoteStep, CalculationResult
│       ├── rounding.py          # round / truncate helpers
│       ├── calculator.py        # fewest-rounds sequence algorithm
│       ├── excel_writer.py      # xlsx read + insert-at-top
│       └── main.py              # orchestrates cli -> calculator -> excel_writer
├── tests/
│   ├── test_rounding.py
│   ├── test_calculator.py
│   └── test_excel_writer.py
├── requirements.txt             # openpyxl
└── README.md
```

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime | Python 3.10+ | Modern typing, `match`/`case`, dataclass `kw_only` |
| Numeric representation | `decimal.Decimal` internally | Avoid binary-float drift in percentage compares |
| Excel library | `openpyxl` | Pure-Python, read+write, sheet manipulation |
| Algorithm | Greedy with feasibility lookahead; memoized DFS fallback | Handles the PRD §7 warning that naive "always max reduction" dead-ends |
| Rounding mode | `ROUND_HALF_UP` when `--rounding=true`, else `ROUND_DOWN` | Common business semantics, behind one helper |
| Auto-target (when `--target-price=0`) | `T = quantize(100 * min_reduction / max_pct, decimals)` | Lowest price at which both constraints can still jointly hold; depends only on `P` and `M` as PRD §4 specifies |
| Append order | Read workbook → shift existing rows down → insert new block at the top | Matches PRD §11: "most recent calculation content is at the front" |

## 5. Non-Goals

- GUI / web interface
- Concurrent writers to the same xlsx (single-process CLI, no file lock required)
- Localization
- Performance tuning beyond "< 1 s for realistic inputs"

## 6. Open Questions (Resolved)

- **"Fastest" means** → fewest number of quoting rounds.
- **No feasible sequence exists** → non-zero exit code, clear error message, **nothing written** to the workbook.
- **Auto-target when `target_price == 0`** → see [02-algorithm.md](./02-algorithm.md) §3.
