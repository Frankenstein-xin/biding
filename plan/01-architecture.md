# 01 — Architecture

## 1. Module Responsibilities

| Module | Responsibility | Public surface |
|--------|----------------|----------------|
| `cli.py` | Parse & validate command-line args, return a typed `CalculationParams` | `build_parser() -> argparse.ArgumentParser`, `parse_args(argv) -> CalculationParams` |
| `models.py` | Plain data classes (no logic) | `CalculationParams`, `QuoteStep`, `CalculationResult` |
| `rounding.py` | Rounding / truncation of `Decimal` values to configured decimals | `quantize(value, decimals, rounding_on) -> Decimal` |
| `calculator.py` | Core algorithm: compute auto-target (if needed) and produce the fewest-rounds sequence | `calculate(params) -> CalculationResult`, `auto_target(params) -> Decimal` |
| `excel_writer.py` | Read existing workbook (if any), prepend a new run block to today's sheet, save | `write_result(result, output_path) -> None` |
| `main.py` | Glue: `cli -> calculator -> excel_writer`; handles errors, exit codes, console output | `main(argv=None) -> int` |
| `__main__.py` | Enables `python -m biding ...` | delegates to `main.main` |

No module imports `argparse` except `cli.py`. No module imports `openpyxl` except `excel_writer.py`. This keeps `calculator.py` pure and fully unit-testable.

## 2. Dependency Direction

```
           +----------+
           |  main    |
           +----+-----+
                |
       +--------+-----------+----------------+
       v                    v                v
  +---------+         +-------------+  +--------------+
  |   cli   | ------> | calculator  |  | excel_writer |
  +---------+  params +-------------+  +--------------+
                         |  uses             |  uses
                         v                   v
                    +----------+        +----------+
                    | rounding |        |  models  |
                    +----------+        +----------+
                         |                   ^
                         +-------------------+
                             both use models
```

- `calculator`, `excel_writer`, `rounding`, `models` must have **zero** cross-module side effects at import time.
- `main` is the only place that performs I/O beyond xlsx file read/write.

## 3. Runtime Data Flow

```
argv
  │
  ▼ cli.parse_args
CalculationParams  (dataclass, Decimal fields)
  │
  ▼ calculator.calculate
CalculationResult  (dataclass: params snapshot + list[QuoteStep] + calculation_time)
  │
  ▼ excel_writer.write_result(result, params.output)
xlsx file updated in place
```

Error paths:

- `cli.parse_args` → `argparse.ArgumentError` / `SystemExit(2)` (standard argparse behavior)
- `calculator.calculate` → raises `InfeasibleError` (custom) when no sequence exists
- `excel_writer.write_result` → raises `OSError` on FS problems, `InvalidFileException` on corrupt xlsx
- `main.main` catches these, prints an English error to `stderr`, returns non-zero exit code (see [05-cli-interface.md §4](./05-cli-interface.md))

## 4. External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openpyxl` | `>=3.1,<4` | xlsx read/write |
| `python` | `>=3.10` | language runtime |

All other functionality (argparse, decimal, datetime, dataclasses, pathlib) is standard library.

`requirements.txt`:
```
openpyxl>=3.1,<4
```

## 5. Testability

- `calculator.calculate` is a **pure function** of `CalculationParams` → deterministic output; trivial to property-test.
- `excel_writer.write_result` takes a `Path`; tests use `tmp_path` fixtures from pytest.
- `rounding.quantize` is a pure function.
- `main` is tested via subprocess or by invoking `main(argv=[...])` directly.

See [06-task-breakdown.md](./06-task-breakdown.md) for the test matrix.

## 6. Console Output

- No logging framework; `main` writes a short English summary to `stdout` on success (rounds, first/last price, output path) and errors to `stderr`.
- `calculator` and `excel_writer` never write to the console — they return values / raise exceptions.
