"""Direct contracts for shared financial resolution and evidence predicates."""

from dataclasses import replace
from math import inf, nan
from re import escape

import pytest

from src.analysis.shared.financial_resolution import (
    common_currency,
    has_provider_backed_evidence,
    is_known_etf,
    margin_of_safety,
    resolve_normalized_eps,
    resolve_optional_quote,
    validate_profile_ticker,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialField, FinancialProviderError
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionOutcome, ResolutionStage
from src.data.financial.resolver import InputResolver
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from tests.analysis.graham_value.test_resolver import (
    NOW,
    PROVIDER_ID,
    SUBJECT_ID,
    FakeProvider,
    SpyCache,
    _make_fact,
    _make_provider_input,
    _three_fy_facts,
)
from tests.analysis.test_instrument_applicability import _profile


@pytest.mark.parametrize("basis", ["three_year_average", "ttm", "custom_observation"])
@pytest.mark.parametrize("value", [0.0, -2.0, 5.0, nan, inf])
def test_eps_override_bypasses_provider_and_cache(basis: str, value: float) -> None:
    provider = FakeProvider()
    cache = SpyCache()
    result = resolve_normalized_eps(
        InputResolver(provider, cache, clock=lambda: NOW),
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis=basis,
        eps_override=value,
        as_of=NOW,
        use_cache=True,
    )
    assert provider.call_count == cache.get_count == cache.put_count == 0
    assert result.resolution_trace.events[0].stage is ResolutionStage.OVERRIDE
    if value in (0.0, -2.0, 5.0):
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        assert result.resolved_input.value == value
        assert result.resolved_input.basis == basis
        assert result.resolved_input.resolved_at == NOW
        assert result.resolved_input.as_of == NOW
        assert result.resolved_input.source_kind is SourceKind.OVERRIDE
    else:
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.resolved_input is None
        assert result.resolution_trace.events[-1].outcome is ResolutionOutcome.INVALID


@pytest.mark.parametrize("basis", ["three_year_average", "ttm"])
def test_eps_provider_cache_and_bypass_preserve_basis_and_provenance(basis: str) -> None:
    facts = _three_fy_facts() if basis == "three_year_average" else (_make_fact(basis="ttm"),)
    provider = FakeProvider(facts)
    resolver = InputResolver(provider, InMemoryResolvedInputCache(), clock=lambda: NOW)
    results = [
        resolve_normalized_eps(
            resolver,
            security_subject_id=SUBJECT_ID,
            security_provider_id=PROVIDER_ID,
            eps_basis=basis,
            eps_override=None,
            as_of=None,
            use_cache=use_cache,
        )
        for use_cache in (True, True, False)
    ]
    assert provider.call_count == 2
    assert provider.last_request is not None
    assert provider.last_request.basis == ("fiscal_year" if basis == "three_year_average" else "ttm")
    assert provider.last_request.observation_count == (3 if basis == "three_year_average" else 1)
    for result in results:
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        assert result.resolved_input.basis == basis
        assert result.resolved_input.resolved_at == NOW
    first, cached, bypass = results
    assert first.resolved_input is not None
    assert cached.resolved_input is not None
    assert bypass.resolved_input is not None
    assert first.resolved_input.value == cached.resolved_input.value == bypass.resolved_input.value
    assert cached.resolved_input.source_kind is SourceKind.CACHE
    assert any(event.outcome is ResolutionOutcome.HIT for event in cached.resolution_trace.events)
    assert any(
        event.stage is ResolutionStage.CACHE and event.outcome is ResolutionOutcome.NOT_USED
        for event in bypass.resolution_trace.events
    )
    if basis == "three_year_average":
        assert first.resolved_input.value == 3.0
        assert first.resolved_input.lineage is not None
        assert len(first.resolved_input.lineage.components) == 3
        assert cached.resolved_input.lineage == first.resolved_input.lineage


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("valid", CalculationStatus.OK),
        ("missing", CalculationStatus.INPUT_UNAVAILABLE),
        ("error", CalculationStatus.PROVIDER_ERROR),
        ("invalid_override", CalculationStatus.INVALID_INPUT),
        ("override", CalculationStatus.OK),
    ],
)
def test_optional_quote_preserves_resolution_outcomes(mode: str, expected: CalculationStatus) -> None:
    facts = (_make_fact(field=FinancialField.CURRENT_PRICE, basis=None, observed_at=NOW),)
    provider = FakeProvider(
        FinancialProviderError("fixture quote failure") if mode == "error" else facts if mode == "valid" else ()
    )
    result = resolve_optional_quote(
        InputResolver(provider, clock=lambda: NOW),
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        quote_override=nan if mode == "invalid_override" else 12.0 if mode == "override" else None,
        as_of=None,
        use_cache=False,
    )
    assert result.status is expected
    assert result.resolution_trace.events
    assert provider.call_count == (0 if mode in ("invalid_override", "override") else 1)
    if expected is CalculationStatus.OK:
        assert result.resolved_input is not None
        assert result.resolved_input.resolved_at == NOW
        assert result.reason is None
    else:
        assert result.resolved_input is None
        assert result.reason


@pytest.mark.parametrize("message", ["Strategy A rejected this ticker.", "Caller B: wrong instrument!"])
def test_profile_mismatch_uses_exact_caller_message(message: str) -> None:
    profile = InstrumentProfile("ACME", None, None, ())
    validate_profile_ticker(" acme ", profile, mismatch_message=message)
    validate_profile_ticker("OTHER", None, mismatch_message=message)
    with pytest.raises(ValueError, match=escape(message)) as error:
        validate_profile_ticker("OTHER", profile, mismatch_message=message)
    assert str(error.value) == message


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (None, False),
        (InstrumentProfile("ACME", None, None, ()), False),
        (_profile(None, "MUTUALFUND"), False),
        (_profile(InstrumentKind.EQUITY, "EQUITY"), False),
        (_profile(InstrumentKind.ETF, "ETF"), True),
    ],
)
def test_etf_requires_affirmative_kind(profile: InstrumentProfile | None, expected: bool) -> None:
    assert is_known_etf(profile) is expected


def test_evidence_and_currency_preserve_missing_override_and_mixed_cases() -> None:
    provider = _make_provider_input()
    override = ResolvedInput("eps", 4.0, SourceKind.OVERRIDE, NOW)
    assert not has_provider_backed_evidence(None, override)
    assert has_provider_backed_evidence(override, provider)
    assert has_provider_backed_evidence(
        replace(provider, source_kind=SourceKind.CACHE, origin_source_kind=SourceKind.PROVIDER, cache_schema_version=1)
    )
    assert common_currency() is None
    assert common_currency(override, provider) == "USD"
    assert common_currency(provider, replace(provider, currency="CAD")) is None
    assert common_currency(override) is None


@pytest.mark.parametrize(
    ("reference", "currency", "expected"),
    [
        (100.0, "USD", 20.0),
        (50.0, "USD", -60.0),
        (None, "USD", None),
        (0.0, "USD", None),
        (-1.0, "USD", None),
        (inf, "USD", None),
        (nan, "USD", None),
        (100.0, "CAD", None),
        (100.0, None, 20.0),
    ],
)
def test_margin_preserves_unavailable_and_currency_rules(
    reference: float | None,
    currency: str | None,
    expected: float | None,
) -> None:
    quote = _make_provider_input(field_name="current_price", value=80.0)
    assert margin_of_safety(reference, quote, valuation_currency=currency) == expected
    assert margin_of_safety(reference, None, valuation_currency=currency) is None
