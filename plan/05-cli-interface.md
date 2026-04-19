# 05 — CLI Interface

All parsing lives in `src/biding/cli.py`. It emits a validated
`CalculationParams` (see [03-data-models.md](./03-data-models.md)).

## 1. Argument Specification

| Flag | Type (argparse) | Required | Default | Description |
|------|-----------------|----------|---------|-------------|
| `--start-price` | `str` → `Decimal` | yes | — | Starting price |
| `--target-price` | `str` → `Decimal` | yes | — | Target price; `0` means auto-compute |
| `--max-pct` | `str` → `Decimal` | yes | — | Max percentage reduction per quote (e.g. `5` for 5 %) |
| `--min-reduction` | `str` → `Decimal` | yes | — | Min absolute reduction per quote |
| `--decimals` | `int` | yes | — | Price decimal places (PRD §8 says default 2 — we honour that default; still accept explicit values) |
| `--rounding` | `str` → `bool` | yes | — | `true` / `false`; whether price math is rounded (vs truncated) |
| `--output` | `str` → `Path` | yes | — | xlsx result file path |

> PRD §3 states "all these parameters are required parameters". We therefore mark every flag `required=True`, including `--decimals`, despite PRD §8 mentioning a default of `2`. Tooling can inject `--decimals 2` to get the documented default. If stakeholders want default-without-flag, reopen this decision.

## 2. Type Coercion

- **Decimal fields** parsed as `Decimal(value_str)`. Rejects inputs like `"1e2"` or `"nan"` via a custom type function that raises `argparse.ArgumentTypeError` with a clear message.
- **Boolean field** accepts, case-insensitively: `true, false, yes, no, 1, 0, y, n, on, off`. Anything else → `ArgumentTypeError`.
- **Path** is `Path(value).expanduser().resolve()`.

## 3. Sample Invocations

```bash
python -m biding \
  --start-price 100 \
  --target-price 45 \
  --max-pct 50 \
  --min-reduction 10 \
  --decimals 2 \
  --rounding true \
  --output ./out/quotes.xlsx
```

Auto-target variant:

```bash
python -m biding \
  --start-price 1000 \
  --target-price 0 \
  --max-pct 10 \
  --min-reduction 5 \
  --decimals 2 \
  --rounding true \
  --output ./out/quotes.xlsx
```

## 4. Exit Codes

| Code | Meaning | Trigger |
|------|---------|---------|
| `0` | Success | Calculation produced a sequence and was written |
| `2` | Argparse error | Missing or malformed argument (argparse native) |
| `3` | Validation error | `CalculationParams.__post_init__` raised (e.g. negative price) |
| `4` | Infeasible | `calculator.InfeasibleError` — no sequence possible |
| `5` | I/O error | xlsx read/write failed |
| `1` | Unexpected | any other exception (bug — logs traceback to stderr) |

`main.main(argv)` returns the integer code; `__main__.py` calls
`sys.exit(main(sys.argv[1:]))`.

## 5. Console Output

Success (stdout):

```
Found sequence in 2 rounds.
Start: 100.00  ->  End: 45.00
Output: /abs/path/out/quotes.xlsx (sheet: 2026-04-19)
```

Validation error (stderr):

```
error: start-price must be > 0
```

Infeasible (stderr):

```
error: no feasible sequence: target and start differ by less than min-reduction (10)
```

I/O error (stderr):

```
error: failed to write xlsx: [Errno 13] Permission denied: '/abs/path/out/quotes.xlsx'
```

No stack trace in exit codes 2–5; full traceback only on exit code 1.

## 6. Help Text

`argparse` auto-renders `--help`. Each flag carries a one-line `help=`
string matching §1. The epilogue shows one example invocation.

## 7. Non-Interactive

No prompts. No stdin reads. Fully scriptable. Returns promptly.
