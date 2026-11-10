"""A Graham fixture provider whose anchor filing and facts a test sets, and the helpers that run both strategies on it.

The provider is the evaluation fixture's: the SYNTH issuer files its annual reports in September (fiscal years end on
30 June), so the anchor at the fixture's clock is the report for the year ended 2024-06-30. A test moves the anchor,
shifts the years of the facts or drops one to build one scenario, and every request the strategy makes is recorded.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import (
    AnnualSeriesFacts,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import PeriodKind
from investment_analysis_engine.data.instrument_profile import InstrumentKind, InstrumentKindEvidence, InstrumentProfile
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    AnchorYearEnd,
    AnchorYearEndRequest,
    AnchorYearEndResolution,
    AnchorYearEndUnavailableReason,
)
from investment_analysis_engine.data.security_unit import (
    SecurityUnitRequest,
    SecurityUnitResolution,
    SecurityUnitResolutionReason,
)
from investment_analysis_engine.evaluation.fixtures.graham import (
    NOW,
    SECURITY_ID,
    FixtureFinancialFactsProvider,
)
from investment_analysis_engine.strategies.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
)
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis, run_graham_growth_analysis
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis, run_graham_number_analysis

POLICY = GrahamGrowthCalculationPolicy(base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4)
ANCHOR_YEAR_END = date(2024, 6, 30)
"""The year the fixture's anchor filing is for at its clock."""
LATE = datetime(2025, 12, 1, 12, tzinfo=UTC)
"""A boundary after the next annual report of the fixture issuer was due (2025-10-20), so its anchor is stale."""


def _years_back(value: datetime | None, years: int) -> datetime | None:
    return None if value is None else value.replace(year=value.year - years)


