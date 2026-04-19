# test_calculator.py — Unit tests for biding.calculator.

from decimal import Decimal
from pathlib import Path

import pytest

from biding.calculator import auto_target, calculate
from biding.models import CalculationParams, InfeasibleError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _params(**overrides) -> CalculationParams:
    defaults = dict(
        start_price=Decimal("100"),
        target_price=Decimal("45"),
        max_pct=Decimal("50"),
        min_reduction=Decimal("10"),
        decimals=2,
        rounding=True,
        output_path=Path("/tmp/test.xlsx"),
    )
    defaults.update(overrides)
    return CalculationParams(**defaults)


def _assert_steps_valid(result, params: CalculationParams) -> None:
    """Assert every step in result satisfies the per-step constraints."""
    for step in result.steps:
        assert step.reduction_amount >= params.min_reduction, (
            f"Round {step.round_no}: reduction {step.reduction_amount} < "
            f"min_reduction {params.min_reduction}"
        )
        max_red = step.start_amount * params.max_pct / Decimal("100")
        assert step.reduction_amount <= max_red, (
            f"Round {step.round_no}: reduction {step.reduction_amount} > "
            f"max allowed {max_red}"
        )
        assert step.end_amount == step.start_amount - step.reduction_amount


# ---------------------------------------------------------------------------
# Happy path — direct hit in one round
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_direct_hit_one_round(self):
        # S=100, T=50, P=50, M=10 → reduction=50 exactly equals 100*50%, done in 1 round
        p = _params(target_price=Decimal("50"), max_pct=Decimal("50"), min_reduction=Decimal("10"))
        result = calculate(p)
        assert len(result.steps) == 1
        assert result.steps[0].start_amount == Decimal("100.00")
        assert result.steps[0].end_amount == Decimal("50.00")
        assert result.effective_target == Decimal("50.00")

    def test_last_price_equals_target_exactly(self):
        p = _params(target_price=Decimal("50"), max_pct=Decimal("50"), min_reduction=Decimal("10"))
        result = calculate(p)
        assert result.steps[-1].end_amount == result.effective_target


# ---------------------------------------------------------------------------
# PRD §7 failure case — naive greedy dead-ends, algorithm must route around it
# ---------------------------------------------------------------------------

class TestPrdSection7FailureCase:
    def test_avoids_dead_zone(self):
        # S=100, T=45, P=50, M=10
        # Naive max-reduction: 100→50, then 50→45 needs reduction=5 < M=10. Dead zone.
        # Correct path: 100→55→45 (2 rounds)
        p = _params(
            start_price=Decimal("100"),
            target_price=Decimal("45"),
            max_pct=Decimal("50"),
            min_reduction=Decimal("10"),
        )
        result = calculate(p)
        prices = [result.steps[0].start_amount] + [s.end_amount for s in result.steps]
        assert len(result.steps) == 2
        assert prices[0] == Decimal("100.00")
        assert prices[1] == Decimal("55.00")
        assert prices[2] == Decimal("45.00")
        _assert_steps_valid(result, p)

    def test_final_price_is_target(self):
        p = _params(
            start_price=Decimal("100"),
            target_price=Decimal("45"),
            max_pct=Decimal("50"),
            min_reduction=Decimal("10"),
        )
        result = calculate(p)
        assert result.steps[-1].end_amount == Decimal("45.00")


# ---------------------------------------------------------------------------
# Multi-step continue zone
# ---------------------------------------------------------------------------

class TestMultiStepContinueZone:
    def test_many_steps_converge(self):
        # S=1000, T=100, P=10, M=5 → many steps, all must be valid, final==target
        p = _params(
            start_price=Decimal("1000"),
            target_price=Decimal("100"),
            max_pct=Decimal("10"),
            min_reduction=Decimal("5"),
        )
        result = calculate(p)
        assert len(result.steps) > 5, "Expected many steps in continue zone"
        _assert_steps_valid(result, p)
        assert result.steps[-1].end_amount == Decimal("100.00")

    def test_step_count_reasonable(self):
        # ceil(log(1000/100) / log(1/0.9)) ≈ 22; allow some slack
        p = _params(
            start_price=Decimal("1000"),
            target_price=Decimal("100"),
            max_pct=Decimal("10"),
            min_reduction=Decimal("5"),
        )
        result = calculate(p)
        assert len(result.steps) <= 50


