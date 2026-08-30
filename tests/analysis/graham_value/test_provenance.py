"""Tests for src.data.financial.provenance models."""

from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan

import pytest

from src.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    ComponentLineage,
    FinancialSubjectKind,
    PeriodKind,
    ResolvedInput,
    SourceKind,
)

AW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)  # aware
NAIVE = datetime(2025, 6, 1, 12, 0)  # naive


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


def test_subject_kind_members() -> None:
    assert FinancialSubjectKind.SECURITY.value == "security"
    assert FinancialSubjectKind.MACRO.value == "macro"
    assert len(list(FinancialSubjectKind)) == 2


def test_source_kind_members() -> None:
    assert SourceKind.OVERRIDE.value == "override"
    assert SourceKind.CACHE.value == "cache"
    assert SourceKind.PROVIDER.value == "provider"
    assert SourceKind.DERIVED.value == "derived"
    assert len(list(SourceKind)) == 4


def test_annual_metadata_enum_members() -> None:
    assert PeriodKind.COMPLETED_ANNUAL.value == "completed_annual"
    assert AccountingScope.CONSOLIDATED.value == "consolidated"
    assert CapitalExpenditureSign.POSITIVE_EXPENDITURE.value == "positive_expenditure"
    assert CapitalExpenditureSign.NEGATIVE_CASH_OUTFLOW.value == "negative_cash_outflow"


# ---------------------------------------------------------------------------
# ComponentLineage tests
# ---------------------------------------------------------------------------


def _make_provided_input(**kwargs: object) -> ResolvedInput:
    defaults: dict[str, object] = {
        "field_name": "eps",
        "value": 5.0,
        "source_kind": SourceKind.PROVIDER,
        "resolved_at": AW,
        "provider_id": "fixture",
    }
    defaults.update(kwargs)
    return ResolvedInput(**defaults)  # type: ignore[arg-type]


def test_lineage_single_component() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    assert lineage.transformation == "mean"
    assert lineage.components == (comp,)


def test_lineage_three_components() -> None:
    c1 = _make_provided_input(field_name="a")
    c2 = _make_provided_input(field_name="b")
    c3 = _make_provided_input(field_name="c")
    lineage = ComponentLineage(transformation="sum", components=(c1, c2, c3))
    assert len(lineage.components) == 3
    assert lineage.components[0].field_name == "a"
    assert lineage.components[2].field_name == "c"


def test_lineage_empty_transformation_rejected() -> None:
    comp = _make_provided_input()
    with pytest.raises(ValueError, match="transformation"):
        ComponentLineage(transformation="", components=(comp,))


def test_lineage_whitespace_transformation_rejected() -> None:
    comp = _make_provided_input()
    with pytest.raises(ValueError, match="transformation"):
        ComponentLineage(transformation="   ", components=(comp,))


def test_lineage_empty_components_rejected() -> None:
    with pytest.raises(ValueError, match="components"):
        ComponentLineage(transformation="mean", components=())


def test_lineage_frozen() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    with pytest.raises(AttributeError):
        lineage.transformation = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResolvedInput — valid construction
# ---------------------------------------------------------------------------


def test_full_construction() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=4.2,
        source_kind=SourceKind.PROVIDER,
        resolved_at=AW,
        provider_id="yfinance",
        provider_field="trailingEps",
        basis="ttm",
        units="USD per share",
        currency="USD",
        observation_period_start=datetime(2024, 7, 1, tzinfo=UTC),
        observation_period_end=datetime(2025, 6, 30, tzinfo=UTC),
        observed_at=datetime(2025, 5, 15, tzinfo=UTC),
        available_at=datetime(2025, 5, 16, tzinfo=UTC),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
        retrieved_at=datetime(2025, 5, 15, 10, 30, tzinfo=UTC),
        notes=("from fixture",),
    )
    assert ri.field_name == "eps"
    assert ri.value == 4.2
    assert ri.source_kind is SourceKind.PROVIDER
    assert ri.provider_id == "yfinance"
    assert ri.basis == "ttm"
    assert ri.notes == ("from fixture",)


def test_minimum_construction() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=AW,
    )
    assert ri.origin_source_kind is None
    assert ri.basis is None
    assert ri.provider_id is None
    assert ri.notes == ()


def test_resolved_input_frozen() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=AW,
    )
    with pytest.raises(AttributeError):
        ri.value = 99.0  # type: ignore[misc]


def test_notes_immutable() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=AW,
        notes=("a", "b"),
    )
    with pytest.raises(TypeError):
        ri.notes[0] = "x"  # type: ignore[index]


# ---------------------------------------------------------------------------
# ResolvedInput — general invariants
# ---------------------------------------------------------------------------


def test_naive_resolved_at_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=NAIVE,
        )


def test_naive_available_at_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            available_at=NAIVE,
        )


def test_naive_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            as_of=NAIVE,
        )


def test_non_finite_nan_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ResolvedInput(
            field_name="eps",
            value=nan,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
        )


