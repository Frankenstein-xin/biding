# 06 — Task Breakdown & Acceptance Criteria

Implementation is split into 6 ordered phases. Each phase has an explicit
*Definition of Done* so the work can be parallelised or paused cleanly.

## Phase 1 — Project Skeleton

**Scope**: directory tree, `requirements.txt`, empty modules, `__main__.py`.

- Create `src/biding/{__init__,__main__,cli,models,rounding,calculator,excel_writer,main}.py`.
- Create `tests/` with `__init__.py`.
- `requirements.txt` with `openpyxl>=3.1,<4`.
- `README.md` in repo root (brief usage).

**DoD**: `python -m biding --help` prints argparse help (even if stub); `pytest` collects 0 tests without error.

## Phase 2 — `rounding.py` + tests

**Scope**: `quantize(value, decimals, rounding_on)`.

- `quantize` uses `ROUND_HALF_UP` when `rounding_on` is true, else `ROUND_DOWN`.
- Accepts `Decimal`, returns `Decimal`.
- Tests (`tests/test_rounding.py`):
  - `quantize(Decimal("1.235"), 2, True)  == Decimal("1.24")`
  - `quantize(Decimal("1.235"), 2, False) == Decimal("1.23")`
  - `quantize(Decimal("1"),     0, True)  == Decimal("1")`
  - Preserves scale (always exactly `decimals` digits after point).

**DoD**: `pytest tests/test_rounding.py` passes.

## Phase 3 — `models.py` + tests

**Scope**: `CalculationParams`, `QuoteStep`, `CalculationResult`, `InfeasibleError`.

- Dataclasses with `frozen=True, kw_only=True`.
- `__post_init__` validation per [03-data-models.md §1.1](./03-data-models.md).
- Tests (`tests/test_models.py`):
  - Valid construction → no error.
  - Each invalid field raises `ValueError` with expected message.
  - Objects are hashable and equal when fields match.

**DoD**: `pytest tests/test_models.py` passes.

## Phase 4 — `calculator.py` + tests

**Scope**: `auto_target`, `calculate`.

- Implements the algorithm in [02-algorithm.md](./02-algorithm.md).
- Raises `InfeasibleError` early when preconditions fail.
- Returns `CalculationResult` with exact `Decimal` arithmetic.
- Tests (`tests/test_calculator.py`):
  - **Happy path** — `S=100, T=50, P=50, M=10` → 1 round.
  - **PRD §7 failure case** — `S=100, T=45, P=50, M=10` → 2 rounds, sequence `[100, 55, 45]`.
  - **Multi-step continue zone** — `S=1000, T=100, P=10, M=5` → `n ≈ 22`, every step satisfies constraints, final equals target.
  - **Auto-target** — `T=0, M=5, P=10, d=2` → `effective_target == Decimal("50.00")`.
  - **Infeasible** — `S=10, T=5, P=10, M=10` → raises `InfeasibleError`.
  - **Rounding off vs on** — same inputs with `rounding=False` truncates; last step still lands exactly on `T`.
  - **Property test (hypothesis, optional)** — for random valid params, every produced step satisfies both constraints and the final equals target.

**DoD**: `pytest tests/test_calculator.py` passes.

## Phase 5 — `excel_writer.py` + tests

**Scope**: `write_result(result, output_path)`.

- Implements the layout in [04-excel-format.md](./04-excel-format.md).
- Tests (`tests/test_excel_writer.py`) use `tmp_path`:
  - **New file** — writes today's sheet with one block; reload via `openpyxl` and assert cells match.
  - **Same-day second run** — second `write_result` on the same day produces: block2 at row 1, block1 shifted by `len(block2) + 2`, rows in between are blank. Sheet count is unchanged.
  - **Different day** — override `calculation_time` on the `CalculationResult` so the second run goes to a new sheet; previous sheet's data is untouched.
  - **Nested output path** — writing to `tmp_path / "nested/dir/quotes.xlsx"` creates the parent directory.
  - **Corrupt file** — pre-create a bogus file at `output_path`; assert `InvalidFileException` propagates.

**DoD**: `pytest tests/test_excel_writer.py` passes.

## Phase 6 — `cli.py` + `main.py` + integration tests

**Scope**: argparse wiring, orchestration, exit codes.

- `cli.parse_args(argv)` → `CalculationParams`.
- `main.main(argv)` returns an int per [05-cli-interface.md §4](./05-cli-interface.md).
- Tests (`tests/test_main.py`):
  - `main(["--start-price", "100", ...])` happy path → exit 0, file produced.
  - Missing required flag → exit 2 (via `SystemExit`).
  - Negative start-price → exit 3.
  - Infeasible inputs → exit 4.
  - Unwritable output path → exit 5 (skip on CI if unable to simulate).

**DoD**: `pytest` runs all tests green; `python -m biding ...` with a real input produces a readable xlsx.

## Cross-Phase Acceptance Criteria

- [ ] Every module has a top-of-file comment explaining its responsibility (English, matching [01-architecture.md §1](./01-architecture.md)).
- [ ] Every public function has a docstring (English).
- [ ] Every non-trivial block has an inline comment (per PRD §12).
- [ ] `main.py` actually imports and calls `cli.parse_args`, `calculator.calculate`, and `excel_writer.write_result` (per PRD §13).
- [ ] No `float` appears in `calculator.py` or `excel_writer.py` (grep).
- [ ] `pytest -q` reports 100 % of listed tests passing.
- [ ] A smoke run of the sample invocation in [05-cli-interface.md §3](./05-cli-interface.md) produces a valid xlsx with the expected sheet name and block shape.

## Estimated Effort

| Phase | Complexity | Rough time |
|-------|------------|-----------|
| 1 — Skeleton | Low | 15 min |
| 2 — rounding | Low | 20 min |
| 3 — models | Low | 30 min |
| 4 — calculator | **Medium-High** | 2–3 h |
| 5 — excel_writer | Medium | 1–1.5 h |
| 6 — cli + main + integration | Medium | 1–1.5 h |
| **Total** | — | **5–7 h** |

## Risk Log

| Risk | Mitigation |
|------|------------|
| Greedy with lookahead misses optimum in odd rounding corner cases | Fallback memoised DFS (§4.2 of [02-algorithm.md](./02-algorithm.md)); property-based test |
| `openpyxl insert_rows` breaks formatting | Tests reload workbook and compare values; formatting is light (bold only) |
| Platform path issues (Windows vs POSIX) | `pathlib.Path` everywhere; tests use `tmp_path` |
| Decimal precision overflow | `getcontext().prec = 50` at calculator module level |
| PRD ambiguity about auto-target semantics | Documented interpretation in [02-algorithm.md §3](./02-algorithm.md); flagged for stakeholder review in PR |
