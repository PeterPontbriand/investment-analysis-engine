"""FCF Growth over an NVDA-shaped issuer, read by the real SEC adapter, from Company Facts to the result."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthConfig, FCFEarningsGrowthPolicy
from investment_analysis_engine.strategies.fcf_growth.presenter import render_fcf_earnings_growth
from tests._fcf_market_data import CLOCK, fcf_market_data

_CIK = 1045810
_PERIODS = (
    ("2020-01-27", "2021-01-31"),
    ("2021-02-01", "2022-01-30"),
    ("2022-01-31", "2023-01-29"),
    ("2023-01-30", "2024-01-28"),
    ("2024-01-29", "2025-01-26"),
    ("2025-01-27", "2026-01-25"),
)
_FILINGS = {
    "21": ("0001045810-21-000010", "2021-02-26"),
    "22": ("0001045810-22-000036", "2022-03-18"),
    "23": ("0001045810-23-000017", "2023-02-24"),
    "24": ("0001045810-24-000029", "2024-02-21"),
    "25": ("0001045810-25-000023", "2025-02-26"),
    "26": ("0001045810-26-000021", "2026-02-25"),
}
# Period index -> the value each filing year reported for it.
_EPS = {
    0: {"21": 6.9, "22": 1.73, "23": 1.73},
    1: {"22": 3.85, "23": 3.85, "24": 3.85},
    2: {"23": 1.74, "24": 1.74, "25": 0.17},
    3: {"24": 11.93, "25": 1.19, "26": 1.19},
    4: {"25": 2.94, "26": 2.94},
    5: {"26": 4.9},
}
_SHARES = {
    0: {"21": 628e6, "22": 2510e6, "23": 2510e6},
    1: {"22": 2535e6, "23": 2535e6, "24": 2535e6},
    2: {"23": 2507e6, "24": 2507e6, "25": 25070e6},
    3: {"24": 2494e6, "25": 24940e6, "26": 24940e6},
    4: {"25": 24804e6, "26": 24804e6},
    5: {"26": 24514e6},
}
# Operating cash flow was never restated; the capex values are the issuer's, tagged only as productive assets.
_OPERATING_CASH_FLOW = {0: 4.7e9, 1: 5.8e9, 2: 5.6e9, 3: 28.1e9, 4: 64.1e9, 5: 102.7e9}
_PRODUCTIVE_ASSETS = {1: 976e6, 2: 1833e6, 3: 1069e6, 4: 3236e6, 5: 6042e6}
_PPE_2010_TO_2012 = (
    ("2009-01-26", "2010-01-31", 77_601_000.0, "0001045810-12-000013", "2012-03-13"),
    ("2010-02-01", "2011-01-30", 97_890_000.0, "0001045810-12-000013", "2012-03-13"),
    ("2011-01-31", "2012-01-29", 138_735_000.0, "0001045810-12-000013", "2012-03-13"),
)


def _row(value: float, start: str, end: str, accession: str, filed: str) -> dict[str, Any]:
    return {
        "val": value,
        "start": start,
        "end": end,
        "accn": accession,
        "filed": filed,
        "fy": int(end[:4]),
        "fp": "FY",
        "form": "10-K",
    }


def _versions(series: Mapping[int, Mapping[str, float]]) -> list[dict[str, Any]]:
    return [
        _row(value, *_PERIODS[index], *_FILINGS[year])
        for index, by_year in series.items()
        for year, value in by_year.items()
    ]


def _company_facts() -> dict[str, Any]:
    latest = {index: {"26": value} for index, value in _OPERATING_CASH_FLOW.items()}
    productive = {index: {"26": value} for index, value in _PRODUCTIVE_ASSETS.items()}
    return {
        "cik": _CIK,
        "entityName": "NVIDIA",
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": _versions(latest)}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            _row(value, start, end, acc, filed) for start, end, value, acc, filed in _PPE_2010_TO_2012
                        ]
                    }
                },
                "PaymentsToAcquireProductiveAssets": {"units": {"USD": _versions(productive)}},
                "EarningsPerShareDiluted": {"units": {"USD/shares": _versions(_EPS)}},
                "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": _versions(_SHARES)}},
            }
        },
    }


class _Fetcher:
    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG002
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> object:
        if "company_tickers.json" in url:
            return {"0": {"cik_str": _CIK, "ticker": "NVDA", "title": "NVIDIA"}}
        if "/companyfacts/" in url:
            return _company_facts()
        if "/submissions/" in url:
            filings = [*_FILINGS.values(), ("0001045810-12-000013", "2012-03-13")]
            return {
                "filings": {
                    "recent": {
                        "accessionNumber": [accession for accession, _ in filings],
                        "acceptanceDateTime": [f"{filed}T12:00:00Z" for _, filed in filings],
                        "form": ["10-K" for _ in filings],
                    }
                }
            }
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _run() -> Any:
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=_Fetcher(),
        clock=lambda: datetime(2026, 8, 29, 16, 0, tzinfo=UTC),
        user_agent="end-to-end fixture tests@example.invalid",
    )
    annual = ProductionAnnualGrowthSeriesResolver(
        ProductionFinancialFactsProvider(sec_edgar=adapter), clock=lambda: CLOCK
    )
    return FCFEarningsGrowthAnalyzer(annual, fcf_market_data()).run_analysis(
        "nvda",
        AnalysisContext(as_of=None, executed_at=CLOCK, use_cache=False),
        FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
    )


_EARLIER = (
    "Diluted EPS and weighted-average diluted shares for FY2021–FY2022 were reported only before a later filing "
    "restated other years (for example after a stock split); those years are left out."
)
_FALLBACK = "Automatic horizon selection fell back because five elapsed years were unavailable."
_LIMITATION = (
    "Capital expenditures include purchases of intangible assets, which the filer reports together with property "
    "and equipment, so free cash flow may be lower than with property and equipment alone."
)


def test_nvda_reaches_a_three_year_horizon_over_fy2023_to_fy2026() -> None:
    result = _run()

    assert result.execution_status is CalculationStatus.OK
    assert (result.selected_horizon_years, result.used_horizon_fallback) == (3, True)
    assert [item.period_end.year for item in result.annual_observations] == [2023, 2024, 2025, 2026]
    assert (result.period_start.date(), result.period_end.date()) == (date(2022, 1, 31), date(2026, 1, 25))
    assert {item.normalized_capital_expenditures.provider_field for item in result.annual_observations} == {
        "us-gaap:PaymentsToAcquireProductiveAssets"
    }
    assert [(item.field, item.fiscal_year) for item in result.left_out_years] == [
        ("eps", 2021),
        ("eps", 2022),
        ("weighted_average_diluted_shares", 2021),
        ("weighted_average_diluted_shares", 2022),
    ]


def test_nvda_text_shows_the_earlier_basis_warning_then_the_fallback_then_the_capex_limitation() -> None:
    lines = render_fcf_earnings_growth(_run(), PresentationMode.CONCISE).splitlines()

    wanted = [f"Warning: {_EARLIER}", f"Warning: {_FALLBACK}", f"Limitation: {_LIMITATION}"]
    positions = [lines.index(line) for line in wanted]
    assert positions == sorted(positions)
    assert lines[-1] == f"Limitation: {_LIMITATION}"
