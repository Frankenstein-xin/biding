# 03 — Data Models

All models live in `src/biding/models.py`. They are plain
`@dataclass(frozen=True, kw_only=True)` classes with no methods beyond
`__post_init__` validation. No module-level side effects.

## 1. `CalculationParams`

Validated CLI input. Immutable snapshot carried end-to-end.

```python
@dataclass(frozen=True, kw_only=True)
class CalculationParams:
    start_price: Decimal           # > 0
    target_price: Decimal          # >= 0 ; 0 means auto-compute
    max_pct: Decimal               # percentage, > 0 and < 100
    min_reduction: Decimal         # > 0
    decimals: int                  # >= 0
    rounding: bool                 # True  -> ROUND_HALF_UP
                                   # False -> ROUND_DOWN (truncate)
    output_path: Path              # destination xlsx file
```

### Validation rules (in `__post_init__`)

| Field | Rule | Error message |
|-------|------|---------------|
| `start_price` | `> 0` | `"start-price must be > 0"` |
| `target_price` | `>= 0` | `"target-price must be >= 0"` |
| `max_pct` | `> 0 and < 100` | `"max-pct must be in (0, 100)"` |
| `min_reduction` | `> 0` | `"min-reduction must be > 0"` |
| `decimals` | `>= 0` | `"decimals must be >= 0"` |
| cross | `target_price == 0 or target_price < start_price` | `"target-price must be < start-price (or 0 to auto-compute)"` |

`max_pct` is stored as a percent (e.g. `5`), not a ratio. `calculator.py`
divides by `100` where needed.

## 2. `QuoteStep`

One row in the *Quoting Sequence* table.

```python
@dataclass(frozen=True, kw_only=True)
class QuoteStep:
    round_no: int                  # 1-based, per PRD §11
    start_amount: Decimal          # price before this round's reduction
    end_amount: Decimal            # price after this round's reduction
    reduction_amount: Decimal      # start_amount - end_amount
    reduction_pct: Decimal         # = reduction_amount / start_amount * 100
```

Invariants (asserted in tests, not enforced in `__post_init__`):

- `start_amount - end_amount == reduction_amount`
- `reduction_amount / start_amount * 100 == reduction_pct` (Decimal-exact)
- `round_no >= 1`

## 3. `CalculationResult`

Output of `calculator.calculate`.

```python
@dataclass(frozen=True, kw_only=True)
class CalculationResult:
    params: CalculationParams      # snapshot of validated input
    calculation_time: datetime     # datetime.now() at start of calculate()
    effective_target: Decimal      # params.target_price or auto-computed
    steps: tuple[QuoteStep, ...]   # non-empty if start_price != effective_target
```

### Rendering helpers (in `excel_writer.py`, not on the model)

| Purpose | Format |
|---------|--------|
| Sheet name from `calculation_time` | `"%Y-%m-%d"` (e.g. `2026-04-19`) |
| Overview timestamp cell | `"%Y-%m-%d %H:%M:%S"` (e.g. `2026-04-19 10:30:00`) |
| Decimal → cell string | `format(value, "f")` (already quantized) |
| Reduction percentage cell | `format(reduction_pct, "f") + " %"` |

Keeping rendering out of the model prevents accidental coupling between
data and presentation.

## 4. `InfeasibleError`

Custom exception raised by `calculator.calculate` when no valid sequence
exists.

```python
class InfeasibleError(ValueError):
    """Raised when constraints make the target unreachable."""
```

Subclassing `ValueError` lets `main.py` catch generic input errors
uniformly.

## 5. Type Conventions

- All monetary values are `decimal.Decimal` at rest. The CLI parses
  **strings** directly into `Decimal` (never `float`) to preserve user
  precision.
- Percentages are `Decimal` in percent units (not ratios). `5` means 5 %.
- Never use `float` for money. The only `float` appears transiently in
  argparse and is immediately converted via `Decimal(str(value))`.
- `Path` from `pathlib`, not raw strings, inside `CalculationParams`.

## 6. Backwards / Forwards Compatibility

Not a goal. There is no persisted pickle format; every run reconstructs
these objects from CLI + xlsx.
