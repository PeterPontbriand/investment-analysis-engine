"""Parts that more than one strategy ``--json`` document contains.

A strategy document is one typed model in the strategy's own ``envelope.py``. The sections that several
strategies write the same way live here once: the security identity and instrument kind, a diagnostics entry,
a metric result, and the Graham family's resolved input, quote and price comparison. A section only one strategy
writes (FCF Growth's resolved input is wider than the Graham one) stays with that strategy.

Every field is required. An absent value is an explicit ``null``, never an omitted key, so a reader can tell
"absent" from "not written" and the generated schema lists every key. Instants are
:data:`~src.reporting.documents.timestamp.DocumentTimestamp`, which spells them as ``datetime.isoformat()`` does.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, WithJsonSchema

from src.analysis.shared.financial_resolution import PriceComparison
from src.core.analysis_status import CalculationStatus
from src.core.metric_result import MetricResult, MetricStatus, ReasonCode
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionTrace
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentProfile,
    InstrumentProfileDiagnostic,
)
from src.data.security_identity import IdentityResolutionStatus, SecurityIdentityResolution
from src.reporting.documents.timestamp import DocumentTimestamp

JsonNumber = Annotated[
    int | float,
    WithJsonSchema({"type": "number", "description": "A finite number, written as the source value was."}),
]
"""A number written exactly as its source holds it: an integer stays ``5``, a float stays ``5.0``.

A plain ``float`` field turns an integer into a float (``5`` into ``5.0``), which would change the bytes of a
document. Only a resolved input's ``value`` is typed this way, because a caller may construct one from an integer.
"""


class DocumentPart(BaseModel):
    """The base of every part: frozen, no undeclared keys, no NaN or infinity."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class SecurityIdentityPart(DocumentPart):
    """The identity snapshot a run retains; every descriptive field is null when the provider returned none."""

    ticker: str
    instrument_name: str | None
    listing_venue: str | None
    issuer_identifier: str | None
    instrument_identifier: str | None
    provider_id: str | None
    resolved_at: DocumentTimestamp | None


class InstrumentKindPart(DocumentPart):
    """The instrument-kind evidence a provider returned: the raw provider value and the reviewed kind it maps to."""

    kind: InstrumentKind | None
    provider_value: str
    provider_id: str
    resolved_at: DocumentTimestamp


class DiagnosticPart(DocumentPart):
    """One diagnostics entry that names no provider: a resolver event or the legacy identity entry."""

    field_name: str
    stage: str
    outcome: str
    message: str


class ProviderDiagnosticPart(DocumentPart):
    """One diagnostics entry for an instrument-profile capability, which names the provider consulted."""

    field_name: str
    stage: str
    outcome: str
    message: str
    provider_id: str


class MetricResultPart(DocumentPart):
    """One metric: its status, its value when the status is ok, and the reason it has none otherwise."""

    status: MetricStatus
    value: float | None
    reason_code: ReasonCode | None
    reason: str | None


class QuotePart(DocumentPart):
    """The optional current-quote attempt: ``ok``, ``not_attempted`` or the status of the failed lookup."""

    status: str
    reason: str | None


class ResolvedInputPart(DocumentPart):
    """One method input and where it came from, as the Graham documents write it."""

    field_name: str
    value: JsonNumber
    source_kind: SourceKind
    origin_source_kind: SourceKind | None
    basis: str | None
    units: str | None
    currency: str | None
    provider_id: str | None
    provider_field: str | None
    observation_period_start: DocumentTimestamp | None
    observation_period_end: DocumentTimestamp | None
    observed_at: DocumentTimestamp | None
    available_at: DocumentTimestamp | None
    as_of: DocumentTimestamp | None
    retrieved_at: DocumentTimestamp | None
    resolved_at: DocumentTimestamp
    cache_schema_version: int | None
    notes: tuple[str, ...]
    lineage: LineagePart | None


class LineagePart(DocumentPart):
    """How a derived input was composed from other inputs."""

    transformation: str
    components: tuple[ResolvedInputPart, ...]


class QuoteFreshnessPart(DocumentPart):
    """How recent the quote behind a price comparison was."""

    status: Literal[
        "recent_retrieval", "expired", "unknown_retrieval_time", "future_timestamp", "user_supplied", "historical"
    ]
    evaluated_at: DocumentTimestamp
    retrieved_at: DocumentTimestamp | None
    retrieval_age_seconds: float | None
    max_retrieval_age_seconds: float
    market_observed_at: DocumentTimestamp | None


