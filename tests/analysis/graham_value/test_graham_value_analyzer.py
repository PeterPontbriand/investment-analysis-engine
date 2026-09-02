"""Unit tests for the Benjamin Graham valuation analyzer and config model.

All external market-data access is replaced by the deterministic
``FixtureDataClient`` — no real API calls are made.
"""

from datetime import timedelta

import pandas as pd
import pytest
from pydantic import ValidationError

from src.analysis.graham_value.graham_value_analyzer import (
    GrahamValueAnalyzer,
    GrahamValueConfig,
)
from src.config import settings
from src.core.constants import ConfigKeys
from src.data.base_client import BaseDataClient
from src.evaluation.fixtures.market_data import FixtureDataClient


class _UnexpectedErrorQuoteClient(BaseDataClient):
    """Data-client test double whose quote lookup fails with an unexpected exception."""

    def fetch_data(self, ticker: str, start_date: str, _end_date: str | None = None) -> pd.DataFrame:
        raise NotImplementedError(f"Historical data is not required by these tests ({ticker}, {start_date}).")

    def fetch_current_price(self, ticker: str) -> float:
        raise RuntimeError(f"unexpected provider fault for {ticker}")


FIXED_CONFIG_KWARGS = {
    "eps": 3.50,
    "expected_growth_rate": 6.5,
    "current_aaa_yield": 5.25,
}


def _pe_parameters() -> tuple[float, float, float]:
    """Resolve the TOML-driven (base_pe, growth_multiplier, baseline_aaa_yield)."""
    cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
    return cfg.base_pe, cfg.growth_multiplier, cfg.baseline_aaa_yield


class TestGrahamValueConfigDefaults:
    """Verify classic defaults are loaded from the TOML configuration."""

    def test_classic_defaults_from_toml(self) -> None:
        base_pe, growth_multiplier, baseline_yield = _pe_parameters()
        assert base_pe == pytest.approx(8.5)
        assert growth_multiplier == pytest.approx(2.0)
        assert baseline_yield == pytest.approx(4.4)

    def test_non_positive_eps_rejected(self) -> None:
        with pytest.raises(ValidationError, match="EPS"):
            GrahamValueConfig(eps=0.0, expected_growth_rate=5.0, current_aaa_yield=5.0)

    def test_negative_eps_rejected(self) -> None:
        with pytest.raises(ValidationError, match="EPS"):
            GrahamValueConfig(eps=-1.0, expected_growth_rate=5.0, current_aaa_yield=5.0)

    def test_zero_aaa_yield_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GrahamValueConfig(eps=3.5, expected_growth_rate=5.0, current_aaa_yield=0.0)


class TestGrahamValueConfigGrowthHandling:
    """Growth-rate handling: no upper cap; non-positive P/E term rejected."""

    def test_no_upper_cap_on_growth_rate(self) -> None:
        # Previously rejected by a hardcoded |g| > 100 cutoff; must now be
        # accepted because the resulting valuation P/E is positive.
        cfg = GrahamValueConfig(eps=3.5, expected_growth_rate=1500.0, current_aaa_yield=5.25)
        base_pe, growth_multiplier, _ = _pe_parameters()
        assert base_pe + growth_multiplier * cfg.expected_growth_rate == pytest.approx(
            base_pe + growth_multiplier * 1500.0
        )

    def test_negative_growth_collapse_rejected(self) -> None:
        # 8.5 + 2 * (-10) = -11.5 → non-positive valuation P/E.
        with pytest.raises(ValidationError, match="positive"):
            GrahamValueConfig(eps=3.5, expected_growth_rate=-10.0, current_aaa_yield=5.25)

    def test_negative_growth_within_band_allowed(self) -> None:
        # 8.5 + 2 * (-3) = 2.5 → still positive, so it must be accepted.
        cfg = GrahamValueConfig(eps=3.5, expected_growth_rate=-3.0, current_aaa_yield=5.25)
        assert cfg.base_pe + cfg.growth_multiplier * cfg.expected_growth_rate > 0


