"""Resolving balance-sheet fields at named year-ends, and the cache version that keys every financial fact."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputCacheKey
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderAmountSource,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import (
    FinancialSubjectKind,
    PeriodKind,
    ResolvedInput,
    SourceKind,
)
from investment_analysis_engine.data.financial.resolver import (
    DEFAULT_CACHE_SCHEMA_VERSION,
    InputResolver,
    InstantSeriesResolution,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.strategies.fcf_growth.input_resolver import CACHE_SCHEMA_VERSION
from tests._sec_instants import NOW, adapter_for, year_ends

_DAY = date(2025, 12, 31)


def _resolver(provider: object, cache: InMemoryResolvedInputCache | None = None) -> InputResolver:
    return InputResolver(provider, cache, clock=lambda: NOW)  # type: ignore[arg-type]


def _request(field: FinancialField, ends: tuple[date, ...] = (_DAY,), **keywords: object) -> InstantSeriesRequest:
    return InstantSeriesRequest("SYN", field, SEC_PROVIDER_ID, ends, **keywords)  # type: ignore[arg-type]


def _fact(day: date = _DAY, **changes: object) -> ProviderFact:
    available = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(days=50)
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="SYN",
        field_name=FinancialField.TOTAL_ASSETS,
        value=100.0,
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field="us-gaap:Assets",
        retrieved_at=NOW,
        basis="fiscal_year_end",
        currency="USD",
        observation_period_end=datetime.combine(day, datetime.max.time(), tzinfo=UTC),
        available_at=available,
        period_kind=PeriodKind.INSTANT,
        provider_fact_id=f"a:{day}",
    )
    return replace(fact, **changes)  # type: ignore[arg-type]


class _Series:
    def __init__(self, answer: InstantSeriesFacts | Exception) -> None:
        self.answer = answer
        self.requests: list[tuple[InstantSeriesRequest, datetime]] = []

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:
        self.requests.append((request, effective_as_of))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


# --- the entry ----------------------------------------------------------------------------------------------------


def test_each_date_present_is_one_resolved_input_naming_its_concept_and_the_absent_dates_are_listed() -> None:
    ends = year_ends(date(2026, 1, 31))
    request = InstantSeriesRequest("WMT", FinancialField.RECEIVABLES, SEC_PROVIDER_ID, ends)

    result = _resolver(adapter_for("WMT")).resolve_instant_series(request)

    assert result.status is CalculationStatus.OK
    assert result.absences == ()
    assert [item.observation_period_end.date() for item in result.inputs if item.observation_period_end] == list(ends)
    first = result.inputs[0]
    assert (first.field_name, first.provider_field, first.units, first.currency) == (
        "receivables",
        "us-gaap:ReceivablesNetCurrent",
        "currency",
        "USD",
    )
    assert first.source_kind is SourceKind.PROVIDER
    assert first.period_kind is PeriodKind.INSTANT
    assert first.observation_period_start is None
    assert first.basis == "fiscal_year_end"
    assert first.available_at is not None
    assert first.provider_fact_id is not None
    assert first.provider_fact_id.endswith(":2024-01-31")
    assert [event.outcome.value for event in result.resolution_trace.events] == ["attempted", "success"]


def test_a_derived_total_carries_its_terms_as_lineage() -> None:
    request = InstantSeriesRequest("WMT", FinancialField.TOTAL_LIABILITIES, SEC_PROVIDER_ID, (date(2026, 1, 31),))

    result = _resolver(adapter_for("WMT")).resolve_instant_series(request)

    item = result.inputs[0]
    assert item.value == 178_488_000_000.0
    assert item.source_kind is SourceKind.DERIVED
    assert item.provider_field is not None
    assert item.provider_field.startswith("derived:")
    assert item.lineage is not None
    assert [component.value for component in item.lineage.components] == [
        284_668_000_000.0,
        105_887_000_000.0,
        293_000_000.0,
    ]
    assert all(component.source_kind is SourceKind.PROVIDER for component in item.lineage.components)
    assert all(component.period_kind is PeriodKind.INSTANT for component in item.lineage.components)
    assert item.lineage.components[0].field_name == "us-gaap:LiabilitiesAndStockholdersEquity"


def test_a_series_with_some_dates_absent_is_ok_and_says_which() -> None:
    ends = year_ends(date(2025, 12, 31))
    request = InstantSeriesRequest("MNST", FinancialField.NONCURRENT_LONG_TERM_DEBT, SEC_PROVIDER_ID, ends)

    result = _resolver(adapter_for("MNST")).resolve_instant_series(request)

    assert result.status is CalculationStatus.OK
    assert [item.value for item in result.inputs] == [373_951_000.0]
    assert {item.period_end.year: item.reason for item in result.absences} == {
        2023: InstantAbsenceReason.NOT_TAGGED,
        2025: InstantAbsenceReason.NOT_TAGGED,
    }


def test_a_series_with_no_date_present_is_unavailable_and_keeps_the_reasons() -> None:
    ends = year_ends(date(2025, 12, 31))
    request = InstantSeriesRequest("SAP", FinancialField.NONCURRENT_LONG_TERM_DEBT, SEC_PROVIDER_ID, ends)

    result = _resolver(adapter_for("SAP")).resolve_instant_series(request)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.inputs == ()
    assert {item.reason for item in result.absences} == {InstantAbsenceReason.UNSUPPORTED}
    assert result.reason is not None
    assert "no noncurrent_long_term_debt" in result.reason


def test_a_provider_without_series_support_is_unavailable() -> None:
    result = _resolver(object()).resolve_instant_series(_request(FinancialField.TOTAL_ASSETS))
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason is not None
    assert "does not serve balance-sheet series" in result.reason


def test_a_provider_failure_is_a_provider_error_with_its_kind() -> None:
    failure = FinancialProviderError("boom", kind=ProviderFailureKind.UNREACHABLE, provider_id=SEC_PROVIDER_ID)
    result = _resolver(_Series(failure)).resolve_instant_series(_request(FinancialField.TOTAL_ASSETS))

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure is not None
    assert result.provider_failure.kind is ProviderFailureKind.UNREACHABLE
    assert result.resolution_trace.events[-1].outcome.value == "error"


def test_the_boundary_given_or_the_clock_is_what_the_provider_is_told() -> None:
    provider = _Series(InstantSeriesFacts(facts=(_fact(),)))
    resolver = _resolver(provider)
    resolver.resolve_instant_series(_request(FinancialField.TOTAL_ASSETS))
    resolver.resolve_instant_series(_request(FinancialField.TOTAL_ASSETS, as_of=NOW + timedelta(days=1)))
    assert [boundary for _request_, boundary in provider.requests] == [NOW, NOW + timedelta(days=1)]


@pytest.mark.parametrize(
    "answer",
    [
        InstantSeriesFacts(facts=(_fact(subject_id="OTHER"),)),
        InstantSeriesFacts(facts=(_fact(provider_id="other"),)),
        InstantSeriesFacts(facts=(_fact(field_name=FinancialField.CURRENT_ASSETS),)),
        InstantSeriesFacts(facts=(_fact(basis="fiscal_year"),)),
        InstantSeriesFacts(facts=(_fact(available_at=None),)),
        InstantSeriesFacts(facts=(_fact(available_at=NOW + timedelta(days=1)),)),
        InstantSeriesFacts(facts=(_fact(), _fact(date(2024, 12, 31)))),
        InstantSeriesFacts(),
        InstantSeriesFacts(absences=(InstantAbsence(date(2024, 12, 31), InstantAbsenceReason.NOT_TAGGED, "x"),)),
    ],
)
def test_an_answer_that_does_not_answer_the_request_is_rejected(answer: InstantSeriesFacts) -> None:
    result = _resolver(_Series(answer)).resolve_instant_series(_request(FinancialField.TOTAL_ASSETS))

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.inputs == ()
    assert result.provider_failure is not None
    assert result.provider_failure.kind is ProviderFailureKind.UNEXPECTED_RESPONSE


def test_a_fact_from_after_the_boundary_in_time_fails_the_quality_check() -> None:
    far = date(2027, 12, 31)
    late = _fact(far, available_at=NOW - timedelta(days=1))
    result = _resolver(_Series(InstantSeriesFacts(facts=(late,)))).resolve_instant_series(
        _request(FinancialField.TOTAL_ASSETS, (far,))
    )
    assert result.status is CalculationStatus.PROVIDER_ERROR


def test_the_series_resolution_enforces_its_invariants() -> None:
    item = ResolvedInput(field_name="total_assets", value=1.0, source_kind=SourceKind.OVERRIDE, resolved_at=NOW)
    with pytest.raises(ValueError, match="OK requires"):
        InstantSeriesResolution(status=CalculationStatus.OK)
    with pytest.raises(ValueError, match="non-OK"):
        InstantSeriesResolution(status=CalculationStatus.INPUT_UNAVAILABLE)
    with pytest.raises(ValueError, match="non-OK"):
        InstantSeriesResolution(status=CalculationStatus.INPUT_UNAVAILABLE, inputs=(item,), reason="x")
    with pytest.raises(ValueError, match="provider_failure requires"):
        InstantSeriesResolution(
            status=CalculationStatus.INPUT_UNAVAILABLE,
            reason="x",
            provider_failure=ProviderFailureRecord(kind=ProviderFailureKind.UNREACHABLE, provider_id=SEC_PROVIDER_ID),
        )


def test_an_instant_input_carries_an_end_and_no_start() -> None:
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="period_kind=instant"):
        ResolvedInput(
            field_name="total_assets",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=stamp,
            period_kind=PeriodKind.INSTANT,
        )
    with pytest.raises(ValueError, match="period_kind=instant"):
        ResolvedInput(
            field_name="total_assets",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=stamp,
            period_kind=PeriodKind.INSTANT,
            observation_period_start=stamp,
            observation_period_end=stamp,
        )


def test_an_amount_source_term_is_a_provider_input_with_its_own_dates() -> None:
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    term = ProviderAmountSource("SYN", SEC_PROVIDER_ID, "us-gaap:X", -3.0, "USD", stamp, stamp, stamp, "a:b")
    fact = _fact(
        field_name=FinancialField.TOTAL_LIABILITIES,
        provider_field="derived:us-gaap:X",
        source_facts=(term,),
        source_transformation="x",
    )
    result = _resolver(_Series(InstantSeriesFacts(facts=(fact,)))).resolve_instant_series(
        _request(FinancialField.TOTAL_LIABILITIES)
    )
    component = result.inputs[0].lineage.components[0]  # type: ignore[union-attr]
    assert (component.value, component.currency, component.observation_period_end) == (-3.0, "USD", stamp)


# --- the cache version --------------------------------------------------------------------------------------------


class _Equity:
    """A latest-only provider that counts how often it is asked."""

    def __init__(self) -> None:
        self.calls = 0

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        self.calls += 1
        assert request.field_name is FinancialField.STOCKHOLDERS_EQUITY
        assert effective_as_of == NOW
        return (
            replace(
                _fact(),
                field_name=FinancialField.STOCKHOLDERS_EQUITY,
                provider_field="us-gaap:StockholdersEquity",
                period_kind=None,
                observation_period_end=datetime(2025, 12, 31, tzinfo=UTC),
            ),
        )


def _equity_request() -> FinancialFactRequest:
    return FinancialFactRequest(
        FinancialSubjectKind.SECURITY,
        "SYN",
        FinancialField.STOCKHOLDERS_EQUITY,
        SEC_PROVIDER_ID,
        basis="fiscal_year_end",
    )


def test_the_financial_fact_cache_version_was_bumped_where_it_is_set() -> None:
    assert DEFAULT_CACHE_SCHEMA_VERSION == 2
    assert CACHE_SCHEMA_VERSION == 3
    assert InputResolver(_Equity(), clock=lambda: NOW)._schema_version == DEFAULT_CACHE_SCHEMA_VERSION


def test_an_entry_stored_under_the_older_version_is_refused_and_a_new_entry_round_trips() -> None:
    provider = _Equity()
    cache = InMemoryResolvedInputCache(lambda: NOW)
    older = ResolvedInputCacheKey(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="SYN",
        field_name="stockholders_equity",
        basis="fiscal_year_end",
        provider_id=SEC_PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    cache.put(
        older,
        ResolvedInput(
            field_name="stockholders_equity",
            value=1.0,
            source_kind=SourceKind.PROVIDER,
            resolved_at=NOW,
            basis="fiscal_year_end",
            provider_id=SEC_PROVIDER_ID,
            units="currency",
            currency="USD",
            observation_period_end=datetime(2025, 12, 31, tzinfo=UTC),
            available_at=datetime(2026, 2, 20, tzinfo=UTC),
            retrieved_at=NOW,
        ),
    )
    resolver = _resolver(provider, cache)

    first = resolver.resolve(_equity_request(), use_cache=True)
    assert provider.calls == 1
    assert first.resolved_input is not None
    assert first.resolved_input.source_kind is SourceKind.PROVIDER
    assert first.resolved_input.value == 100.0

    second = resolver.resolve(_equity_request(), use_cache=True)
    assert provider.calls == 1
    assert second.resolved_input is not None
    assert second.resolved_input.source_kind is SourceKind.CACHE
    assert second.resolved_input.cache_schema_version == DEFAULT_CACHE_SCHEMA_VERSION