class SecurityUnitEvidencePart(DocumentPart):
    """The evidence relating the filing's share unit to the quoted one."""

    ticker: str
    filing_unit_kind: str
    quoted_unit_kind: str
    underlying_shares_per_quoted_unit: float | None
    provider_id: str
    source: str


class SecurityUnitDocumentPart(DocumentPart):
    """One filing document that supports the share-unit evidence."""

    accession: str
    url: str
    context_ids: tuple[str, ...]
    available_at: DocumentTimestamp
    retrieved_at: DocumentTimestamp
    listing_venue: str | None


class SecurityUnitProvenancePart(DocumentPart):
    """The reviewed single-class inference behind the share-unit evidence."""

    mapping_id: str
    cik: str
    class_title: str
    documents: tuple[SecurityUnitDocumentPart, ...]


class PriceComparisonPart(DocumentPart):
    """The relationship between a method's value and the current price, with the evidence behind it."""

    status: Literal["available", "unavailable"]
    reason: str
    percent: float | None
    quote_freshness: QuoteFreshnessPart | None
    security_unit_evidence: SecurityUnitEvidencePart | None
    provenance: SecurityUnitProvenancePart | None


ResolvedInputPart.model_rebuild()
LineagePart.model_rebuild()

DiagnosticEntry = DiagnosticPart | ProviderDiagnosticPart
"""A diagnostics entry: the shape without a provider, or the shape with one."""


def security_identity_part(ticker: str, resolution: SecurityIdentityResolution | None) -> SecurityIdentityPart:
    """Return the identity part for ``ticker``, taken from ``resolution`` when it resolved an identity.

    Raises:
        ValueError: If the ticker is blank, or the resolved identity is for another ticker.
    """
    identity = resolution.identity if resolution is not None else None
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must be a non-empty string.")
    if identity is not None and identity.ticker != normalized:
        raise ValueError("Security identity ticker does not match the presented analysis ticker.")
    return SecurityIdentityPart(
        ticker=normalized,
        instrument_name=identity.instrument_name if identity is not None else None,
        listing_venue=identity.listing_venue if identity is not None else None,
        issuer_identifier=identity.issuer_identifier if identity is not None else None,
        instrument_identifier=identity.instrument_identifier if identity is not None else None,
        provider_id=identity.provider_id if identity is not None else None,
        resolved_at=identity.resolved_at if identity is not None else None,
    )


def instrument_kind_part(evidence: InstrumentKindEvidence | None) -> InstrumentKindPart | None:
    """Return the kind part for ``evidence``, or ``None`` when no provider returned any."""
    if evidence is None:
        return None
    return InstrumentKindPart(
        kind=evidence.kind,
        provider_value=evidence.provider_value,
        provider_id=evidence.provider_id,
        resolved_at=evidence.resolved_at,
    )


def instrument_kind_part_of(profile: InstrumentProfile | None) -> InstrumentKindPart | None:
    """Return the kind part for a profile's kind evidence, or ``None`` without a profile or evidence."""
    return instrument_kind_part(profile.kind_evidence if profile is not None else None)


def provider_diagnostic_part(item: InstrumentProfileDiagnostic) -> ProviderDiagnosticPart:
    """Return the diagnostics entry for one instrument-profile capability attempt."""
    return ProviderDiagnosticPart(
        field_name=item.capability.value,
        stage="provider",
        outcome=item.status.value,
        message=item.message,
        provider_id=item.provider_id,
    )


def profile_diagnostic_parts(profile: InstrumentProfile | None) -> list[DiagnosticEntry]:
    """Return one entry per profile capability attempt, in order; none without a profile."""
    if profile is None:
        return []
    return [provider_diagnostic_part(item) for item in profile.diagnostics]


def identity_diagnostic_parts(
    profile: InstrumentProfile | None, resolution: SecurityIdentityResolution | None
) -> list[DiagnosticEntry]:
    """Return the one legacy identity entry, only when there is no profile and the lookup did not resolve."""
    if profile is None and resolution is not None and resolution.status is not IdentityResolutionStatus.RESOLVED:
        return [
            DiagnosticPart(
                field_name="security_identity",
                stage="provider",
                outcome=resolution.status.value,
                message=resolution.message,
            )
        ]
    return []