def test_non_finite_inf_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ResolvedInput(
            field_name="eps",
            value=inf,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
        )


def test_empty_field_name_rejected() -> None:
    with pytest.raises(ValueError, match="field_name"):
        ResolvedInput(
            field_name="",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
        )


def test_whitespace_field_name_rejected() -> None:
    with pytest.raises(ValueError, match="field_name"):
        ResolvedInput(
            field_name="   ",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
        )


# ---------------------------------------------------------------------------
# ResolvedInput — PROVIDER invariants
# ---------------------------------------------------------------------------


def test_provider_without_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.PROVIDER,
            resolved_at=AW,
        )


def test_provider_with_empty_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.PROVIDER,
            resolved_at=AW,
            provider_id="  ",
        )


def test_provider_with_origin_source_rejected() -> None:
    with pytest.raises(ValueError, match="origin_source_kind"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.PROVIDER,
            resolved_at=AW,
            provider_id="fixture",
            origin_source_kind=SourceKind.PROVIDER,
        )


def test_provider_with_schema_version_rejected() -> None:
    with pytest.raises(ValueError, match="cache_schema_version"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.PROVIDER,
            resolved_at=AW,
            provider_id="fixture",
            cache_schema_version=1,
        )


def test_provider_with_lineage_rejected() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    with pytest.raises(ValueError, match="lineage"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.PROVIDER,
            resolved_at=AW,
            provider_id="fixture",
            lineage=lineage,
        )


# ---------------------------------------------------------------------------
# ResolvedInput — OVERRIDE invariants
# ---------------------------------------------------------------------------


def test_override_with_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            provider_id="fixture",
        )


def test_override_with_provider_field_rejected() -> None:
    with pytest.raises(ValueError, match="provider_field"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            provider_field="trailingEps",
        )


def test_override_with_origin_source_rejected() -> None:
    with pytest.raises(ValueError, match="origin_source_kind"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            origin_source_kind=SourceKind.PROVIDER,
        )


def test_override_with_schema_version_rejected() -> None:
    with pytest.raises(ValueError, match="cache_schema_version"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            cache_schema_version=1,
        )


def test_override_with_lineage_rejected() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    with pytest.raises(ValueError, match="lineage"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            lineage=lineage,
        )


# ---------------------------------------------------------------------------
# ResolvedInput — DERIVED invariants
# ---------------------------------------------------------------------------


def test_derived_with_lineage() -> None:
    c1 = _make_provided_input(field_name="a")
    c2 = _make_provided_input(field_name="b")
    lineage = ComponentLineage(transformation="mean", components=(c1, c2))
    ri = ResolvedInput(
        field_name="avg_eps",
        value=3.0,
        source_kind=SourceKind.DERIVED,
        resolved_at=AW,
        lineage=lineage,
    )
    assert ri.lineage is not None
    assert ri.lineage.transformation == "mean"
    assert len(ri.lineage.components) == 2


def test_derived_without_lineage_rejected() -> None:
    with pytest.raises(ValueError, match="lineage"):
        ResolvedInput(
            field_name="avg_eps",
            value=3.0,
            source_kind=SourceKind.DERIVED,
            resolved_at=AW,
        )


def test_derived_with_origin_source_rejected() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    with pytest.raises(ValueError, match="origin_source_kind"):
        ResolvedInput(
            field_name="avg_eps",
            value=3.0,
            source_kind=SourceKind.DERIVED,
            resolved_at=AW,
            lineage=lineage,
            origin_source_kind=SourceKind.PROVIDER,
        )


def test_derived_with_schema_version_rejected() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    with pytest.raises(ValueError, match="cache_schema_version"):
        ResolvedInput(
            field_name="avg_eps",
            value=3.0,
            source_kind=SourceKind.DERIVED,
            resolved_at=AW,
            lineage=lineage,
            cache_schema_version=1,
        )


# ---------------------------------------------------------------------------
# ResolvedInput — CACHE invariants
# ---------------------------------------------------------------------------


def test_cache_valid_provider_origin() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=4.2,
        source_kind=SourceKind.CACHE,
        resolved_at=AW,
        origin_source_kind=SourceKind.PROVIDER,
        cache_schema_version=1,
        provider_id="yfinance",
    )
    assert ri.source_kind is SourceKind.CACHE
    assert ri.origin_source_kind is SourceKind.PROVIDER


def test_cache_valid_derived_origin() -> None:
    c1 = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(c1,))
    ri = ResolvedInput(
        field_name="avg_eps",
        value=3.0,
        source_kind=SourceKind.CACHE,
        resolved_at=AW,
        origin_source_kind=SourceKind.DERIVED,
        cache_schema_version=2,
        lineage=lineage,
    )
    assert ri.lineage is not None


def test_cache_without_origin_rejected() -> None:
    with pytest.raises(ValueError, match="origin_source_kind"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            cache_schema_version=1,
        )


def test_cache_origin_cache_rejected() -> None:
    with pytest.raises(ValueError, match="PROVIDER or DERIVED"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.CACHE,
            cache_schema_version=1,
        )


