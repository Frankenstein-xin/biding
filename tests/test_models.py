# test_models.py — Unit tests for biding.models data classes.

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from biding.models import (
    CalculationParams,
    CalculationResult,
    InfeasibleError,
    QuoteStep,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_params(**overrides) -> CalculationParams:
    """Return a CalculationParams with sensible defaults, optionally overridden."""
    defaults = dict(
        start_price=Decimal("100"),
        target_price=Decimal("45"),
        max_pct=Decimal("50"),
        min_reduction=Decimal("10"),
        decimals=2,
        rounding=True,
        output_path=Path("/tmp/out.xlsx"),
    )
    defaults.update(overrides)
    return CalculationParams(**defaults)


# ---------------------------------------------------------------------------
# CalculationParams — valid construction
# ---------------------------------------------------------------------------

class TestCalculationParamsValid:
    def test_basic_construction(self):
        p = _valid_params()
        assert p.start_price == Decimal("100")
        assert p.target_price == Decimal("45")

    def test_auto_target_zero_allowed(self):
        # target_price == 0 is the auto-compute sentinel; must not raise
        p = _valid_params(target_price=Decimal("0"))
        assert p.target_price == Decimal("0")

    def test_frozen_immutable(self):
        p = _valid_params()
        with pytest.raises((AttributeError, TypeError)):
            p.start_price = Decimal("999")  # type: ignore[misc]

    def test_hashable(self):
        p1 = _valid_params()
        p2 = _valid_params()
        assert p1 == p2
        assert hash(p1) == hash(p2)


# ---------------------------------------------------------------------------
# CalculationParams — validation errors
# ---------------------------------------------------------------------------

class TestCalculationParamsValidation:
    def test_start_price_zero(self):
        with pytest.raises(ValueError, match="start-price must be > 0"):
            _valid_params(start_price=Decimal("0"))

    def test_start_price_negative(self):
        with pytest.raises(ValueError, match="start-price must be > 0"):
            _valid_params(start_price=Decimal("-1"))

    def test_target_price_negative(self):
        with pytest.raises(ValueError, match="target-price must be >= 0"):
            _valid_params(target_price=Decimal("-1"))

    def test_max_pct_zero(self):
        with pytest.raises(ValueError, match="max-pct must be in"):
            _valid_params(max_pct=Decimal("0"))

    def test_max_pct_hundred(self):
        with pytest.raises(ValueError, match="max-pct must be in"):
            _valid_params(max_pct=Decimal("100"))

    def test_max_pct_above_hundred(self):
        with pytest.raises(ValueError, match="max-pct must be in"):
            _valid_params(max_pct=Decimal("101"))

    def test_min_reduction_zero(self):
        with pytest.raises(ValueError, match="min-reduction must be > 0"):
            _valid_params(min_reduction=Decimal("0"))

    def test_min_reduction_negative(self):
        with pytest.raises(ValueError, match="min-reduction must be > 0"):
            _valid_params(min_reduction=Decimal("-5"))

    def test_decimals_negative(self):
        with pytest.raises(ValueError, match="decimals must be >= 0"):
            _valid_params(decimals=-1)

    def test_target_equals_start(self):
        with pytest.raises(ValueError, match="target-price must be < start-price"):
            _valid_params(start_price=Decimal("100"), target_price=Decimal("100"))

    def test_target_greater_than_start(self):
        with pytest.raises(ValueError, match="target-price must be < start-price"):
            _valid_params(start_price=Decimal("100"), target_price=Decimal("200"))


# ---------------------------------------------------------------------------
# QuoteStep
# ---------------------------------------------------------------------------

class TestQuoteStep:
    def test_basic_construction(self):
        step = QuoteStep(
            round_no=1,
            start_amount=Decimal("100.00"),
            end_amount=Decimal("55.00"),
            reduction_amount=Decimal("45.00"),
            reduction_pct=Decimal("45.00"),
        )
        assert step.round_no == 1
        assert step.reduction_amount == Decimal("45.00")

    def test_frozen(self):
        step = QuoteStep(
            round_no=1,
            start_amount=Decimal("100"),
            end_amount=Decimal("55"),
            reduction_amount=Decimal("45"),
            reduction_pct=Decimal("45"),
        )
        with pytest.raises((AttributeError, TypeError)):
            step.round_no = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CalculationResult
# ---------------------------------------------------------------------------

class TestCalculationResult:
    def test_basic_construction(self):
        params = _valid_params()
        step = QuoteStep(
            round_no=1,
            start_amount=Decimal("100.00"),
            end_amount=Decimal("45.00"),
            reduction_amount=Decimal("55.00"),
            reduction_pct=Decimal("55.00"),
        )
        result = CalculationResult(
            params=params,
            calculation_time=datetime(2026, 4, 19, 10, 30, 0),
            effective_target=Decimal("45.00"),
            steps=(step,),
        )
        assert len(result.steps) == 1
        assert result.effective_target == Decimal("45.00")


# ---------------------------------------------------------------------------
# InfeasibleError
# ---------------------------------------------------------------------------

class TestInfeasibleError:
    def test_is_value_error(self):
        err = InfeasibleError("test message")
        assert isinstance(err, ValueError)

    def test_message(self):
        err = InfeasibleError("no solution")
        assert str(err) == "no solution"
