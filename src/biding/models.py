# models.py — Plain data classes (no logic) for the Quoting Calculator.
#
# Responsibility: define the typed, immutable snapshot structures that flow
# through the pipeline: CLI input → CalculationParams, algorithm output →
# CalculationResult (containing a tuple of QuoteStep), and the custom
# exception InfeasibleError.
#
# No module-level side effects. Nothing here imports argparse or openpyxl.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path


class InfeasibleError(ValueError):
    """Raised by calculator.calculate when no valid quoting sequence exists.

    Subclasses ValueError so main.py can catch generic input errors uniformly.
    """


@dataclass(frozen=True, kw_only=True)
class CalculationParams:
    """Validated, immutable snapshot of the CLI arguments.

    All monetary values use Decimal to avoid binary-float drift.
    max_pct is stored in percent units (e.g. 5 means 5 %), not as a ratio.
    """

    start_price: Decimal    # must be > 0
    target_price: Decimal   # must be >= 0; 0 signals auto-compute
    max_pct: Decimal        # percent, must be in (0, 100)
    min_reduction: Decimal  # must be > 0
    decimals: int           # must be >= 0
    rounding: bool          # True → ROUND_HALF_UP, False → ROUND_DOWN (truncate)
    output_path: Path       # destination xlsx file

    def __post_init__(self) -> None:
        """Validate field invariants; raise ValueError with a clear message on failure."""
        if self.start_price <= 0:
            raise ValueError("start-price must be > 0")
        if self.target_price < 0:
            raise ValueError("target-price must be >= 0")
        if not (0 < self.max_pct < 100):
            raise ValueError("max-pct must be in (0, 100)")
        if self.min_reduction <= 0:
            raise ValueError("min-reduction must be > 0")
        if self.decimals < 0:
            raise ValueError("decimals must be >= 0")
        # target_price == 0 means auto-compute; otherwise it must be strictly < start_price
        if self.target_price != 0 and self.target_price >= self.start_price:
            raise ValueError(
                "target-price must be < start-price (or 0 to auto-compute)"
            )


@dataclass(frozen=True, kw_only=True)
class QuoteStep:
    """One row in the Quoting Sequence output table.

    Fields mirror the PRD §11 column order:
      Round | Start Amount | End Amount | Reduction Amount | Reduction Pct
    """

    round_no: int              # 1-based round number
    start_amount: Decimal      # price before this round's reduction
    end_amount: Decimal        # price after this round's reduction
    reduction_amount: Decimal  # = start_amount - end_amount
    reduction_pct: Decimal     # = reduction_amount / start_amount * 100


@dataclass(frozen=True, kw_only=True)
class CalculationResult:
    """Output of calculator.calculate — the full result for one run.

    params             — snapshot of validated CLI input
    calculation_time   — datetime.now() captured at the start of calculate()
    effective_target   — the actual target used (params.target_price or auto-computed)
    steps              — tuple of QuoteStep, non-empty when start != target
    """

    params: CalculationParams
    calculation_time: datetime
    effective_target: Decimal
    steps: tuple[QuoteStep, ...]
