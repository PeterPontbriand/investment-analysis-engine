"""Deterministic annual financial-fact fixture for C2 resolver tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)

PROVIDER_ID = "annual-fixture"
RETRIEVED_AT = datetime(2026, 2, 1, tzinfo=UTC)


class FixtureAnnualFinancialFactsProvider:
    """Return configured annual facts while recording deterministic calls."""

    def __init__(
        self,
        facts: tuple[ProviderFact, ...],
        *,
        error_field: FinancialField | None = None,
    ) -> None:
        """Initialize with immutable facts and an optional failing field."""
        self.facts = facts
        self.error_field = error_field
        self.requests: list[FinancialFactRequest] = []

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Return matching configured facts or raise the configured error."""
        self.requests.append(request)
        if request.field_name is self.error_field:
            raise FinancialProviderError("fixture provider failure")
        return tuple(
            fact
            for fact in self.facts
            if fact.field_name is request.field_name
            and fact.subject_id == request.subject_id
            and fact.provider_id == request.provider_id
        )


def annual_fact(  # noqa: PLR0913, PLR0917
    field: FinancialField,
    fiscal_year: int,
    value: float,
    *,
    available_at: datetime | None = None,
    provider_fact_id: str | None = None,
    currency: str = "USD",
    accounting_scope: AccountingScope | None = AccountingScope.CONSOLIDATED,
    period_kind: PeriodKind | None = PeriodKind.COMPLETED_ANNUAL,
    capex_sign: CapitalExpenditureSign | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> ProviderFact:
    """Build one completed annual fixture fact with exact-touching periods."""
    start = period_start or datetime(fiscal_year - 1, 1, 1, tzinfo=UTC)
    end = period_end or datetime(fiscal_year, 1, 1, tzinfo=UTC)
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ACME",
        field_name=field,
        value=value,
        units=(
            FinancialUnit.CURRENCY_PER_SHARE
            if field is FinancialField.EPS
            else FinancialUnit.SHARES
            if field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES
            else FinancialUnit.CURRENCY
        ),
        provider_id=PROVIDER_ID,
        provider_field=f"fixture.{field.value}",
        retrieved_at=RETRIEVED_AT,
        basis="fiscal_year",
        currency=None if field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES else currency,
        observation_period_start=start,
        observation_period_end=end,
        available_at=available_at or datetime(fiscal_year, 2, 1, tzinfo=UTC),
        fiscal_year=fiscal_year,
        period_kind=period_kind,
        accounting_scope=accounting_scope,
        capital_expenditure_sign=capex_sign,
        provider_fact_id=provider_fact_id or f"{field.value}-{fiscal_year}",
    )


def annual_series(
    years: range,
    *,
    fcf_values: tuple[float, ...] | None = None,
) -> tuple[ProviderFact, ...]:
    """Build compatible annual FCF, diluted-share, and diluted-EPS facts."""
    facts: list[ProviderFact] = []
    selected_years = tuple(years)
    for index, year in enumerate(selected_years):
        desired_fcf = fcf_values[index] if fcf_values is not None else 80.0 + index * 10.0
        capex = 20.0
        facts.extend(
            (
                annual_fact(FinancialField.OPERATING_CASH_FLOW, year, desired_fcf + capex),
                annual_fact(
                    FinancialField.CAPITAL_EXPENDITURES,
                    year,
                    capex,
                    capex_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE,
                ),
                annual_fact(FinancialField.EPS, year, 2.0 + index * 0.5),
                annual_fact(FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES, year, 100.0),
            )
        )
    return tuple(facts)
