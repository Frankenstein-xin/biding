# calculator.py — Core quoting algorithm for the Quoting Calculator.
#
# Responsibility: given a validated CalculationParams, find the fewest-rounds
# price-reduction sequence from start_price down to target_price (or an
# auto-computed target when target_price == 0), obeying on every step:
#   reduction >= min_reduction
#   reduction <= current_price * max_pct / 100
#   each intermediate price is quantized to `decimals` places
#   the last price must exactly equal the target
#
# Raises InfeasibleError when no such sequence exists.
#
# This module is a pure function of CalculationParams; it has no I/O and
# does not import argparse or openpyxl.

from __future__ import annotations

import decimal
from datetime import datetime
from decimal import Decimal

from biding.models import CalculationParams, CalculationResult, InfeasibleError, QuoteStep
from biding.rounding import quantize

# Raise decimal precision to avoid drift when chaining many multiplications.
decimal.getcontext().prec = 50


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def auto_target(params: CalculationParams) -> Decimal:
    """Compute the auto-target price when params.target_price == 0.

    Formula (design §3):
        T_auto = quantize( 100 * min_reduction / max_pct, decimals, rounding )

    This is the lowest price at which both the min-reduction and max-percentage
    constraints can still hold simultaneously: at any price below this, the
    max allowed reduction (price * max_pct/100) would fall below min_reduction.
    """
    raw = (Decimal("100") * params.min_reduction) / params.max_pct
    return quantize(raw, params.decimals, params.rounding)


def calculate(params: CalculationParams) -> CalculationResult:
    """Find the fewest-rounds quoting sequence from start_price to target.

    Returns a CalculationResult with the full step-by-step sequence.
    Raises InfeasibleError if no valid sequence exists.
    """
    # Capture the calculation timestamp before any heavy computation
    calc_time = datetime.now()

    # --- Resolve effective target ---
    # target_price == 0 is the sentinel meaning "auto-compute"
    if params.target_price == Decimal("0"):
        target = auto_target(params)
        if target >= params.start_price:
            raise InfeasibleError(
                f"auto-computed target {target} is not below start price "
                f"{params.start_price}"
            )
    else:
        target = params.target_price

    # Quantize start to the configured decimal places so all comparisons are exact
    start = quantize(params.start_price, params.decimals, params.rounding)

    # Trivial case: already at target (no steps needed)
    if start == target:
        return CalculationResult(
            params=params,
            calculation_time=calc_time,
            effective_target=target,
            steps=(),
        )

    # Early feasibility check before entering the search
    if start < target + params.min_reduction:
        raise InfeasibleError(
            f"no feasible sequence: target and start differ by less than "
            f"min-reduction ({params.min_reduction})"
        )

    # Run the lookahead-greedy search to find the shortest path
    path = _find_sequence(start, target, params)

    # Convert the price path into structured QuoteStep objects
    steps = _build_steps(path, params)

    return CalculationResult(
        params=params,
        calculation_time=calc_time,
        effective_target=target,
        steps=tuple(steps),
    )


# ---------------------------------------------------------------------------
# Feasibility helpers
# ---------------------------------------------------------------------------

def _feasible(y: Decimal, target: Decimal, params: CalculationParams) -> bool:
    """Return True if price y can eventually reach target under the constraints.

    Three zones (design §2):
      Dead zone:     y in (target, target + M)  → infeasible
      Direct zone:   y in [target+M, target/(1-P/100)]  → one step lands on target
      Continue zone: y > target/(1-P/100) and y*P/100 >= M  → keep reducing
    """
    M = params.min_reduction
    P = params.max_pct

    if y == target:
        return True

    # Any price below target cannot be reduced to reach target
    if y < target:
        return False

    # Dead zone: the gap to target is smaller than the minimum required reduction
    if y < target + M:
        return False

    # Direct zone: maximum-reduction step lands at or above target
    one_minus_p = Decimal("1") - P / Decimal("100")
    if one_minus_p > 0:
        upper_direct = target / one_minus_p
        if y <= upper_direct:
            return True

    # Continue zone: we can make at least one valid step (max-reduction >= M)
    if y * P / Decimal("100") >= M:
        return True

    return False