class TestGrahamValuationComputation:
    """Core formula and margin-of-safety computation."""

    def test_intrinsic_value_formula(self) -> None:
        base_pe, growth_multiplier, baseline_yield = _pe_parameters()
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        expected = (
            cfg.eps * (base_pe + growth_multiplier * cfg.expected_growth_rate) * baseline_yield
        ) / cfg.current_aaa_yield

        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=50.0)

        assert metrics.intrinsic_value == pytest.approx(expected)
        assert metrics.ticker == "TEST"

    def test_margin_of_safety_with_explicit_price(self) -> None:
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=50.0)

        intrinsic = metrics.intrinsic_value
        assert metrics.current_price == pytest.approx(50.0)
        assert metrics.margin_of_safety_percent == pytest.approx((intrinsic - 50.0) / intrinsic * 100.0)

    def test_margin_of_safety_resolved_from_client_quote(self) -> None:
        client = FixtureDataClient()
        quote = client.fetch_current_price("TEST")

        analyzer = GrahamValueAnalyzer(default_ticker="TEST", data_client=client)
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        metrics = analyzer.run_analysis(config=cfg)

        intrinsic = metrics.intrinsic_value
        assert metrics.current_price == pytest.approx(quote)
        assert metrics.margin_of_safety_percent == pytest.approx((intrinsic - quote) / intrinsic * 100.0)

    def test_quote_failure_yields_none_price_and_margin(self) -> None:
        analyzer = GrahamValueAnalyzer(default_ticker="FAIL", data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        metrics = analyzer.run_analysis(config=cfg)

        # Intrinsic value is unaffected; price-related fields are None, not zero.
        assert metrics.intrinsic_value > 0
        assert metrics.current_price is None
        assert metrics.margin_of_safety_percent is None

    def test_zero_margin_of_safety(self) -> None:
        # A price exactly at intrinsic value is a legitimate 0.0 margin of
        # safety — explicitly distinct from the None reported when no
        # quote is available.
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        base_pe, growth_multiplier, baseline_yield = _pe_parameters()
        expected_iv = (
            cfg.eps * (base_pe + growth_multiplier * cfg.expected_growth_rate) * baseline_yield
        ) / cfg.current_aaa_yield
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=expected_iv)
        assert metrics.intrinsic_value == pytest.approx(expected_iv)
        assert metrics.current_price == pytest.approx(expected_iv)
        assert metrics.margin_of_safety_percent == 0.0


class TestGrahamValuationConfigurableConstants:
    """Configurable valuation constants must flow through to the valuation."""

    def test_configurable_constants(self) -> None:
        cfg = GrahamValueConfig(
            eps=3.50,
            expected_growth_rate=5.0,
            current_aaa_yield=5.25,
            base_pe=10.0,
            growth_multiplier=3.0,
            baseline_aaa_yield=6.0,
        )
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=2.00)

        assert metrics.base_pe == pytest.approx(10.0)
        assert metrics.growth_multiplier == pytest.approx(3.0)
        assert metrics.baseline_aaa_yield == pytest.approx(6.0)
        # (3.50 * (10.0 + 3.0 * 5.0) * 6.0) / 5.25 = 100.0
        assert metrics.intrinsic_value == pytest.approx(100.0)
        # (100.0 - 2.00) / 100.0 * 100 = 98.0
        assert metrics.margin_of_safety_percent == pytest.approx(98.0)

    def test_zero_growth_multiplier_is_accepted(self) -> None:
        # ge=0 boundary: no growth contribution collapses the valuation to
        # the zero-growth benchmark P/E and must remain finite and positive.
        cfg = GrahamValueConfig(eps=3.50, expected_growth_rate=6.5, current_aaa_yield=5.25, growth_multiplier=0.0)
        base_pe, _, baseline_yield = _pe_parameters()
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=5.00)
        expected_iv = (cfg.eps * base_pe * baseline_yield) / cfg.current_aaa_yield
        assert metrics.intrinsic_value == pytest.approx(expected_iv)


class TestGrahamValueConfigConstantConstraints:
    """Valuation constants outside their meaningful ranges must be rejected."""

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("base_pe", 0.0),
            ("base_pe", -1.0),
            ("growth_multiplier", -0.5),
            ("baseline_aaa_yield", 0.0),
            ("baseline_aaa_yield", -4.4),
        ],
    )
    def test_invalid_constants(self, field: str, value: float) -> None:
        with pytest.raises(ValidationError):
            GrahamValueConfig(**{**FIXED_CONFIG_KWARGS, field: value})


class TestGrahamValuationEdgeCases:
    """Edge-case guard rails around explicit inputs."""

    def test_explicit_non_positive_price_rejected(self) -> None:
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        with pytest.raises(ValueError, match="current_price"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=0.0)

    def test_explicit_negative_price_rejected(self) -> None:
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        with pytest.raises(ValueError, match="current_price"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=-12.5)

    def test_overvalued_price_produces_negative_margin(self) -> None:
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        # Price far above intrinsic value → negative margin of safety.
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=10_000.0)
        assert metrics.margin_of_safety_percent is not None
        assert metrics.margin_of_safety_percent < 0

    def test_explicit_nan_price_rejected(self) -> None:
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        with pytest.raises(ValueError, match="current_price"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=float("nan"))

    def test_explicit_inf_price_rejected(self) -> None:
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        with pytest.raises(ValueError, match="current_price"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=float("inf"))


