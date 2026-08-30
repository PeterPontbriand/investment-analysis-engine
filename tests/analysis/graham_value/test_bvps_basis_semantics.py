"""Focused regression tests for Graham Number BVPS basis semantics."""

from __future__ import annotations

from datetime import UTC, datetime

from src.analysis.graham_value.input_resolver import _with_semantic_bvps_basis
from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind

NOW = datetime(2026, 8, 24, 2, 50, tzinfo=UTC)


def _component(
    field_name: str,
    value: float,
    *,
    basis: str,
    units: str,
    currency: str | None,
) -> ResolvedInput:
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis=basis,
        units=units,
        currency=currency,
        provider_id="sec_edgar",
        provider_field=f"test:{field_name}",
        observation_period_end=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        available_at=NOW,
        retrieved_at=NOW,
    )


def _derived_bvps(*, component_basis: str = "fiscal_year_end") -> ResolvedInput:
    equity = _component(
        "stockholders_equity",
        100.0,
        basis=component_basis,
        units="currency",
        currency="USD",
    )
    preferred = _component(
        "preferred_shares_outstanding",
        0.0,
        basis=component_basis,
        units="shares",
        currency=None,
    )
    common = _component(
        "common_shares_outstanding",
        10.0,
        basis=component_basis,
        units="shares",
        currency=None,
    )
    return ResolvedInput(
        field_name="bvps",
        value=10.0,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        observation_period_end=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        available_at=NOW,
        retrieved_at=NOW,
        lineage=ComponentLineage(
            transformation="stockholders_equity / common_shares_outstanding",
            components=(equity, preferred, common),
        ),
    )


def test_period_end_derived_bvps_receives_semantic_basis() -> None:
    result = _with_semantic_bvps_basis(_derived_bvps())

    assert result.basis == "fiscal_year_end"
    assert result.source_kind is SourceKind.DERIVED
    assert result.lineage is not None


def test_unknown_derived_bvps_basis_is_not_invented() -> None:
    result = _with_semantic_bvps_basis(_derived_bvps(component_basis="other_basis"))

    assert result.basis is None
