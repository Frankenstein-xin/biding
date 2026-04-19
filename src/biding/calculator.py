"""Core quoting algorithm.

Given a ``CalculationParams``, produce the *fewest-rounds* price
reduction sequence from ``start_price`` to ``target_price`` that obeys
on every step:

* reduction >= ``min_reduction``  (absolute floor)
* reduction <= current_price * ``max_pct`` / 100  (relative ceiling)
* every intermediate price is quantised to ``decimals`` places
* the last price is exactly the effective target

If ``target_price`` is ``0`` the target is auto-computed from
``max_pct`` and ``min_reduction`` per plan/02-algorithm §3.

The approach is a lookahead-greedy search with memoised DFS fallback.
See the algorithm design doc for the rationale, the four candidate
next-prices, and the feasibility tests; this module is the faithful
translation of that design.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, getcontext
from typing import Optional

from biding.models import (
    CalculationParams,
    CalculationResult,
    InfeasibleError,
    QuoteStep,
)
from biding.rounding import quantize


# Generous precision for intermediate exact arithmetic.  We never rely
# on this for display, only for internal comparisons.
getcontext().prec = 50

_HUNDRED = Decimal("100")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def auto_target(params: CalculationParams) -> Decimal:
    """Compute the auto target price when the user passed ``--target-price 0``.

    ``T_auto = quantize(100 * M / P, decimals, rounding)`` — the floor
    price at which the max-percent constraint can still accommodate the
    min-absolute constraint (see plan/02-algorithm §3).
    """
    raw = (_HUNDRED * params.min_reduction) / params.max_pct
    return quantize(raw, params.decimals, params.rounding)


def calculate(params: CalculationParams) -> CalculationResult:
    """Produce the fewest-rounds quoting sequence.

    Raises:
        InfeasibleError: when no sequence satisfying all constraints exists.
    """
    started_at = datetime.now()

    # --- 1. Resolve the effective target. ----------------------------------
    if params.target_price == 0:
        target = auto_target(params)
        if target >= params.start_price:
            raise InfeasibleError(
                f"auto-computed target {target} is not below start price "
                f"{params.start_price}"
            )
    else:
        target = quantize(params.target_price, params.decimals, params.rounding)

    start = quantize(params.start_price, params.decimals, params.rounding)

    if start == target:
        # Degenerate but technically feasible — no steps required.
        return CalculationResult(
            params=params,
            calculation_time=started_at,
            effective_target=target,
            steps=(),
        )

    if start < target:
        raise InfeasibleError(
            f"start-price {start} is below target {target}"
        )

    # --- 2. Search for the fewest-rounds sequence. -------------------------
    path = _search(start, target, params)
    if path is None:
        raise InfeasibleError(
            "no feasible sequence: constraints cannot reach the target "
            f"(start={start}, target={target}, max-pct={params.max_pct}, "
            f"min-reduction={params.min_reduction})"
        )

    steps = _path_to_steps(path, params)
    return CalculationResult(
        params=params,
        calculation_time=started_at,
        effective_target=target,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _candidates(
    x: Decimal, target: Decimal, params: CalculationParams
) -> list[Decimal]:
    """Return candidate next prices in preferred (fewest-rounds) order.

    Candidate order follows plan/02-algorithm §4:

    1. direct hit on the target
    2. max reduction (the most aggressive step we are allowed to take)
    3. "safe lowest" — land exactly on ``target + min_reduction``
       so that the *next* step can hit the target directly
    4. min reduction — conservative fallback
    """
    d = params.decimals
    r = params.rounding
    p_ratio = params.max_pct / _HUNDRED

    result: list[Decimal] = []

    def _push(v: Decimal) -> None:
        qv = quantize(v, d, r)
        if qv < target:
            return
        if qv >= x:
            return
        if qv not in result:
            result.append(qv)

    # 1. direct hit
    _push(target)
    # 2. max reduction
    _push(x - x * p_ratio)
    # 3. safe lowest (target + min_reduction)
    _push(target + params.min_reduction)
    # 4. min reduction
    _push(x - params.min_reduction)

    return result


def _step_valid(x: Decimal, y: Decimal, params: CalculationParams) -> bool:
    """Is the transition ``x -> y`` allowed by the two constraints?"""
    reduction = x - y
    if reduction < params.min_reduction:
        return False
    max_reduction = x * params.max_pct / _HUNDRED
    if reduction > max_reduction:
        return False
    return True


def _feasible(y: Decimal, target: Decimal, params: CalculationParams) -> bool:
    """Can we reach ``target`` starting from ``y``?

    Mirrors plan/02-algorithm §4.1.  Cheap to compute; used to prune the
    greedy search so we never commit to a step that strands us in the
    dead zone ``(target, target + min_reduction)``.
    """
    if y == target:
        return True
    if y < target + params.min_reduction:
        return False
    if params.max_pct <= 0:
        return False
    direct_ceiling = target * _HUNDRED / (_HUNDRED - params.max_pct)
    if y <= direct_ceiling:
        return True
    # Continue zone — ensure at least the minimum reduction is allowed
    # at ``y``; otherwise we would be stuck here.
    if y * params.max_pct / _HUNDRED < params.min_reduction:
        return False
    return True


def _search(
    start: Decimal, target: Decimal, params: CalculationParams
) -> Optional[list[Decimal]]:
    """Return the fewest-rounds path ``[start, ..., target]`` or ``None``.

    Uses a memoised DFS over the candidate lattice.  The candidate set
    at each node is small (<= 4) and the feasibility predicate prunes
    almost all dead ends, so the search is fast for realistic inputs.
    """
    memo: dict[Decimal, Optional[list[Decimal]]] = {}

    # Depth cap prevents pathological inputs (near-zero max_pct) from
    # spinning the search.  ``log(start/target) / log(1/(1-p))`` is the
    # continue-zone bound; we allow a large multiple to cover arbitrary
    # min-reduction walks.
    depth_cap = 10_000

    def dfs(x: Decimal, depth: int) -> Optional[list[Decimal]]:
        if x == target:
            return [x]
        if depth > depth_cap:
            return None
        if x in memo:
            return memo[x]
        memo[x] = None  # cycle guard

        best: Optional[list[Decimal]] = None
        for y in _candidates(x, target, params):
            if not _step_valid(x, y, params):
                continue
            if not _feasible(y, target, params):
                continue
            sub = dfs(y, depth + 1)
            if sub is None:
                continue
            candidate_path = [x] + sub
            if best is None or len(candidate_path) < len(best):
                best = candidate_path

        memo[x] = best
        return best

    return dfs(start, 0)


def _path_to_steps(
    path: list[Decimal], params: CalculationParams
) -> tuple[QuoteStep, ...]:
    """Translate a list of prices into ``QuoteStep`` rows.

    Reduction percentage is computed relative to the round's start
    amount and quantised via the user's rounding policy so it renders
    cleanly in the xlsx.
    """
    steps: list[QuoteStep] = []
    for i in range(1, len(path)):
        start_amount = path[i - 1]
        end_amount = path[i]
        reduction = start_amount - end_amount
        pct_raw = reduction * _HUNDRED / start_amount
        pct = quantize(pct_raw, params.decimals, params.rounding)
        steps.append(
            QuoteStep(
                round_no=i,
                start_amount=start_amount,
                end_amount=end_amount,
                reduction_amount=reduction,
                reduction_pct=pct,
            )
        )
    return tuple(steps)


__all__ = ["calculate", "auto_target"]
