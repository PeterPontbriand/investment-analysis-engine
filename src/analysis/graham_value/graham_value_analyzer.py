"""Module for evaluating stock intrinsic value using the Benjamin Graham formula.

Implements the revised Benjamin Graham intrinsic-value formula commonly
expressed as:

    V = (EPS × (8.5 + 2g) × 4.4) / Y

where:
    EPS = Trailing Twelve Months earnings per share
    g   = expected annual growth rate in percent (e.g. 5.0 means 5 %)
    Y   = current yield on AAA corporate bonds (percent)
    8.5 = base P/E for a zero-growth company
    2   = growth multiplier (sometimes 1.5 is used)
    4.4 = historical benchmark AAA bond yield

This implementation exposes the numeric constants as configurable parameters
while preserving the classic defaults.  See Benjamin Graham, *The Intelligent
Investor* (revised editions) and subsequent restatements of the formula.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from pydantic import BaseModel, Field, field_validator, model_validator

from src.analysis.base_analyzer import BaseAnalyzer
from src.analysis.graham_value.calculators import compute_graham_growth_value
from src.config import settings
from src.core.analysis_status import CalculationStatus
from src.core.constants import ConfigKeys
from src.data.base_client import BaseDataClient, DataFetchError
from src.data.yfinance import YFinanceClient
from src.utils.logger_util import setup_logger


@dataclass(frozen=True)
class GrahamValueMetrics:
    """Read-only container for finalized Benjamin Graham valuation metrics.

    `current_price` and `margin_of_safety_percent` are nullable: when no
    market price is available, both are reported explicitly as `None`
    rather than substituted with a sentinel value.
    """

    ticker: str
    eps: float
    expected_growth_rate: float
    current_aaa_yield: float
    base_pe: float
    growth_multiplier: float
    baseline_aaa_yield: float
    intrinsic_value: float
    current_price: float | None
    margin_of_safety_percent: float | None
    timestamp: datetime


class GrahamValueConfig(BaseModel):
    """Configuration parameters for the Benjamin Graham intrinsic value formula.

    Formula:
        V = (EPS * (base_pe + growth_multiplier * g) * baseline_aaa_yield)
            / current_aaa_yield

    All percentage fields (expected_growth_rate, current_aaa_yield,
    baseline_aaa_yield) are expressed in percent units — e.g. 5.0 means 5 %,
    not 0.05.
    """

    eps: float = Field(
        ...,
        description="Trailing Twelve Months (TTM) Earnings Per Share. "
        "Must be strictly positive for a meaningful valuation.",
    )
    expected_growth_rate: float = Field(
        ...,
        description="Expected annual growth rate in percent over the next 7-10 years (e.g. 5.0 for 5 %).",
    )
    current_aaa_yield: float = Field(
        ...,
        gt=0,
        description="Current yield on AAA corporate bonds in percent (e.g. 5.25 for 5.25 %).",
    )
    base_pe: float = Field(
        default_factory=lambda: settings.get_graham_value_analysis()[ConfigKeys.GRAHAM_VALUES][ConfigKeys.BASE_PE],
        gt=0,
        description="Base P/E ratio for a company with 0 % growth; must be positive.",
    )
    growth_multiplier: float = Field(
        default_factory=lambda: settings.get_graham_value_analysis()[ConfigKeys.GRAHAM_VALUES][
            ConfigKeys.GROWTH_MULTIPLIER
        ],
        ge=0,
        description="Multiplier for the growth rate (commonly 1.5 or 2.0); must be non-negative.",
    )
    baseline_aaa_yield: float = Field(
        default_factory=lambda: settings.get_graham_value_analysis()[ConfigKeys.GRAHAM_VALUES][
            ConfigKeys.BASELINE_AAA_YIELD
        ],
        gt=0,
        description="Historical benchmark AAA bond yield in percent.",
    )

    @field_validator(
        "eps",
        "expected_growth_rate",
        "current_aaa_yield",
        "base_pe",
        "growth_multiplier",
        "baseline_aaa_yield",
    )
    @classmethod
    def numeric_inputs_must_be_finite(cls, v: float) -> float:
        """Reject NaN/±inf inputs; they would propagate into undefined outputs."""
        if not math.isfinite(v):
            raise ValueError(f"All Graham numeric inputs must be finite (received {v!r}).")
        return v

    @field_validator("eps")
    @classmethod
    def eps_must_be_positive(cls, v: float) -> float:
        """Reject non-positive EPS; Graham's formula is undefined or misleading.

        Zero or negative earnings produce nonsensical intrinsic values.
        """
        if v <= 0:
            raise ValueError(
                "EPS must be strictly positive for Graham valuation "
                f"(received {v}). Negative or zero earnings produce "
                "nonsensical intrinsic values."
            )
        return v

    @model_validator(mode="after")
    def valuation_pe_must_be_positive(self) -> "GrahamValueConfig":
        """Reject configurations where the valuation P/E term is not positive.

        A non-positive valuation P/E collapses the intrinsic value to zero
        or below, which the formula domain explicitly forbids. No cap is
        placed on the growth rate itself; only the resulting P/E term is
        validated.
        """
        valuation_pe = self.base_pe + self.growth_multiplier * self.expected_growth_rate
        if valuation_pe <= 0:
            raise ValueError(
                "base_pe + growth_multiplier * expected_growth_rate must be "
                f"positive (received P/E term {valuation_pe})."
            )
        return self


class GrahamValueAnalyzer(BaseAnalyzer[GrahamValueConfig]):
    """Calculates intrinsic valuation based on the revised Benjamin Graham Formula."""

    config_schema = GrahamValueConfig

    def __init__(self, default_ticker: str | None = None, data_client: BaseDataClient | None = None) -> None:
        """Initialize analyzer with default configuration and client dependencies."""
        super().__init__(default_ticker=default_ticker)
        analysis_settings = settings.get_analysis_settings()

        default_section = analysis_settings[ConfigKeys.DEFAULT_SECTION]
        self._fallback_ticker: Final[str] = default_ticker or default_section[ConfigKeys.TICKER]

        # Decoupled Dependency Injection
        self.data_client: Final[BaseDataClient] = data_client or YFinanceClient()

    def run_analysis(
        self,
        config: GrahamValueConfig,
        ticker: str | None = None,
        current_price: float | None = None,
    ) -> GrahamValueMetrics:
        """Execute Graham Valuation calculation using the configured model metrics.

        If `current_price` is omitted, the latest quote is resolved through
        the injected `BaseDataClient` quote capability.  A `DataFetchError`
        during the quote lookup (quote unavailable) is logged at WARNING level
        and results in `current_price=None` and `margin_of_safety_percent=None`
        — the intrinsic-value calculation is unaffected.  Any other unexpected
        data-client exception is propagated to the caller.

        Args:
            config: Validated Graham formula inputs.
            ticker: Optional ticker override; falls back to the configured default.
            current_price: Optional explicit positive, finite price for the margin of safety.

        Returns:
            GrahamValueMetrics: Finalized valuation metrics.

        Raises:
            ValueError: If an explicitly supplied `current_price` is not finite and
                positive, or if the computed intrinsic value / margin of safety is
                not finite.
        """
        target_ticker: str = ticker or self._fallback_ticker

        if current_price is not None and (not math.isfinite(current_price) or current_price <= 0):
            raise ValueError(f"Explicit current_price must be finite and positive (received {current_price!r}).")

        with setup_logger(__name__) as logger:
            logger.debug(f"Executing Graham Valuation analysis for {target_ticker}")

            # Core Benjamin Graham intrinsic value calculation — delegated
            # to the pure calculator for a single source of truth.
            calc_result = compute_graham_growth_value(
                normalized_eps=config.eps,
                expected_growth_rate=config.expected_growth_rate,
                current_aaa_yield=config.current_aaa_yield,
                base_pe=config.base_pe,
                growth_multiplier=config.growth_multiplier,
                baseline_aaa_yield=config.baseline_aaa_yield,
            )

            # Preserve the analyzer's existing error contract:
            # non-finite / non-positive computed values raise ValueError.
            if calc_result.status is not CalculationStatus.OK:
                raise ValueError(f"Computed Graham intrinsic value must be finite and positive: {calc_result.reason}")
            intrinsic_value = calc_result.growth_value
            if intrinsic_value is None:
                raise ValueError(f"Computed Graham intrinsic value must be finite and positive: {calc_result.reason}")

            # Final safety net: config layer should prevent this, but reject
            # a non-positive value so an undefined valuation is never exposed.
            if intrinsic_value <= 0:
                raise ValueError(
                    f"Computed Graham intrinsic value must be finite and positive (received {intrinsic_value!r})."
                )

            # Resolve the market price through the quote boundary when one was
            # not explicitly supplied.  Only the contract's DataFetchError
            # (quote unavailable) is degraded; unexpected client failures
            # propagate to the caller.
            if current_price is None:
                try:
                    current_price = self.data_client.fetch_current_price(target_ticker)
                except DataFetchError as exc:
                    logger.warning(
                        "Unable to obtain current quote for %s (%s: %s); margin of safety set to None",
                        target_ticker,
                        type(exc).__name__,
                        exc,
                    )
                    current_price = None

            # Calculate Margin of Safety: (V - price) / V * 100.  Kept
            # explicitly None when no price is available (never a zero).
            margin_of_safety_pct: float | None = None
            if current_price is not None:
                margin_of_safety_pct = ((intrinsic_value - current_price) / intrinsic_value) * 100.0
                if not math.isfinite(margin_of_safety_pct):
                    raise ValueError(
                        "Computed margin of safety must be finite "
                        f"(received {margin_of_safety_pct!r}) for intrinsic_value={intrinsic_value!r}, "
                        f"current_price={current_price!r}"
                    )

            logger.info(f"Graham valuation for {target_ticker}: IV=${intrinsic_value:,.2f}")

        return GrahamValueMetrics(
            ticker=target_ticker,
            eps=config.eps,
            expected_growth_rate=config.expected_growth_rate,
            current_aaa_yield=config.current_aaa_yield,
            base_pe=config.base_pe,
            growth_multiplier=config.growth_multiplier,
            baseline_aaa_yield=config.baseline_aaa_yield,
            intrinsic_value=intrinsic_value,
            current_price=current_price,
            margin_of_safety_percent=margin_of_safety_pct,
            timestamp=datetime.now(UTC),
        )


if __name__ == "__main__":
    analyzer = GrahamValueAnalyzer()
    try:
        # Example configuration execution using sample metrics
        sample_config = GrahamValueConfig(
            eps=3.50,
            expected_growth_rate=6.5,  # 6.5 % growth
            current_aaa_yield=5.25,  # 5.25 % AAA yield
        )
        metrics = analyzer.run_analysis(config=sample_config, current_price=48.00)

        with setup_logger(__name__) as main_logger:
            main_logger.info(f"Local Valuation Execution Successful for {metrics.ticker}")
            main_logger.info(f"EPS: ${metrics.eps:.2f}")
            main_logger.info(f"Intrinsic Value: ${metrics.intrinsic_value:,.2f}")
            if metrics.margin_of_safety_percent is not None:
                main_logger.info(f"Margin of Safety: {metrics.margin_of_safety_percent:.2f}%")
            else:
                main_logger.info("Margin of Safety: unavailable (no current quote)")
    except Exception as exc:
        with setup_logger(__name__) as main_logger:
            main_logger.critical(f"Self-test harness faulted: {exc}", exc_info=True)
