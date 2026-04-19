"""Typed data models for the quoting calculator.

These classes carry the validated user input (``CalculationParams``)
through the pipeline, describe a single round of quoting (``QuoteStep``)
and the full run output (``CalculationResult``).  The ``InfeasibleError``
custom exception signals that the constraints make the target
unreachable.

All classes are frozen dataclasses with keyword-only fields; no module-
level side effects or I/O live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path


class InfeasibleError(ValueError):
    """Raised when the constraints make reaching the target impossible.

    Subclasses ValueError so CLI-level handlers can treat it as a
    user-input problem.
    """


@dataclass(frozen=True, kw_only=True)
class CalculationParams:
    """Immutable, validated snapshot of the CLI inputs."""

    start_price: Decimal
    target_price: Decimal  # 0 means "auto-compute from max_pct + min_reduction"
    max_pct: Decimal  # percentage units, e.g. Decimal("5") == 5 %
    min_reduction: Decimal
    decimals: int
    rounding: bool
    output_path: Path

    def __post_init__(self) -> None:
        # --- Individual field checks. --------------------------------------
        if self.start_price <= 0:
            raise ValueError("start-price must be > 0")
        if self.target_price < 0:
            raise ValueError("target-price must be >= 0")
        if not (Decimal("0") < self.max_pct < Decimal("100")):
            raise ValueError("max-pct must be in (0, 100)")
        if self.min_reduction <= 0:
            raise ValueError("min-reduction must be > 0")
        if self.decimals < 0:
            raise ValueError("decimals must be >= 0")

        # --- Cross-field check. --------------------------------------------
        # target_price == 0 is the auto-compute sentinel and is allowed even
        # though it is not strictly less than start_price.
        if self.target_price != 0 and self.target_price >= self.start_price:
            raise ValueError(
                "target-price must be < start-price (or 0 to auto-compute)"
            )


@dataclass(frozen=True, kw_only=True)
class QuoteStep:
    """One row in the emitted quoting sequence.

    ``reduction_pct`` is stored in percent units (e.g. Decimal("18.18"))
    so it can be rendered directly as "18.18 %" without further math.
    """

    round_no: int
    start_amount: Decimal
    end_amount: Decimal
    reduction_amount: Decimal
    reduction_pct: Decimal


@dataclass(frozen=True, kw_only=True)
class CalculationResult:
    """Output of :func:`biding.calculator.calculate`.

    Holds a snapshot of the validated params, the wall-clock time the
    calculation started (used for sheet naming and the Overview block),
    the effective target (either user-supplied or auto-computed), and
    the ordered tuple of quoting steps.
    """

    params: CalculationParams
    calculation_time: datetime
    effective_target: Decimal
    steps: tuple[QuoteStep, ...] = field(default_factory=tuple)
