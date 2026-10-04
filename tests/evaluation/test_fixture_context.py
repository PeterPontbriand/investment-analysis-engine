"""Focused checks for the cross-strategy fixture context and the shared requirement check."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.evaluation.fixture_context import (
    SUPPORTED_FIXTURE_IDS,
    FixtureCompositionError,
    FixtureContext,
    FixtureRequirement,
    SharedKey,
    build_fixture_context,
    profile_resolver,
    require_fixture_evidence,
    selected_variant,
    validate_clock,
)
from src.evaluation.fixture_ids import (
    GRAHAM_FACTS_FIXTURE_ID,
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.instrument_profiles import GOLDEN_ETF_TICKER
from src.evaluation.fixtures.sec_edgar_fpi import (
    SEC_FPI_ASML_FIXTURE_ID,
    SEC_FPI_FIXTURE_IDS,
    SEC_FPI_NTR_FIXTURE_ID,
    SEC_FPI_NVO_FIXTURE_ID,
)
from src.evaluation.models import Case, Expectation

EXECUTION_TIME = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
_REQUIREMENT = FixtureRequirement(frozenset({GRAHAM_FACTS_FIXTURE_ID}), "Sample", etf_profile_exempt=True)


def _case(*fixture_ids: str) -> Case:
    """Build a small supplied case."""
    return Case(
        case_id="context-case",
        description="Synthetic fixture-context case.",
        task="Build the fixture context.",
        fixture_ids=fixture_ids,
        expectation=Expectation(),
    )


def test_the_context_holds_only_cross_strategy_state() -> None:
    """The context carries the ids, the clock and the SEC FPI provider; no strategy-specific selection."""
    context = build_fixture_context(_case(MOMENTUM_SUCCESS_FIXTURE_ID), clock_at=EXECUTION_TIME)
    assert isinstance(context, FixtureContext)
    assert context.fixture_ids == {MOMENTUM_SUCCESS_FIXTURE_ID}
    assert context.clock_at == EXECUTION_TIME
    assert context.sec_fpi_provider is None
    assert {name for name in FixtureContext.__dataclass_fields__ if not name.startswith("_")} == {
        "fixture_ids",
        "clock_at",
        "sec_fpi_provider",
    }


def test_a_selected_sec_fpi_fixture_builds_the_frozen_provider() -> None:
    """Foreign-private-issuer evidence is built once and shared through the context."""
    context = build_fixture_context(_case(SEC_FPI_ASML_FIXTURE_ID), clock_at=EXECUTION_TIME)
    assert context.sec_fpi_provider is not None


@pytest.mark.parametrize(
    ("fixture_ids", "message"),
    [
        (("unknown_fixture",), "Unsupported fixture IDs: unknown_fixture."),
        (
            (SEC_FPI_ASML_FIXTURE_ID, SEC_FPI_NTR_FIXTURE_ID),
            "Conflicting SEC FPI evidence fixture IDs: sec_fpi_asml_us_gaap_20f, sec_fpi_ntr_ifrs.",
        ),
    ],
)
def test_unsupported_or_conflicting_shared_evidence_fails_closed(fixture_ids: tuple[str, ...], message: str) -> None:
    """The builder rejects identifiers no composition serves and ambiguous shared evidence."""
    with pytest.raises(FixtureCompositionError) as raised:
        build_fixture_context(_case(*fixture_ids), clock_at=EXECUTION_TIME)
    assert str(raised.value) == message


def test_a_naive_clock_is_rejected_before_any_fixture_is_read() -> None:
    """The clock is validated first, so an unsupported id does not mask an ambiguous clock."""
    with pytest.raises(FixtureCompositionError, match="timezone-aware"):
        build_fixture_context(_case("unknown_fixture"), clock_at=EXECUTION_TIME.replace(tzinfo=None))
    validate_clock(EXECUTION_TIME)


def test_selected_variant_returns_none_one_or_rejects_several() -> None:
    """A variant group selects at most one fixture."""
    candidates = frozenset({MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID})
    assert selected_variant(frozenset({GRAHAM_FACTS_FIXTURE_ID}), candidates, label="Momentum price") is None
    assert (
        selected_variant(frozenset({MOMENTUM_BOUNDARY_FIXTURE_ID}), candidates, label="Momentum price")
        == MOMENTUM_BOUNDARY_FIXTURE_ID
    )
    with pytest.raises(FixtureCompositionError, match="Conflicting Momentum price fixture IDs"):
        selected_variant(frozenset(candidates), candidates, label="Momentum price")


def test_every_sec_fpi_identifier_is_supported() -> None:
    """The supported set covers the identifiers whose evidence stays with the FPI fixtures."""
    assert SEC_FPI_FIXTURE_IDS <= SUPPORTED_FIXTURE_IDS


def test_the_profile_resolver_is_exact_ticker_and_absent_without_profile_evidence() -> None:
    """Only a selected profile fixture yields a resolver, and it answers for its own ticker alone."""
    assert profile_resolver(build_fixture_context(_case(GRAHAM_FACTS_FIXTURE_ID), clock_at=EXECUTION_TIME)) is None

    etf = profile_resolver(build_fixture_context(_case(KNOWN_ETF_PROFILE_FIXTURE_ID), clock_at=EXECUTION_TIME))
    assert etf is not None
    assert etf(f" {GOLDEN_ETF_TICKER.lower()} ").ticker == GOLDEN_ETF_TICKER
    with pytest.raises(FixtureCompositionError, match="cannot satisfy ticker 'OTHER'"):
        etf("other")

    nvo = profile_resolver(build_fixture_context(_case(SEC_FPI_NVO_FIXTURE_ID), clock_at=EXECUTION_TIME))
    assert nvo is not None
    assert nvo("NVO").ticker == "NVO"


def test_requirement_passes_with_a_required_identifier_and_names_its_label_otherwise() -> None:
    """A required identifier satisfies the check; its absence names the strategy's own label."""
    require_fixture_evidence(_case(GRAHAM_FACTS_FIXTURE_ID), _REQUIREMENT, ticker="SYNTH")
    with pytest.raises(FixtureCompositionError) as raised:
        require_fixture_evidence(_case(MOMENTUM_SUCCESS_FIXTURE_ID), _REQUIREMENT, ticker="SYNTH")
    assert str(raised.value) == "Case 'context-case' has no selected Sample fixture."