def test_cache_origin_override_rejected() -> None:
    with pytest.raises(ValueError, match="PROVIDER or DERIVED"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.OVERRIDE,
            cache_schema_version=1,
        )


def test_cache_without_schema_version_rejected() -> None:
    with pytest.raises(ValueError, match="cache_schema_version"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.PROVIDER,
            provider_id="fixture",
        )


def test_cache_zero_schema_version_rejected() -> None:
    with pytest.raises(ValueError, match="cache_schema_version"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.PROVIDER,
            provider_id="fixture",
            cache_schema_version=0,
        )


def test_cache_provider_origin_without_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.PROVIDER,
            cache_schema_version=1,
        )


def test_cache_provider_origin_with_empty_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.PROVIDER,
            provider_id="  ",
            cache_schema_version=1,
        )


def test_cache_derived_origin_without_lineage_rejected() -> None:
    with pytest.raises(ValueError, match="lineage"):
        ResolvedInput(
            field_name="avg_eps",
            value=3.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.DERIVED,
            cache_schema_version=1,
        )


def test_cache_provider_origin_with_lineage_rejected() -> None:
    comp = _make_provided_input()
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    with pytest.raises(ValueError, match="lineage"):
        ResolvedInput(
            field_name="eps",
            value=1.0,
            source_kind=SourceKind.CACHE,
            resolved_at=AW,
            origin_source_kind=SourceKind.PROVIDER,
            provider_id="fixture",
            cache_schema_version=1,
            lineage=lineage,
        )


# ---------------------------------------------------------------------------
# ResolvedInput — provider_id canonicalization
# ---------------------------------------------------------------------------


def test_provider_id_canonicalization_strip_lower() -> None:
    """PROVIDER provider_id with surrounding whitespace and mixed case is canonicalized."""
    ri = ResolvedInput(
        field_name="eps",
        value=5.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=AW,
        provider_id=" YFinance ",
    )
    assert ri.provider_id == "yfinance"


def test_cache_provider_origin_id_canonicalization() -> None:
    """CACHE with PROVIDER origin canonicalizes provider_id the same way."""
    ri = ResolvedInput(
        field_name="eps",
        value=5.0,
        source_kind=SourceKind.CACHE,
        resolved_at=AW,
        origin_source_kind=SourceKind.PROVIDER,
        provider_id="  FRED  ",
        cache_schema_version=1,
    )
    assert ri.provider_id == "fred"


def test_provider_id_already_canonicalized_unchanged() -> None:
    """A provider_id that is already lowercase and stripped passes through unchanged."""
    ri = ResolvedInput(
        field_name="eps",
        value=5.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=AW,
        provider_id="yfinance",
    )
    assert ri.provider_id == "yfinance"


def test_override_provider_id_not_canonicalized() -> None:
    """OVERRIDE source rejects provider_id (must be None), so no canonicalization applies."""
    with pytest.raises(ValueError, match="provider_id"):
        ResolvedInput(
            field_name="eps",
            value=5.0,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=AW,
            provider_id="  whatever  ",
        )


# ---------------------------------------------------------------------------
# ResolvedInput — lineage self-consistency
# ---------------------------------------------------------------------------


def test_lineage_empty_transformation_via_input_rejected() -> None:
    """ComponentLineage raises before ResolvedInput is ever reached."""
    comp = _make_provided_input()
    with pytest.raises(ValueError, match="transformation"):
        ComponentLineage(transformation="", components=(comp,))


def test_lineage_empty_components_via_input_rejected() -> None:
    """ComponentLineage raises before ResolvedInput is ever reached."""
    with pytest.raises(ValueError, match="components"):
        ComponentLineage(transformation="mean", components=())


def test_completed_annual_metadata_is_preserved_and_normalized() -> None:
    ri = _make_provided_input(
        field_name="capital_expenditures",
        fiscal_year=2025,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        capital_expenditure_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE,
        provider_fact_id="  fact-2025  ",
    )
    assert ri.fiscal_year == 2025
    assert ri.period_kind is PeriodKind.COMPLETED_ANNUAL
    assert ri.accounting_scope is AccountingScope.CONSOLIDATED
    assert ri.provider_fact_id == "fact-2025"


def test_resolved_input_fiscal_year_requires_completed_annual_kind() -> None:
    with pytest.raises(ValueError, match="completed_annual"):
        _make_provided_input(fiscal_year=2025, period_kind=PeriodKind.QUARTERLY)


def test_resolved_input_nonpositive_fiscal_year_rejected() -> None:
    with pytest.raises(ValueError, match="positive year label"):
        _make_provided_input(fiscal_year=0, period_kind=PeriodKind.COMPLETED_ANNUAL)


def test_resolved_input_capex_sign_rejected_for_other_field() -> None:
    with pytest.raises(ValueError, match="only applicable"):
        _make_provided_input(
            capital_expenditure_sign=CapitalExpenditureSign.NEGATIVE_CASH_OUTFLOW,
        )