# ---------------------------------------------------------------------------
# Auto-target (target_price == 0)
# ---------------------------------------------------------------------------

class TestAutoTarget:
    def test_auto_target_formula(self):
        # T_auto = quantize(100 * M / P, d, rounding) = quantize(100*5/10, 2, True) = 50.00
        p = _params(
            target_price=Decimal("0"),
            max_pct=Decimal("10"),
            min_reduction=Decimal("5"),
            decimals=2,
            rounding=True,
        )
        t = auto_target(p)
        assert t == Decimal("50.00")

    def test_calculate_with_auto_target(self):
        p = _params(
            start_price=Decimal("1000"),
            target_price=Decimal("0"),
            max_pct=Decimal("10"),
            min_reduction=Decimal("5"),
            decimals=2,
            rounding=True,
        )
        result = calculate(p)
        assert result.effective_target == Decimal("50.00")
        assert result.steps[-1].end_amount == Decimal("50.00")
        _assert_steps_valid(result, p)

    def test_auto_target_infeasible_when_above_start(self):
        # M=60, P=10 → T_auto = 600, but start=100 → infeasible
        with pytest.raises(InfeasibleError):
            calculate(_params(
                start_price=Decimal("100"),
                target_price=Decimal("0"),
                max_pct=Decimal("10"),
                min_reduction=Decimal("60"),
            ))


# ---------------------------------------------------------------------------
# Infeasible cases
# ---------------------------------------------------------------------------

class TestInfeasible:
    def test_gap_less_than_min_reduction(self):
        # start=10, target=5, gap=5 but min_reduction=10 → gap < min_reduction
        with pytest.raises(InfeasibleError):
            calculate(_params(
                start_price=Decimal("10"),
                target_price=Decimal("5"),
                max_pct=Decimal("10"),
                min_reduction=Decimal("10"),
            ))

    def test_target_too_close_to_start(self):
        # start=100, target=99, min_reduction=10 → gap=1 < M=10
        with pytest.raises(InfeasibleError):
            calculate(_params(
                start_price=Decimal("100"),
                target_price=Decimal("99"),
                max_pct=Decimal("50"),
                min_reduction=Decimal("10"),
            ))


# ---------------------------------------------------------------------------
# Rounding mode
# ---------------------------------------------------------------------------

class TestRoundingMode:
    def test_rounding_on_lands_on_target(self):
        result = calculate(_params(rounding=True))
        assert result.steps[-1].end_amount == result.effective_target

    def test_rounding_off_lands_on_target(self):
        result = calculate(_params(rounding=False))
        assert result.steps[-1].end_amount == result.effective_target


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_result_contains_params_snapshot(self):
        p = _params()
        result = calculate(p)
        assert result.params is p

    def test_steps_are_tuple(self):
        result = calculate(_params())
        assert isinstance(result.steps, tuple)

    def test_round_numbers_are_sequential(self):
        p = _params(
            start_price=Decimal("1000"),
            target_price=Decimal("100"),
            max_pct=Decimal("10"),
            min_reduction=Decimal("5"),
        )
        result = calculate(p)
        for i, step in enumerate(result.steps, start=1):
            assert step.round_no == i

    def test_consecutive_steps_connect(self):
        # Each step's start_amount must equal the previous step's end_amount
        p = _params(
            start_price=Decimal("1000"),
            target_price=Decimal("100"),
            max_pct=Decimal("10"),
            min_reduction=Decimal("5"),
        )
        result = calculate(p)
        for i in range(1, len(result.steps)):
            assert result.steps[i].start_amount == result.steps[i - 1].end_amount
