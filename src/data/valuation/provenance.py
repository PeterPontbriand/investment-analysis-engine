"""Provenance models for resolved valuation inputs.

Defines the subject and source discriminators, component lineage, and the
frozen ``ResolvedInput`` record that carries a single resolved numeric value
with full temporal and provenance metadata.

All models are frozen.  Every ``datetime`` field, when present, must be
timezone-aware; naive datetimes raise ``ValueError`` at construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _require_timezone_aware(dt: datetime, *, field_name: str) -> None:
    """Raise ``ValueError`` if *dt* is not timezone-aware."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        msg = f"{field_name} must be timezone-aware (received {dt!r})."
        raise ValueError(msg)


def _require_finite(value: float, *, field_name: str) -> None:
    """Raise ``ValueError`` if *value* is not finite."""
    if not math.isfinite(value):
        msg = f"{field_name} must be finite (received {value!r})."
        raise ValueError(msg)


def _require_non_empty(text: str, *, field_name: str) -> None:
    """Raise ``ValueError`` if *text* is empty or whitespace-only."""
    if not text.strip():
        msg = f"{field_name} must be a non-empty string."
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ValuationSubjectKind(StrEnum):
    """Discriminator for the subject of a valuation fact."""

    SECURITY = "security"
    MACRO = "macro"


class SourceKind(StrEnum):
    """How a resolved input value was obtained."""

    OVERRIDE = "override"
    CACHE = "cache"
    PROVIDER = "provider"
    DERIVED = "derived"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentLineage:
    """Describes how a derived value was composed from component inputs.

    Attributes:
        transformation: Non-empty human-readable description of the computation.
        components: At least one fully-provenanced ``ResolvedInput``.
    """

    transformation: str
    components: tuple[ResolvedInput, ...]

    def __post_init__(self) -> None:
        """Validate transformation and components."""
        _require_non_empty(self.transformation, field_name="transformation")
        if len(self.components) < 1:
            msg = "ComponentLineage.components must contain at least one element."
            raise ValueError(msg)


@dataclass(frozen=True)
class ResolvedInput:
    """A successfully resolved numeric input with full provenance.

    Represents a *valid* resolved value — not an unvalidated provider payload.
    All temporal fields must be timezone-aware.

    Attributes:
        field_name: Non-empty semantic input name.
        value: Finite numeric value.
        source_kind: How this value was resolved.
        origin_source_kind: Required when ``source_kind`` is ``CACHE``; the
            original source kind of the cached fact.
        basis: Measurement/variant label (e.g. ``"ttm"``, ``"three_year_average"``).
        units: Unit label (e.g. ``"USD per share"``).
        currency: ISO 4217 code when monetary.
        provider_id: Provider identifier (e.g. ``"yfinance"``, ``"fred"``).
        provider_field: Exact upstream field or series identifier.
        observation_period_start: Timezone-aware start of a reporting period.
        observation_period_end: Timezone-aware end of a reporting period.
        observed_at: Timezone-aware point-observation timestamp.
        available_at: Timezone-aware time when fact became publicly knowable.
        as_of: Timezone-aware requested analysis boundary (None = current).
        retrieved_at: Timezone-aware original provider/fixture fetch time.
        resolved_at: Timezone-aware resolution-operation time (always required).
        cache_schema_version: Required when ``source_kind`` is ``CACHE``.
        lineage: Required when ``source_kind`` is ``DERIVED`` or when
            ``origin_source_kind`` is ``DERIVED``.
        notes: Immutable additional provenance annotations.
    """

    field_name: str
    value: float
    source_kind: SourceKind
    resolved_at: datetime
    origin_source_kind: SourceKind | None = None
    basis: str | None = None
    units: str | None = None
    currency: str | None = None
    provider_id: str | None = None
    provider_field: str | None = None
    observation_period_start: datetime | None = None
    observation_period_end: datetime | None = None
    observed_at: datetime | None = None
    available_at: datetime | None = None
    as_of: datetime | None = None
    retrieved_at: datetime | None = None
    cache_schema_version: int | None = None
    lineage: ComponentLineage | None = None
    notes: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        """Validate all invariants for this ResolvedInput."""
        # Canonicalize provider_id when the source is PROVIDER or CACHE with
        # PROVIDER origin (strip whitespace, lowercase).
        if self.provider_id is not None and (
            self.source_kind is SourceKind.PROVIDER
            or (self.source_kind is SourceKind.CACHE and self.origin_source_kind is SourceKind.PROVIDER)
        ):
            object.__setattr__(self, "provider_id", self.provider_id.strip().lower())
        self._validate()

    def _validate(self) -> None:
        """Validate all invariants for this ResolvedInput."""
        _validate_general_invariants(self)
        _validate_source_kind(self)
        _validate_lineage_consistency(self)