class TestGrahamValuationErrorPropagation:
    """Only DataFetchError degrades gracefully; unexpected faults propagate."""

    def test_unexpected_quote_client_error_propagates(self) -> None:
        analyzer = GrahamValueAnalyzer(default_ticker="BOOM", data_client=_UnexpectedErrorQuoteClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        with pytest.raises(RuntimeError, match="unexpected provider fault"):
            analyzer.run_analysis(config=cfg)

    def test_data_fetch_error_still_degrades_to_none_price(self) -> None:
        analyzer = GrahamValueAnalyzer(default_ticker="FAIL", data_client=FixtureDataClient())
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        metrics = analyzer.run_analysis(config=cfg)
        assert metrics.intrinsic_value > 0
        assert metrics.current_price is None
        assert metrics.margin_of_safety_percent is None


class TestGrahamValuationFiniteInputs:
    """NaN/±inf numeric inputs must be rejected at the configuration boundary."""

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("eps", float("nan")),
            ("eps", float("inf")),
            ("eps", float("-inf")),
            ("expected_growth_rate", float("nan")),
            ("expected_growth_rate", float("inf")),
            ("current_aaa_yield", float("nan")),
            ("current_aaa_yield", float("inf")),
            ("base_pe", float("nan")),
            ("base_pe", float("inf")),
            ("growth_multiplier", float("nan")),
            ("growth_multiplier", float("inf")),
            ("baseline_aaa_yield", float("nan")),
            ("baseline_aaa_yield", float("inf")),
        ],
    )
    def test_non_finite_numeric_inputs_rejected(self, field: str, value: float) -> None:
        kwargs = {**FIXED_CONFIG_KWARGS, field: value}
        # NaN may fail either the field constraint ("greater than") or the
        # explicit finiteness validator ("finite") depending on the field.
        with pytest.raises(ValidationError, match="finite|greater than"):
            GrahamValueConfig(**kwargs)


class TestGrahamValuationFiniteOutputs:
    """Non-finite computed results must raise instead of silently propagating."""

    def test_oversized_eps_infinite_intrinsic_value_rejected(self) -> None:
        cfg = GrahamValueConfig(eps=1e308, expected_growth_rate=6.5, current_aaa_yield=5.25)
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        with pytest.raises(ValueError, match="intrinsic value"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=50.0)

    def test_oversized_growth_rate_infinite_intrinsic_value_rejected(self) -> None:
        cfg = GrahamValueConfig(eps=3.5, expected_growth_rate=1e308, current_aaa_yield=5.25)
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        with pytest.raises(ValueError, match="intrinsic value"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=50.0)

    def test_non_finite_margin_of_safety_rejected(self) -> None:
        # Tiny IV (≈1.8e-299) vs huge price (1e308) → margin overflows to -inf.
        cfg = GrahamValueConfig(eps=1e-300, expected_growth_rate=6.5, current_aaa_yield=5.25)
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        with pytest.raises(ValueError, match="margin of safety"):
            analyzer.run_analysis(config=cfg, ticker="TEST", current_price=1e308)


class TestGrahamValuationMetadata:
    """Result metadata: UTC timestamp and ticker resolution semantics."""

    def test_utc_timestamp(self) -> None:
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        analyzer = GrahamValueAnalyzer(data_client=FixtureDataClient())
        metrics = analyzer.run_analysis(config=cfg, ticker="TEST", current_price=5.00)
        assert metrics.timestamp.tzinfo is not None
        assert metrics.timestamp.utcoffset() == timedelta(0)

    def test_ticker_behavior(self) -> None:
        cfg = GrahamValueConfig(**FIXED_CONFIG_KWARGS)
        # Explicit ticker wins and is preserved verbatim (no upper-casing).
        explicit = GrahamValueAnalyzer(default_ticker="DEFAULT", data_client=FixtureDataClient()).run_analysis(
            config=cfg, ticker="abc", current_price=5.00
        )
        assert explicit.ticker == "abc"
        # Omitted ticker falls back to the analyzer's default.
        fallback = GrahamValueAnalyzer(default_ticker="DEFAULT", data_client=FixtureDataClient()).run_analysis(
            config=cfg, current_price=5.00
        )
        assert fallback.ticker == "DEFAULT"
        # No default configured either → the settings-driven default ticker.
        default_section = settings.get_analysis_settings()[ConfigKeys.DEFAULT_SECTION]
        unconfigured = GrahamValueAnalyzer(data_client=FixtureDataClient()).run_analysis(config=cfg, current_price=5.00)
        assert unconfigured.ticker == default_section[ConfigKeys.TICKER]
