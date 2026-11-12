"""The resolver and the Graham assemblies store the kind and provider of a provider failure.

A typed failure raised by a provider is carried onto the stored resolution; a provider answer the project rejects is
an ``unexpected_response`` from the provider the request named; anything that is not a typed provider failure
propagates.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import (
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from investment_analysis_engine.data.financial.resolver import (
    InputResolutionResult,
    InputResolver,
    _bvps_component_alignment_failure,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from tests.analysis.graham_value._anchored import anchor_for
from tests.analysis.graham_value.test_resolver import (
    FY2024_END,
    NOW,
    PERIOD_END,
    PERIOD_START,
    PROVIDER_ID,
    RETRIEVED_AT,
    SUBJECT_ID,
    _c2c_request,
    _make_fact,
    _make_request,
    _three_fy_facts,
)

_FAILED = set(ProviderFailureKind)


class _Provider:
    """Answers each field from a table; a table entry that is an exception is raised."""

    def __init__(self, answers: dict[FinancialField, Any]) -> None:
        self.answers = answers

    def fetch_facts(
        self,
        request: FinancialFactRequest,
        *,
        effective_as_of: datetime,  # noqa: ARG002
    ) -> tuple[ProviderFact, ...]:
        answer = self.answers.get(request.field_name, ())
        if isinstance(answer, BaseException):
            raise answer
        return tuple(answer)


def _error(kind: ProviderFailureKind | None, provider_id: str = PROVIDER_ID) -> FinancialProviderError:
    if kind is None:
        return FinancialProviderError("synthetic failure")
    return FinancialProviderError("synthetic failure", kind=kind, provider_id=provider_id)


def _resolver(answers: dict[FinancialField, Any]) -> InputResolver:
    return InputResolver(_Provider(answers), clock=lambda: NOW)


def _record(kind: ProviderFailureKind, provider_id: str = PROVIDER_ID) -> ProviderFailureRecord:
    return ProviderFailureRecord(kind=kind, provider_id=provider_id)


@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_a_typed_failure_is_carried_by_the_single_fact_resolution(kind: ProviderFailureKind) -> None:
    result = _resolver({FinancialField.EPS: _error(kind)}).resolve(_make_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(kind)
    assert "synthetic failure" in (result.reason or "")


@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_a_typed_failure_is_carried_by_the_three_year_average(kind: ProviderFailureKind) -> None:
    result = _resolver({FinancialField.EPS: _error(kind)}).resolve_three_year_average_eps(
        _c2c_request(), use_cache=False
    )

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(kind)


def test_an_unclassified_failure_stores_no_kind() -> None:
    result = _resolver({FinancialField.EPS: _error(None)}).resolve(_make_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure is None


@pytest.mark.parametrize("defect", [RuntimeError("defect"), ValueError("defect"), KeyError("defect")])
def test_an_exception_that_is_not_a_provider_failure_propagates(defect: BaseException) -> None:
    resolver = _resolver({FinancialField.EPS: defect})

    with pytest.raises(type(defect)):
        resolver.resolve(_make_request(), use_cache=False)
    with pytest.raises(type(defect)):
        resolver.resolve_three_year_average_eps(_c2c_request(), use_cache=False)


def test_more_than_one_fact_is_an_unexpected_response_from_the_requested_provider() -> None:
    facts = (_make_fact(), _make_fact(value=5.0))

    result = _resolver({FinancialField.EPS: facts}).resolve(_make_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(ProviderFailureKind.UNEXPECTED_RESPONSE)


def test_a_fact_that_fails_the_coherence_checks_is_an_unexpected_response() -> None:
    wrong_subject = _make_fact(subject_id="OTHER")

    result = _resolver({FinancialField.EPS: (wrong_subject,)}).resolve(_make_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(ProviderFailureKind.UNEXPECTED_RESPONSE)


def test_a_candidate_that_fails_validation_is_an_unexpected_response() -> None:
    candidates = tuple(replace(fact, basis="mismatched_basis") for fact in _three_fy_facts())

    result = _resolver({FinancialField.EPS: candidates}).resolve_three_year_average_eps(_c2c_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(ProviderFailureKind.UNEXPECTED_RESPONSE)


def test_a_rejected_answer_names_the_provider_of_the_request() -> None:
    request = _make_request(provider_id="provider-b")

    result = _resolver({FinancialField.EPS: (_make_fact(), _make_fact(value=5.0))}).resolve(request, use_cache=False)

    assert result.provider_failure == ProviderFailureRecord(
        kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id="provider-b"
    )


def test_a_failure_kind_requires_a_provider_error_status() -> None:
    with pytest.raises(ValueError, match="provider_failure requires status PROVIDER_ERROR"):
        InputResolutionResult(
            status=CalculationStatus.INPUT_UNAVAILABLE,
            reason="unavailable",
            reason_code=ReasonCode.MISSING_FACT,
            provider_failure=_record(ProviderFailureKind.NO_DATA),
        )


# --- BVPS derivation ---------------------------------------------------------------------------------------------


def _component_fact(field: FinancialField, value: float, **kwargs: Any) -> ProviderFact:
    currency = "USD" if field is FinancialField.STOCKHOLDERS_EQUITY else None
    units = FinancialUnit.CURRENCY if currency else FinancialUnit.SHARES
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=field,
        value=value,
        units=units,
        provider_id=PROVIDER_ID,
        provider_field=f"synthetic_{field.value}",
        retrieved_at=RETRIEVED_AT,
        basis="fiscal_year_end",
        currency=currency,
        observation_period_start=PERIOD_START,
        observation_period_end=PERIOD_END,
        available_at=RETRIEVED_AT,
        **kwargs,
    )


def _bvps_request() -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=FinancialField.BVPS,
        provider_id=PROVIDER_ID,
        as_of=None,
    )


def _components(equity: float, shares: float) -> dict[FinancialField, Any]:
    return {
        FinancialField.STOCKHOLDERS_EQUITY: (_component_fact(FinancialField.STOCKHOLDERS_EQUITY, equity),),
        FinancialField.COMMON_SHARES_OUTSTANDING: (_component_fact(FinancialField.COMMON_SHARES_OUTSTANDING, shares),),
        FinancialField.PREFERRED_SHARES_OUTSTANDING: (
            _component_fact(FinancialField.PREFERRED_SHARES_OUTSTANDING, 0.0),
        ),
    }


_BVPS_LABELS = {
    FinancialField.STOCKHOLDERS_EQUITY: "Stockholders' equity",
    FinancialField.COMMON_SHARES_OUTSTANDING: "The common share count",
    FinancialField.PREFERRED_SHARES_OUTSTANDING: "The preferred share count",
}


@pytest.mark.parametrize("failed", list(_BVPS_LABELS))
@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_a_component_failure_passes_its_kind_through_the_bvps_derivation(
    failed: FinancialField, kind: ProviderFailureKind
) -> None:
    answers = _components(100.0, 10.0) | {failed: _error(kind)}

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(kind)
    assert _BVPS_LABELS[failed] in (result.reason or "")


def test_a_non_finite_bvps_quotient_is_reachable_from_finite_components() -> None:
    answers = _components(1e300, 1e-10)

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert "non-finite" in (result.reason or "")
    assert result.provider_failure == _record(ProviderFailureKind.UNEXPECTED_RESPONSE)


# --- the code of an unavailable BVPS derivation ------------------------------------------------------------------


def _part(field: FinancialField, value: float, *, units: FinancialUnit, currency: str | None) -> ResolvedInput:
    return ResolvedInput(
        field.value,
        value,
        SourceKind.PROVIDER,
        NOW,
        units=units.value,
        currency=currency,
        provider_id=PROVIDER_ID,
        retrieved_at=RETRIEVED_AT,
        observation_period_end=PERIOD_END,
    )


def _equity(*, units: FinancialUnit = FinancialUnit.CURRENCY, currency: str | None = "USD") -> ResolvedInput:
    return _part(FinancialField.STOCKHOLDERS_EQUITY, 100.0, units=units, currency=currency)


def _preferred(value: float = 0.0, units: FinancialUnit = FinancialUnit.SHARES) -> ResolvedInput:
    return _part(FinancialField.PREFERRED_SHARES_OUTSTANDING, value, units=units, currency=None)


def _common(value: float = 10.0, units: FinancialUnit = FinancialUnit.SHARES) -> ResolvedInput:
    return _part(FinancialField.COMMON_SHARES_OUTSTANDING, value, units=units, currency=None)


@pytest.mark.parametrize(
    ("equity", "preferred", "common", "code", "message"),
    [
        (
            _equity(),
            _preferred(),
            replace(_common(), observation_period_end=PERIOD_END - timedelta(days=365)),
            ReasonCode.INCOMPATIBLE_PERIOD,
            "Equity and the share counts are not for one reporting-period end.",
        ),
        (
            _equity(currency=None),
            _preferred(),
            _common(),
            ReasonCode.INCOMPATIBLE_CURRENCY,
            "Stockholders' equity has no currency.",
        ),
        (
            _equity(units=FinancialUnit.CURRENCY_PER_SHARE),
            _preferred(),
            _common(),
            ReasonCode.INCOMPATIBLE_UNITS,
            "Stockholders' equity is not a currency amount.",
        ),
        (
            _equity(),
            _preferred(),
            _common(units=FinancialUnit.CURRENCY),
            ReasonCode.INCOMPATIBLE_UNITS,
            "A share count is not expressed in shares.",
        ),
        (
            _equity(),
            _preferred(-1.0),
            _common(),
            ReasonCode.AMBIGUOUS_FACT,
            "The reported preferred share count is negative.",
        ),
        (
            _equity(),
            _preferred(),
            _common(0.0),
            ReasonCode.AMBIGUOUS_FACT,
            "The reported common share count is not greater than zero.",
        ),
    ],
)
def test_components_that_cannot_be_aligned_carry_the_code_of_the_cause(
    equity: ResolvedInput, preferred: ResolvedInput, common: ResolvedInput, code: ReasonCode, message: str
) -> None:
    assert _bvps_component_alignment_failure(equity, preferred, common) == (code, message)


def test_aligned_components_have_no_alignment_failure() -> None:
    assert _bvps_component_alignment_failure(_equity(), _preferred(), _common()) is None


def test_components_for_two_period_ends_make_the_derived_bvps_unavailable_with_the_period_code() -> None:
    answers = _components(100.0, 10.0)
    shifted = replace(
        _component_fact(FinancialField.COMMON_SHARES_OUTSTANDING, 10.0),
        observation_period_start=PERIOD_START - timedelta(days=365),
        observation_period_end=PERIOD_END - timedelta(days=365),
    )
    answers[FinancialField.COMMON_SHARES_OUTSTANDING] = (shifted,)

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.INCOMPATIBLE_PERIOD
    assert result.reason == "Equity and the share counts are not for one reporting-period end."


def test_a_company_with_preferred_shares_has_no_common_equity_and_carries_the_scope_code() -> None:
    answers = _components(100.0, 10.0)
    answers[FinancialField.PREFERRED_SHARES_OUTSTANDING] = (
        _component_fact(FinancialField.PREFERRED_SHARES_OUTSTANDING, 5.0),
    )

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.INCOMPATIBLE_SCOPE
    assert (
        result.reason == "The company has preferred shares, so stockholders' equity is not common shareholders' equity."
    )


@pytest.mark.parametrize("failed", list(_BVPS_LABELS))
def test_an_unavailable_component_passes_its_code_through_the_bvps_derivation(failed: FinancialField) -> None:
    label = _BVPS_LABELS[failed]
    answers = _components(100.0, 10.0) | {failed: FactsNotAvailableAsOf("filed after the boundary")}

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert (result.reason or "").startswith(f"{label} could not be resolved: filed after the boundary")
    assert (result.reason or "").endswith("is not assumed to be zero.") is (
        failed is FinancialField.PREFERRED_SHARES_OUTSTANDING
    )


def test_missing_preferred_share_data_is_not_assumed_to_be_zero() -> None:
    answers = _components(100.0, 10.0) | {FinancialField.PREFERRED_SHARES_OUTSTANDING: ()}

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.MISSING_FACT
    assert result.reason == (
        "The preferred share count could not be resolved: Provider returned no data for the requested field. "
        "Missing preferred-share data is not assumed to be zero."
    )


def test_a_component_provider_error_carries_no_reason_code() -> None:
    answers = _components(100.0, 10.0) | {FinancialField.STOCKHOLDERS_EQUITY: _error(None)}

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.reason_code is None


# --- the Graham assemblies record the failure against the input ---------------------------------------------------


def _number_assembly(answers: dict[FinancialField, Any]) -> Any:
    resolver = GrahamNumberInputResolver(_Provider(answers), clock=lambda: NOW)
    return resolver.assemble_graham_number(
        anchor=anchor_for(FY2024_END.date()).anchor,
        security_subject_id=SUBJECT_ID,
        use_cache=False,
    )


def _growth_assembly(answers: dict[FinancialField, Any]) -> Any:
    resolver = GrahamGrowthInputResolver(_Provider(answers), clock=lambda: NOW)
    return resolver.assemble_growth_value(
        anchor=anchor_for(FY2024_END.date()).anchor,
        security_subject_id=SUBJECT_ID,
        eps_basis="fiscal_year",
        expected_growth=5.0,
        aaa_yield_override=4.5,
        use_cache=False,
    )


@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_graham_number_records_the_failed_input(kind: ProviderFailureKind) -> None:
    eps = _number_assembly({FinancialField.EPS: _error(kind, SEC_PROVIDER_ID)})
    bvps = _number_assembly(
        {FinancialField.EPS: _three_fy_facts(SEC_PROVIDER_ID), FinancialField.BVPS: _error(kind, SEC_PROVIDER_ID)}
    )

    assert eps.status is CalculationStatus.PROVIDER_ERROR
    assert eps.provider_failure == _record(kind, SEC_PROVIDER_ID).for_input("eps")
    assert bvps.status is CalculationStatus.PROVIDER_ERROR
    assert bvps.provider_failure == _record(kind, SEC_PROVIDER_ID).for_input("bvps")


@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_graham_growth_records_the_failed_input(kind: ProviderFailureKind) -> None:
    eps = _growth_assembly({FinancialField.EPS: _error(kind, SEC_PROVIDER_ID)})

    assert eps.provider_failure == _record(kind, SEC_PROVIDER_ID).for_input("eps")


def test_a_non_failing_assembly_stores_no_failure() -> None:
    assembly = _number_assembly({FinancialField.EPS: _three_fy_facts(SEC_PROVIDER_ID)})

    assert assembly.status is not CalculationStatus.PROVIDER_ERROR
    assert assembly.provider_failure is None


def test_the_yahoo_clock_guard_is_a_defect_that_propagates_through_the_resolver() -> None:
    class _NaiveClockProvider:
        def fetch_facts(
            self,
            request: FinancialFactRequest,  # noqa: ARG002
            *,
            effective_as_of: datetime,  # noqa: ARG002
        ) -> tuple[ProviderFact, ...]:
            raise ValueError("Yahoo financial-facts adapter clock returned a naive datetime.")

    resolver = InputResolver(_NaiveClockProvider(), clock=lambda: NOW)

    with pytest.raises(ValueError, match="naive datetime"):
        resolver.resolve(_make_request(), use_cache=False)


def test_a_not_available_as_of_signal_is_an_unavailable_input_not_a_provider_failure() -> None:
    signal = FactsNotAvailableAsOf("first annual report on 2020-02-01; set an override")

    for result in (
        _resolver({FinancialField.EPS: signal}).resolve(_make_request(), use_cache=False),
        _resolver({FinancialField.EPS: signal}).resolve_three_year_average_eps(_c2c_request(), use_cache=False),
    ):
        assert result.status is CalculationStatus.INPUT_UNAVAILABLE
        assert result.provider_failure is None
        assert result.reason == "first annual report on 2020-02-01; set an override"
        assert result.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
