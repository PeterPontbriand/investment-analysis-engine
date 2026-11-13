"""The boundary check and the quality check give plain messages that name no rule identifier (issue 250)."""

from __future__ import annotations

from datetime import UTC, datetime

from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind
from investment_analysis_engine.data.financial.quality import financial_quality_error
from investment_analysis_engine.data.financial.resolver import _boundary_error
from investment_analysis_engine.data.quality import FreshnessPolicy, QualityContext, QualityOutcome, evaluate_freshness

EARLIER = datetime(2025, 1, 10, 9, 0, tzinfo=UTC)
AS_OF = datetime(2025, 3, 1, 12, 0, tzinfo=UTC)


def _request(as_of: datetime | None) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ABC",
        field_name=FinancialField.EPS,
        provider_id="sec_edgar",
        as_of=as_of,
        observation_count=1,
    )


def _fact(available_at: datetime | None) -> ProviderFact:
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ABC",
        field_name=FinancialField.EPS,
        value=4.5,
        units=FinancialUnit.CURRENCY_PER_SHARE,
        provider_id="sec_edgar",
        provider_field="EarningsPerShareDiluted",
        retrieved_at=EARLIER,
        currency="USD",
        available_at=available_at,
    )


def test_a_value_with_no_availability_date_is_explained_in_plain_words() -> None:
    assert _boundary_error(_request(AS_OF), _fact(None)) == (
        "The provider gave no date when this value became public, which an as-of analysis needs."
    )


def test_a_value_public_after_the_as_of_date_names_both_dates() -> None:
    available = datetime(2025, 3, 5, 8, 30, tzinfo=UTC)
    assert _boundary_error(_request(AS_OF), _fact(available)) == (
        "This value became public on 2025-03-05, after the as-of date 2025-03-01."
    )


def test_a_value_public_later_on_the_as_of_day_names_both_moments() -> None:
    available = datetime(2025, 3, 1, 18, 0, tzinfo=UTC)
    assert _boundary_error(_request(AS_OF), _fact(available)) == (
        "This value became public at 2025-03-01T18:00:00+00:00, after the as-of time 2025-03-01T12:00:00+00:00."
    )


def test_a_value_public_by_the_as_of_date_and_a_current_request_have_no_boundary_error() -> None:
    assert _boundary_error(_request(AS_OF), _fact(EARLIER)) is None
    assert _boundary_error(_request(None), _fact(None)) is None


def test_no_boundary_message_names_an_internal_identifier() -> None:
    for message in (
        _boundary_error(_request(AS_OF), _fact(None)),
        _boundary_error(_request(AS_OF), _fact(datetime(2025, 3, 5, tzinfo=UTC))),
        _boundary_error(_request(AS_OF), _fact(datetime(2025, 3, 1, 18, tzinfo=UTC))),
    ):
        assert message is not None
        assert "available_at" not in message
        assert "as_of" not in message


def test_a_failed_quality_rule_gives_its_reason_alone() -> None:
    fact = _fact(datetime(2025, 3, 5, tzinfo=UTC))
    decisions = evaluate_freshness(
        context=QualityContext("ABC:eps", AS_OF, analysis_as_of=AS_OF, retrieved_at=fact.retrieved_at),
        policy=FreshnessPolicy(cache_ttl=None),
        cached_at=None,
        observed_at=None,
        available_at=fact.available_at,
    )
    failed = [decision for decision in decisions if decision.outcome is QualityOutcome.FAIL]
    assert failed, "the fact must fail a quality rule for this test to mean anything"

    error = financial_quality_error(fact, input_id="ABC:eps", now=AS_OF, as_of=AS_OF)

    assert error == failed[0].reason
    assert not error.startswith(f"{failed[0].rule_id}:")


def test_every_financial_field_has_a_plain_label_that_names_no_identifier() -> None:
    from investment_analysis_engine.data.financial.facts import FINANCIAL_FIELD_LABELS  # noqa: PLC0415

    assert set(FINANCIAL_FIELD_LABELS) == set(FinancialField)
    for field, label in FINANCIAL_FIELD_LABELS.items():
        assert label.strip()
        assert "_" not in label, field


def test_a_quote_timing_message_names_the_problem_in_plain_words() -> None:
    from investment_analysis_engine.data.financial.quote_freshness import quote_timing_message  # noqa: PLC0415

    assert (
        quote_timing_message("future_timestamp")
        == "Quote response timing is unusable: the quote is dated in the future."
    )
    assert quote_timing_message("unknown_retrieval_time") == (
        "Quote response timing is unusable: the time the quote was retrieved is unknown."
    )