def trace_parts(trace: ResolutionTrace) -> list[DiagnosticEntry]:
    """Return one entry per resolver event, in order."""
    return [
        DiagnosticPart(
            field_name=event.field_name, stage=event.stage.value, outcome=event.outcome.value, message=event.message
        )
        for event in trace.events
    ]


def metric_result_part(metric: MetricResult) -> MetricResultPart:
    """Return the part for one metric result."""
    return MetricResultPart(
        status=metric.status, value=metric.value, reason_code=metric.reason_code, reason=metric.reason
    )


def resolved_input_part(value: ResolvedInput | None) -> ResolvedInputPart | None:
    """Return the part for one resolved input, with its lineage nested, or ``None`` for an absent input."""
    if value is None:
        return None
    lineage = (
        None
        if value.lineage is None
        else LineagePart(
            transformation=value.lineage.transformation,
            components=tuple(
                part for component in value.lineage.components if (part := resolved_input_part(component)) is not None
            ),
        )
    )
    return ResolvedInputPart(
        field_name=value.field_name,
        value=value.value,
        source_kind=value.source_kind,
        origin_source_kind=value.origin_source_kind,
        basis=value.basis,
        units=value.units,
        currency=value.currency,
        provider_id=value.provider_id,
        provider_field=value.provider_field,
        observation_period_start=value.observation_period_start,
        observation_period_end=value.observation_period_end,
        observed_at=value.observed_at,
        available_at=value.available_at,
        as_of=value.as_of,
        retrieved_at=value.retrieved_at,
        resolved_at=value.resolved_at,
        cache_schema_version=value.cache_schema_version,
        notes=value.notes,
        lineage=lineage,
    )


def quote_part(current_price: ResolvedInput | None, status: CalculationStatus | None, reason: str | None) -> QuotePart:
    """Return the quote-attempt part: the failed lookup's status, ``ok`` for a quote, else ``not_attempted``."""
    if status is not None:
        return QuotePart(status=status.value, reason=reason)
    if current_price is not None:
        return QuotePart(status="ok", reason=None)
    return QuotePart(status="not_attempted", reason=None)


def price_comparison_part(comparison: PriceComparison | None) -> PriceComparisonPart | None:
    """Return the part for a price comparison, or ``None`` when none was made."""
    if comparison is None:
        return None
    resolution = comparison.security_unit_resolution
    evidence = resolution.evidence if resolution is not None else None
    provenance = resolution.provenance if resolution is not None else None
    freshness = comparison.quote_freshness
    return PriceComparisonPart(
        status=comparison.status,  # type: ignore[arg-type]  # validated against the two statuses the model allows
        reason=comparison.reason,
        percent=comparison.percent,
        quote_freshness=None
        if freshness is None
        else QuoteFreshnessPart(
            status=freshness.status,
            evaluated_at=freshness.evaluated_at,
            retrieved_at=freshness.retrieved_at,
            retrieval_age_seconds=freshness.retrieval_age_seconds,
            max_retrieval_age_seconds=freshness.max_retrieval_age_seconds,
            market_observed_at=freshness.market_observed_at,
        ),
        security_unit_evidence=None
        if evidence is None
        else SecurityUnitEvidencePart(
            ticker=evidence.ticker,
            filing_unit_kind=evidence.filing_unit_kind.value,
            quoted_unit_kind=evidence.quoted_unit_kind.value,
            underlying_shares_per_quoted_unit=evidence.underlying_shares_per_quoted_unit,
            provider_id=evidence.provider_id,
            source=evidence.source,
        ),
        provenance=None
        if provenance is None
        else SecurityUnitProvenancePart(
            mapping_id=provenance.mapping_id,
            cik=provenance.cik,
            class_title=provenance.class_title,
            documents=tuple(
                SecurityUnitDocumentPart(
                    accession=item.accession,
                    url=item.url,
                    context_ids=item.context_ids,
                    available_at=item.available_at,
                    retrieved_at=item.retrieved_at,
                    listing_venue=item.listing_venue,
                )
                for item in provenance.documents
            ),
        ),
    )