def test_the_etf_exemption_applies_only_when_declared_and_only_to_the_profiled_ticker() -> None:
    """Affirmative ETF evidence for the exact ticker satisfies an exempt requirement and nothing else."""
    etf_case = _case(KNOWN_ETF_PROFILE_FIXTURE_ID)
    require_fixture_evidence(etf_case, _REQUIREMENT, ticker=f" {GOLDEN_ETF_TICKER.lower()}")
    with pytest.raises(FixtureCompositionError, match="has no selected Sample fixture"):
        require_fixture_evidence(etf_case, _REQUIREMENT, ticker="SYNTH")
    not_exempt = FixtureRequirement(_REQUIREMENT.required_ids, "Sample", etf_profile_exempt=False)
    with pytest.raises(FixtureCompositionError, match="has no selected Sample fixture"):
        require_fixture_evidence(etf_case, not_exempt, ticker=GOLDEN_ETF_TICKER)


class _Marker:
    """A shared object for the memo checks."""


def test_a_shared_object_is_built_once_per_context_and_not_across_contexts() -> None:
    """Strategies of a family read the same instance within a case; a new case gets a new one."""
    key = SharedKey("marker", _Marker)
    first = build_fixture_context(_case(GRAHAM_FACTS_FIXTURE_ID), clock_at=EXECUTION_TIME)
    second = build_fixture_context(_case(GRAHAM_FACTS_FIXTURE_ID), clock_at=EXECUTION_TIME)
    built: list[_Marker] = []

    def build() -> _Marker:
        built.append(_Marker())
        return built[-1]

    assert first.shared(key, build) is first.shared(key, build)
    assert len(built) == 1
    assert second.shared(key, build) is not first.shared(key, build)
    assert len(built) == 2


def test_a_shared_name_bound_to_another_class_fails_closed() -> None:
    """A name cannot be reused for an object of a different class."""
    context = build_fixture_context(_case(GRAHAM_FACTS_FIXTURE_ID), clock_at=EXECUTION_TIME)
    context.shared(SharedKey("clash", _Marker), _Marker)
    with pytest.raises(FixtureCompositionError, match="Shared fixture 'clash' holds a _Marker, not a str"):
        context.shared(SharedKey("clash", str), lambda: "text")
