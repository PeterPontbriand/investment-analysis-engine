"""D5 integration regressions for the approved SEC annual-fact mapping."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from src.analysis.fcf_earnings_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.analysis.fcf_earnings_growth.models import FCFEarningsGrowthPolicy, ReasonCode
from src.core.analysis_status import CalculationStatus
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
CIK = 789019


class _SecFixtureFetcher:
    """Serve a complete bounded SEC payload without external calls."""

    def __init__(self, company_facts: object) -> None:
        self._company_facts = company_facts

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        """Return the fixture matching the requested SEC endpoint."""
        assert headers["User-Agent"] == "D5 integration tests@example.invalid"
        if "company_tickers.json" in url:
            return {"0": {"cik_str": CIK, "ticker": "MSFT", "title": "Microsoft Corporation"}}
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return {"filings": {"recent": {}}}
        msg = f"Unexpected SEC URL: {url}"
        raise AssertionError(msg)


def _annual_observations(values: tuple[float, ...], *, unit: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for offset, value in enumerate(values):
        start_year = 2019 + offset
        end_year = start_year
        observations.append(
            {
                "val": value,
                "start": date(start_year, 1, 1).isoformat(),
                "end": date(end_year, 12, 31).isoformat(),
                "accn": f"0000789019-{(end_year + 1) % 100:02d}-{offset:06d}",
                "filed": date(end_year + 1, 2, 1).isoformat(),
                # Deliberately unrelated to the period-end year: the adapter
                # must derive the project fiscal-year label from exact dates.
                "fy": 2099,
                "fp": "FY",
                "form": "10-K",
            }
        )
    assert unit in {"USD", "USD/shares"}
    return observations


def _company_facts(*, capex_concept: str = "PaymentsToAcquirePropertyPlantAndEquipment") -> dict[str, Any]:
    return {
        "cik": CIK,
        "entityName": "Microsoft Corporation",
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": _annual_observations((100, 110, 121, 133.1, 146.41, 161.051), unit="USD")}
                },
                capex_concept: {"units": {"USD": _annual_observations((20, 21, 22, 23, 24, 25), unit="USD")}},
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": _annual_observations(
                            (2, 2.2, 2.42, 2.662, 2.9282, 3.22102),
                            unit="USD/shares",
                        )
                    }
                },
            }
        },
    }


def _resolver(company_facts: object) -> ProductionAnnualGrowthSeriesResolver:
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=_SecFixtureFetcher(company_facts),
        clock=lambda: NOW,
        user_agent="D5 integration tests@example.invalid",
    )
    return ProductionAnnualGrowthSeriesResolver(
        ProductionFinancialFactsProvider(sec_edgar=adapter),
        clock=lambda: NOW,
    )


def test_real_sec_adapter_composes_a_complete_provenanced_series() -> None:
    result = _resolver(_company_facts()).resolve(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="msft",
        currency="USD",
        as_of=NOW,
    )

    assert result.status is CalculationStatus.OK, result.reason
    assert result.selected_horizon_years == 5
    assert [observation.fiscal_year for observation in result.observations] == list(range(2019, 2025))
    assert result.observations[0].free_cash_flow.value == 80.0
    assert all(
        component.provider_id == "sec_edgar"
        for observation in result.observations
        for component in (
            observation.operating_cash_flow,
            observation.normalized_capital_expenditures,
            observation.diluted_eps,
        )
    )


def test_unsupported_productive_assets_shape_remains_typed_unavailable() -> None:
    result = _resolver(_company_facts(capex_concept="PaymentsToAcquireProductiveAssets")).resolve(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="MSFT",
        currency="USD",
        as_of=NOW,
    )

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.MISSING_FACT
    assert result.reason == "No usable capital_expenditures facts were returned."
    assert result.observations == ()