def _step_valid(x: Decimal, y: Decimal, params: CalculationParams) -> bool:
    """Return True if the step x → y satisfies both per-step constraints.

    Constraints:
      min_reduction <= x - y <= x * max_pct / 100
    """
    reduction = x - y
    M = params.min_reduction
    max_reduction = x * params.max_pct / Decimal("100")
    return M <= reduction <= max_reduction


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def _candidates(x: Decimal, target: Decimal, params: CalculationParams) -> list[Decimal]:
    """Return ordered candidate next-prices from current price x.

    Candidates (design §4, preference order for fewest rounds):
      1. target itself  — direct hit if valid
      2. x*(1 - P/100) — maximum percentage reduction (fastest progress)
      3. target + M     — safe minimum that still allows a direct hit next step
      4. x - M          — minimum-reduction fallback
    """
    P = params.max_pct
    M = params.min_reduction
    d = params.decimals
    r = params.rounding

    c1 = target
    c2 = quantize(x * (Decimal("1") - P / Decimal("100")), d, r)
    c3 = quantize(target + M, d, r)
    c4 = quantize(x - M, d, r)

    # De-duplicate while preserving preference order
    seen: set[Decimal] = set()
    result: list[Decimal] = []
    for c in [c1, c2, c3, c4]:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Main search: greedy with memoised-DFS fallback
# ---------------------------------------------------------------------------

def _find_sequence(
    start: Decimal, target: Decimal, params: CalculationParams
) -> list[Decimal]:
    """Return the shortest price path [start, ..., target] satisfying constraints.

    Strategy (design §4):
      At each step, try the four candidates in preference order.
      Take the first candidate that is (a) a valid step and (b) feasible.
      If no greedy candidate works, fall back to memoised DFS for that step.
    """
    path: list[Decimal] = [start]
    x = start

    # Upper bound on iterations: each step reduces price by at least min_reduction
    max_iterations = int((start - target) / params.min_reduction) + 10

    for _ in range(max_iterations):
        if x == target:
            break

        # Try greedy candidates in preference order
        chosen: Decimal | None = None
        for y in _candidates(x, target, params):
            if _step_valid(x, y, params) and _feasible(y, target, params):
                chosen = y
                break

        if chosen is None:
            # Greedy exhausted; fall back to memoised DFS for this position
            chosen = _dfs_best_next(x, target, params, memo={})

        if chosen is None:
            raise InfeasibleError(
                f"no feasible sequence from {x} to {target} "
                f"(min_reduction={params.min_reduction}, max_pct={params.max_pct}%)"
            )

        path.append(chosen)
        x = chosen

    if x != target:
        raise InfeasibleError(
            f"no feasible sequence: exceeded iteration limit from {start} to {target}"
        )

    return path


def _dfs_best_next(
    x: Decimal,
    target: Decimal,
    params: CalculationParams,
    memo: dict[Decimal, Decimal | None],
) -> Decimal | None:
    """Memoised DFS: return the best next price from x toward target, or None.

    'Best' means the choice that leads to the fewest total remaining steps.
    The memo dict maps price → best next price (or None if infeasible).
    """
    if x == target:
        return target  # already done

    if x in memo:
        return memo[x]

    # Sentinel to detect cycles (shouldn't happen in practice but be safe)
    memo[x] = None

    best_steps: int | None = None
    best_next: Decimal | None = None

    for y in _candidates(x, target, params):
        if not _step_valid(x, y, params):
            continue
        if not _feasible(y, target, params):
            continue

        # Count steps from y to target via recursion
        steps = _count_steps(y, target, params, memo={})
        if steps is not None:
            total = 1 + steps
            if best_steps is None or total < best_steps:
                best_steps = total
                best_next = y

    memo[x] = best_next
    return best_next


def _count_steps(
    x: Decimal,
    target: Decimal,
    params: CalculationParams,
    memo: dict[Decimal, int | None],
) -> int | None:
    """Return the minimum number of steps from x to target, or None if infeasible."""
    if x == target:
        return 0
    if x in memo:
        return memo[x]

    memo[x] = None  # cycle guard

    best: int | None = None
    for y in _candidates(x, target, params):
        if not _step_valid(x, y, params):
            continue
        if not _feasible(y, target, params):
            continue
        sub = _count_steps(y, target, params, memo)
        if sub is not None:
            total = 1 + sub
            if best is None or total < best:
                best = total

    memo[x] = best
    return best


# ---------------------------------------------------------------------------
# Step construction
# ---------------------------------------------------------------------------

def _build_steps(path: list[Decimal], params: CalculationParams) -> list[QuoteStep]:
    """Convert a list of quantized prices into a list of QuoteStep objects."""
    steps: list[QuoteStep] = []
    for i in range(1, len(path)):
        start_amt = path[i - 1]
        end_amt = path[i]
        reduction = start_amt - end_amt
        # Compute percentage with full Decimal precision, then quantize for display
        pct = quantize(
            reduction / start_amt * Decimal("100"),
            params.decimals,
            params.rounding,
        )
        steps.append(
            QuoteStep(
                round_no=i,
                start_amount=start_amt,
                end_amount=end_amt,
                reduction_amount=reduction,
                reduction_pct=pct,
            )
        )
    return steps