def _validate_general_invariants(ri: ResolvedInput) -> None:
    """Validate general invariants: field_name, value, and all datetimes."""
    _require_non_empty(ri.field_name, field_name="field_name")
    _require_finite(ri.value, field_name="value")
    _require_timezone_aware(ri.resolved_at, field_name="resolved_at")

    _validate_optional_datetime(ri.observation_period_start, "observation_period_start")
    _validate_optional_datetime(ri.observation_period_end, "observation_period_end")
    _validate_optional_datetime(ri.observed_at, "observed_at")
    _validate_optional_datetime(ri.available_at, "available_at")
    _validate_optional_datetime(ri.as_of, "as_of")
    _validate_optional_datetime(ri.retrieved_at, "retrieved_at")


def _validate_source_kind(ri: ResolvedInput) -> None:
    """Validate per-source_kind invariants."""
    if ri.source_kind is SourceKind.PROVIDER:
        _validate_provider(ri)
    elif ri.source_kind is SourceKind.OVERRIDE:
        _validate_override(ri)
    elif ri.source_kind is SourceKind.DERIVED:
        _validate_derived(ri)
    elif ri.source_kind is SourceKind.CACHE:
        _validate_cache(ri)


def _validate_provider(ri: ResolvedInput) -> None:
    """Validate PROVIDER source invariants."""
    if ri.provider_id is None or not ri.provider_id.strip():
        msg = "PROVIDER source requires a non-empty provider_id."
        raise ValueError(msg)
    if ri.origin_source_kind is not None:
        msg = "PROVIDER source requires origin_source_kind to be None."
        raise ValueError(msg)
    if ri.cache_schema_version is not None:
        msg = "PROVIDER source requires cache_schema_version to be None."
        raise ValueError(msg)
    if ri.lineage is not None:
        msg = "PROVIDER source requires lineage to be None."
        raise ValueError(msg)


def _validate_override(ri: ResolvedInput) -> None:
    """Validate OVERRIDE source invariants."""
    if ri.provider_id is not None:
        msg = "OVERRIDE source requires provider_id to be None."
        raise ValueError(msg)
    if ri.provider_field is not None:
        msg = "OVERRIDE source requires provider_field to be None."
        raise ValueError(msg)
    if ri.origin_source_kind is not None:
        msg = "OVERRIDE source requires origin_source_kind to be None."
        raise ValueError(msg)
    if ri.cache_schema_version is not None:
        msg = "OVERRIDE source requires cache_schema_version to be None."
        raise ValueError(msg)
    if ri.lineage is not None:
        msg = "OVERRIDE source requires lineage to be None."
        raise ValueError(msg)


def _validate_derived(ri: ResolvedInput) -> None:
    """Validate DERIVED source invariants."""
    if ri.lineage is None:
        msg = "DERIVED source requires lineage to be present."
        raise ValueError(msg)
    if ri.origin_source_kind is not None:
        msg = "DERIVED source requires origin_source_kind to be None."
        raise ValueError(msg)
    if ri.cache_schema_version is not None:
        msg = "DERIVED source requires cache_schema_version to be None."
        raise ValueError(msg)


def _validate_cache(ri: ResolvedInput) -> None:
    """Validate CACHE source invariants."""
    if ri.origin_source_kind is None:
        msg = "CACHE source requires origin_source_kind to be present."
        raise ValueError(msg)
    if ri.origin_source_kind is SourceKind.CACHE or ri.origin_source_kind is SourceKind.OVERRIDE:
        msg = f"CACHE source origin must be PROVIDER or DERIVED, not {ri.origin_source_kind}."
        raise ValueError(msg)
    if ri.cache_schema_version is None or ri.cache_schema_version <= 0:
        msg = "CACHE source requires cache_schema_version to be a positive integer."
        raise ValueError(msg)
    if ri.origin_source_kind is SourceKind.DERIVED:
        if ri.lineage is None:
            msg = "CACHE source with DERIVED origin requires lineage to be present."
            raise ValueError(msg)
    elif ri.origin_source_kind is SourceKind.PROVIDER:
        if ri.provider_id is None or not ri.provider_id.strip():
            msg = "CACHE source with PROVIDER origin requires a non-empty provider_id."
            raise ValueError(msg)
        if ri.lineage is not None:
            msg = "CACHE source with PROVIDER origin requires lineage to be None."
            raise ValueError(msg)


def _validate_lineage_consistency(ri: ResolvedInput) -> None:
    """Validate lineage self-consistency if present."""
    if ri.lineage is None:
        return
    if not ri.lineage.transformation.strip():
        msg = "Lineage transformation must be non-empty."
        raise ValueError(msg)
    if len(ri.lineage.components) < 1:
        msg = "Lineage components must contain at least one element."
        raise ValueError(msg)


def _validate_optional_datetime(dt: datetime | None, field_name: str) -> None:
    """Validate an optional datetime field is timezone-aware if present."""
    if dt is not None:
        _require_timezone_aware(dt, field_name=field_name)