class ScriptedProvider(FixtureFinancialFactsProvider):
    """The fixture provider with a movable anchor, shiftable years, a droppable EPS year and recorded requests.

    Attributes:
        anchor: What ``resolve_anchor_year_end`` answers; ``None`` for the fixture's own answer.
        anchor_error: A failure ``resolve_anchor_year_end`` raises.
        facts_error: A failure every facts request raises.
        eps_years_back: Moves every EPS period this many years earlier.
        oldest_eps_years_back: Moves only the oldest EPS period this many years earlier, which leaves a gap.
        serve_single_year_eps: Answers a single-year EPS request with the newest fiscal year.
        bvps_years_back: Moves the book-value period this many years earlier.
        drop_eps_year_ending: Leaves out the EPS observation that ends on this date.
        earlier_basis_year_ending: Reports the EPS observation that ends on this date as left out on an earlier basis.
        fact_requests: Every ``fetch_facts`` and ``fetch_annual_series`` request, in order.
        anchor_requests: The number of ``resolve_anchor_year_end`` calls.
    """

    def __init__(self) -> None:
        """Start with the fixture's own data and no recorded request."""
        super().__init__()
        self.anchor: AnchorYearEndResolution | None = None
        self.anchor_error: FinancialProviderError | None = None
        self.facts_error: FinancialProviderError | None = None
        self.eps_years_back = 0
        self.oldest_eps_years_back = 0
        self.serve_single_year_eps = False
        self.bvps_years_back = 0
        self.drop_eps_year_ending: date | None = None
        self.earlier_basis_year_ending: date | None = None
        self.fact_requests: list[FinancialFactRequest] = []
        self.anchor_requests = 0
        self.scopes_opened = 0
        self.in_scope = False
        self.unit_requests: list[bool] = []

    def resolve_security_unit(self, request: SecurityUnitRequest) -> SecurityUnitResolution:
        """Record whether an analysis scope was open when share-unit verification was asked for."""
        del request
        self.unit_requests.append(self.in_scope)
        return SecurityUnitResolution(SecurityUnitResolutionReason.PROVIDER_UNSUPPORTED)

    @contextmanager
    def analysis_scope(self, *, subject_id: str, provider_id: str, as_of: datetime | None) -> Iterator[None]:
        """Count the scopes opened, then behave as the fixture does."""
        self.scopes_opened += 1
        self.in_scope = True
        try:
            with super().analysis_scope(subject_id=subject_id, provider_id=provider_id, as_of=as_of):
                yield
        finally:
            self.in_scope = False

    def resolve_anchor_year_end(self, request: AnchorYearEndRequest) -> AnchorYearEndResolution:
        """Return the scripted anchor, raise the scripted failure, or answer as the fixture does."""
        self.anchor_requests += 1
        if self.anchor_error is not None:
            raise self.anchor_error
        return self.anchor or super().resolve_anchor_year_end(request)

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        """Return the fixture's facts, shifted or reduced as scripted."""
        self.fact_requests.append(request)
        if self.facts_error is not None:
            raise self.facts_error
        if self.serve_single_year_eps and request.field_name is FinancialField.EPS and request.observation_count == 1:
            facts = super().fetch_facts(replace(request, observation_count=3), effective_as_of=effective_as_of)[-1:]
        else:
            facts = super().fetch_facts(request, effective_as_of=effective_as_of)
        if request.field_name is FinancialField.EPS:
            kept = [fact for fact in facts if not self._is_dropped(fact)]
            if self.oldest_eps_years_back and kept:
                oldest = min(kept, key=lambda fact: fact.observation_period_end or NOW)
                kept[kept.index(oldest)] = replace(
                    oldest,
                    observation_period_start=_years_back(oldest.observation_period_start, self.oldest_eps_years_back),
                    observation_period_end=_years_back(oldest.observation_period_end, self.oldest_eps_years_back),
                )
            return tuple(self._eps(fact) for fact in kept)
        if request.field_name is FinancialField.BVPS:
            return tuple(
                replace(fact, observation_period_end=_years_back(fact.observation_period_end, self.bvps_years_back))
                for fact in facts
            )
        return facts

    def fetch_annual_series(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> AnnualSeriesFacts:
        """Report the scripted earlier-basis year beside the series, as the SEC adapter does."""
        everything = self._all_eps(request, effective_as_of)
        facts = self.fetch_facts(request, effective_as_of=effective_as_of)
        earlier = tuple(
            replace(self._eps(fact), period_kind=PeriodKind.COMPLETED_ANNUAL)
            for fact in everything
            if fact.observation_period_end is not None
            and fact.observation_period_end.date() == self.earlier_basis_year_ending
        )
        return AnnualSeriesFacts(facts=tuple(fact for fact in facts if fact not in earlier), earlier_basis=earlier)

    def _all_eps(self, request: FinancialFactRequest, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        return super().fetch_facts(request, effective_as_of=effective_as_of)

    def _is_dropped(self, fact: ProviderFact) -> bool:
        end = fact.observation_period_end
        return end is not None and end.date() in {self.drop_eps_year_ending, self.earlier_basis_year_ending}

    def _eps(self, fact: ProviderFact) -> ProviderFact:
        return replace(
            fact,
            observation_period_start=_years_back(fact.observation_period_start, self.eps_years_back),
            observation_period_end=_years_back(fact.observation_period_end, self.eps_years_back),
        )


def anchor_for(year_end: date, *, filed: date | None = None, form: str = "10-K") -> AnchorYearEndResolution:
    """Return an anchor for the fiscal year ending ``year_end``, filed on ``filed`` (default: 75 days later)."""
    accession = f"0000000009-{year_end.year % 100:02d}-000001"
    filing = filed or date.fromordinal(year_end.toordinal() + 75)
    return AnchorYearEndResolution(
        anchor=AnchorYearEnd(
            year_end=year_end, accession=accession, form=form, filing_date=filing, filing_dates={accession: filing}
        )
    )


def no_anchor(reason: AnchorYearEndUnavailableReason, message: str) -> AnchorYearEndResolution:
    """Return the resolution of an issuer with no usable anchor filing."""
    return AnchorYearEndResolution(reason=reason, message=message)


def provider_failure(provider_id: str = "sec_edgar") -> FinancialProviderError:
    """Return a classified provider failure."""
    return FinancialProviderError("simulated outage", kind=ProviderFailureKind.UNREACHABLE, provider_id=provider_id)


def equity_profile(ticker: str = SECURITY_ID) -> InstrumentProfile:
    """Return an instrument profile that classifies the instrument as an equity."""
    return InstrumentProfile(
        ticker, None, InstrumentKindEvidence(ticker, InstrumentKind.EQUITY, "EQUITY", "yfinance", NOW), ()
    )


def etf_profile(ticker: str = SECURITY_ID) -> InstrumentProfile:
    """Return an instrument profile that affirmatively classifies the instrument as an ETF."""
    return InstrumentProfile(
        ticker, None, InstrumentKindEvidence(ticker, InstrumentKind.ETF, "ETF", "yfinance", NOW), ()
    )


def run_number(  # noqa: PLR0913
    provider: FixtureFinancialFactsProvider,
    *,
    cache: Any = None,
    effective_as_of: datetime = NOW,
    as_of: datetime | None = None,
    use_cache: bool = True,
    ticker: str = SECURITY_ID,
    profile: InstrumentProfile | None = None,
    **overrides: float | None,
) -> GrahamNumberAnalysis:
    """Run Graham Number on ``provider``; ``overrides`` set ``eps_override``, ``bvps_override``, ``quote_override``."""
    resolver = GrahamNumberInputResolver(provider, cache=cache, clock=lambda: NOW)
    values: dict[str, float | None] = {"eps_override": None, "bvps_override": None, "quote_override": None}
    values.update(overrides)
    return run_graham_number_analysis(
        resolver=resolver,
        ticker=ticker,
        as_of=as_of,
        effective_as_of=effective_as_of,
        use_cache=use_cache,
        instrument_profile=profile,
        **values,
    )


def run_growth(  # noqa: PLR0913
    provider: FixtureFinancialFactsProvider,
    *,
    cache: Any = None,
    effective_as_of: datetime = NOW,
    as_of: datetime | None = None,
    use_cache: bool = True,
    eps_basis: str = "three_year_average",
    ticker: str = SECURITY_ID,
    profile: InstrumentProfile | None = None,
    **overrides: float | None,
) -> GrahamGrowthAnalysis:
    """Run Graham Growth Value on ``provider``; ``overrides`` are ``eps_override`` and ``quote_override``."""
    resolver = GrahamGrowthInputResolver(provider, cache=cache, clock=lambda: NOW)
    values: dict[str, float | None] = {"eps_override": None, "quote_override": None}
    values.update(overrides)
    return run_graham_growth_analysis(
        resolver=resolver,
        ticker=ticker,
        eps_basis=eps_basis,
        expected_growth=5.0,
        aaa_yield_override=4.5,
        as_of=as_of,
        effective_as_of=effective_as_of,
        use_cache=use_cache,
        policy=POLICY,
        instrument_profile=profile,
        **values,
    )


def requested_fields(provider: ScriptedProvider) -> Sequence[FinancialField]:
    """Return the field of every request the provider recorded."""
    return [request.field_name for request in provider.fact_requests]
