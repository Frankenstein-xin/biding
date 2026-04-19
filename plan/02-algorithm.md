# 02 — Algorithm

This is the brain of the program. All price values are `decimal.Decimal`;
all comparisons are exact.

## 1. Problem Statement

Given:

- Starting price `S > 0`
- Target price `T >= 0` (if `T == 0`, compute it — see §3)
- Max percentage reduction per step `P` (as a percent, e.g. `5` for 5 %)
- Min absolute reduction per step `M > 0`
- Decimals `d >= 0`
- Rounding mode flag (true → round half up, false → truncate)

Find a sequence `x_0 = S, x_1, x_2, ..., x_n = T` such that, for every step `i = 1..n`:

```
reduction_i    = x_{i-1} - x_i
reduction_i   >= M                         (min-reduction constraint)
reduction_i   <= x_{i-1} * P / 100         (max-percentage constraint)
x_i            = quantize(x_i, d, mode)    (decimals constraint)
x_n            = T exactly
```

**Minimising `n`.**

If no such sequence exists, raise `InfeasibleError`.

## 2. Feasibility Landscape

For a current price `x > T`, partition the real line into zones by the next
valid price `y`:

- **Direct-to-target zone `D`**: `y = T`. Requires `T + M <= x` and `x * (1 - P/100) <= T`, i.e. `x ∈ [T + M, T / (1 - P/100)]`.
- **Continue zone `C`**: `x > T / (1 - P/100)`. After one max-reduction step we land at `x * (1 - P/100)`, which is still above `T` and we continue recursively.
- **Dead zone `Z`**: `x ∈ (T, T + M)`. Cannot reduce by at least `M` without undershooting `T`. Infeasible.

The PRD §7 warning corresponds to a greedy step landing in `Z`.

### 2.1 Feasible precondition (solvability check)

The problem is solvable from `S` iff:
- `S == T`, or
- `S >= T + M` (so at least one step can be taken), and
- `S * P / 100 >= M` whenever `S > T / (1 - P/100)` (so reductions are possible in the continue zone), and
- `S` is reachable by repeated `*(1 - P/100)` ratio jumps into `D`.

The calculator performs this check up front and raises `InfeasibleError`
with a clear message before entering the search.

## 3. Auto-Target when `T == 0`

Per PRD §4, auto-target depends only on `P` and `M`. We define:

```
T_auto = quantize( (100 * M) / P , d, rounding_mode )
```

Rationale: at any price `x < 100 * M / P`, the max allowed reduction
`x * P / 100` is below `M`, so no further reduction is possible. This is
the natural floor implied by the two constraints alone.

**Edge cases:**

- If `T_auto >= S`: `InfeasibleError("auto-computed target {T_auto} is not below start price {S}")`
- If `T_auto == S` after quantizing: `InfeasibleError`
- If `P <= 0` or `M <= 0`: `InfeasibleError` (validated by CLI; defensive check here)

## 4. Search Strategy — Lookahead Greedy

For each step from `x`, candidate next prices considered:

1. `y = T` (direct hit, if valid)
2. `y = quantize(x * (1 - P/100), d, mode)` (max reduction)
3. `y = quantize(T + M, d, mode)` (safe lowest that still lets next step hit `T`)
4. `y = quantize(x - M, d, mode)` (min reduction — fallback)

For **fewest rounds**, the preferred order is 1 → 2 → 3 → 4, taking the first `y` such that:

- `M <= x - y <= x * P / 100` (step is valid)
- `y == T` or `feasible(y)` (next step can make progress)

### 4.1 Feasibility test

```
def feasible(y):
    if y == T:
        return True
    if y < T + M:                # dead zone (including y < T)
        return False
    if y <= T / (1 - P/100):     # direct zone
        return True
    if y * P / 100 < M:          # cannot reduce from here
        return False
    return True                  # continue zone
```

### 4.2 When greedy is not enough — memoised DFS

A pure greedy of candidate 2 can, after quantization, land on a `y` that
violates `feasible(y)`. The algorithm therefore walks the ordered
candidate list and picks the first feasible one. If *none* is feasible
(rare corner cases near rounding boundaries), we fall back to a memoised
DFS:

```
best[x] = optimal (n, path) from x to T, or None
for y in candidates ordered lowest-first:
    sub = best[y]
    if sub is not None:
        store best[x] = (sub.n + 1, [x] + sub.path)
        break
```

The state space is bounded by `(S - T) * 10^d`. For realistic inputs
(`S <= 10^7`, `d <= 4`, `P >= 1 %`) the lookahead greedy accepts
candidate 2 almost always, so DFS rarely runs.

## 5. Worked Examples

Let `d = 2`, rounding on.

### 5.1 Happy path — direct hit

`S = 100, T = 50, P = 50, M = 10` → `reduction = 50 = 100 * 50 %`. Step 1 lands on `T`. Sequence: `[100.00, 50.00]`. `n = 1`.

### 5.2 PRD §7 failure case handled

`S = 100, T = 45, P = 50, M = 10`.

- Naive max-reduction greedy: `100 → 50`, then `50 → 45` needs reduction `5 < M`. **Dead zone.**
- Our algorithm: candidate 1 `y = 45` at `x = 100`? `100 - 45 = 55 > 100 * 50 % = 50`. Rejected.
  Candidate 2: `y = 50`. `feasible(50)`? `50 < T + M = 55`. Dead zone. Rejected.
  Candidate 3: `y = T + M = 55`. `100 - 55 = 45 <= 50`. Valid. `feasible(55)`? `55 ∈ [55, 90]`. Yes.
  Take `100 → 55`. Next step from `55`: candidate 1 `y = 45`. `55 - 45 = 10 >= 10` and `<= 55 * 50 % = 27.5`. Valid. Done. `n = 2`.

### 5.3 Multi-step continue zone

`S = 1000, T = 100, P = 10, M = 5`.

- Step 1: `y = 900` (max reduction). `900 > T/(1-P/100) = 111.11…`, continue zone. Accept.
- Step 2: `y = 810`. Still continue zone.
- … continue until `x_k <= 111.11`, then direct-hit `T`. Converges in `ceil(log(S/T) / log(1/(1-P/100)))` ≈ 22 steps.

## 6. Rounding & Equality

Every produced `x_i` goes through `rounding.quantize` so the final
comparison `x_n == T` is exact under `Decimal`.

The max-percent and min-absolute constraints are checked in **exact Decimal
arithmetic before quantization**. A step whose post-quantize value drifts
outside `[x - x*P/100, x - M]` is rejected and the next candidate is
tried. This avoids off-by-one cent issues at high precision.

## 7. Output Contract

`calculator.calculate(params)` returns:

```
CalculationResult(
    params=params,                 # snapshot
    calculation_time=datetime,     # now(), rendered as "YYYY-MM-DD hh:mm:ss"
    effective_target=T_effective,  # == params.target_price or auto-computed
    steps=[QuoteStep(round=1, start_amount, end_amount, reduction_amount, reduction_pct), ...]
)
```

See [03-data-models.md](./03-data-models.md) for field types.
