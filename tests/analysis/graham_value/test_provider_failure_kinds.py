"""The resolver and the Graham assemblies store the kind and provider of a provider failure.

A typed failure raised by a provider is carried onto the stored resolution; a provider answer the project rejects is
an ``unexpected_response`` from the provider the request named; anything that is not a typed provider failure
propagates.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import pytest

from src.core.analysis_status import CalculationStatus
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import FinancialSubjectKind
from src.data.financial.resolver import InputResolutionResult, InputResolver
from src.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from src.strategies.graham_number.calculation import GrahamNumberInputResolver
from tests.analysis.graham_value.test_resolver import (
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

_FAILED = {ProviderFailureKind.UNREACHABLE, ProviderFailureKind.UNEXPECTED_RESPONSE, ProviderFailureKind.NO_DATA}


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


def _error(kind: ProviderFailureKind | None) -> FinancialProviderError:
    if kind is None:
        return FinancialProviderError("synthetic failure")
    return FinancialProviderError("synthetic failure", kind=kind, provider_id=PROVIDER_ID)


def _resolver(answers: dict[FinancialField, Any]) -> InputResolver:
    return InputResolver(_Provider(answers), clock=lambda: NOW)


def _record(kind: ProviderFailureKind) -> ProviderFailureRecord:
    return ProviderFailureRecord(kind=kind, provider_id=PROVIDER_ID)


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
    candidates = tuple(replace(fact, basis="ttm") for fact in _three_fy_facts())

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


@pytest.mark.parametrize(
    "failed",
    [
        FinancialField.STOCKHOLDERS_EQUITY,
        FinancialField.COMMON_SHARES_OUTSTANDING,
        FinancialField.PREFERRED_SHARES_OUTSTANDING,
    ],
)
@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_a_component_failure_passes_its_kind_through_the_bvps_derivation(
    failed: FinancialField, kind: ProviderFailureKind
) -> None:
    answers = _components(100.0, 10.0) | {failed: _error(kind)}

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.provider_failure == _record(kind)
    assert failed.value in (result.reason or "")


def test_a_non_finite_bvps_quotient_is_reachable_from_finite_components() -> None:
    answers = _components(1e300, 1e-10)

    result = _resolver(answers).resolve_bvps(_bvps_request(), use_cache=False)

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert "non-finite" in (result.reason or "")
    assert result.provider_failure == _record(ProviderFailureKind.UNEXPECTED_RESPONSE)


# --- the Graham assemblies record the failure against the input ---------------------------------------------------


def _number_assembly(answers: dict[FinancialField, Any]) -> Any:
    resolver = GrahamNumberInputResolver(_Provider(answers), clock=lambda: NOW)
    return resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        use_cache=False,
    )


def _growth_assembly(answers: dict[FinancialField, Any]) -> Any:
    resolver = GrahamGrowthInputResolver(_Provider(answers), clock=lambda: NOW)
    return resolver.assemble_growth_value(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        expected_growth=5.0,
        aaa_subject_id="AAA",
        aaa_provider_id=PROVIDER_ID,
        use_cache=False,
    )


@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_graham_number_records_the_failed_input(kind: ProviderFailureKind) -> None:
    eps = _number_assembly({FinancialField.EPS: _error(kind)})
    bvps = _number_assembly({FinancialField.EPS: (_make_fact(basis="ttm"),), FinancialField.BVPS: _error(kind)})

    assert eps.status is CalculationStatus.PROVIDER_ERROR
    assert eps.provider_failure == _record(kind).for_input("eps")
    assert bvps.status is CalculationStatus.PROVIDER_ERROR
    assert bvps.provider_failure == _record(kind).for_input("bvps")


@pytest.mark.parametrize("kind", sorted(_FAILED))
def test_graham_growth_records_the_failed_input(kind: ProviderFailureKind) -> None:
    eps = _growth_assembly({FinancialField.EPS: _error(kind)})
    aaa = _growth_assembly(
        {FinancialField.EPS: (_make_fact(basis="ttm"),), FinancialField.CURRENT_AAA_YIELD: _error(kind)}
    )

    assert eps.provider_failure == _record(kind).for_input("eps")
    assert aaa.status is CalculationStatus.PROVIDER_ERROR
    assert aaa.provider_failure == _record(kind).for_input("current_aaa_yield")


def test_a_non_failing_assembly_stores_no_failure() -> None:
    assembly = _number_assembly({FinancialField.EPS: (_make_fact(basis="ttm"),)})

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
