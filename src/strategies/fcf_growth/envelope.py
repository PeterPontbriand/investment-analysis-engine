"""The FCF Growth ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay.

The document is the complete result plus the presentation fields (``schema_version``, ``result_schema_version``,
``security_identity`` and ``instrument_kind``). Its resolved inputs are wider than the Graham family's: they
carry the annual-fact fields (fiscal year, period kind, accounting scope, capital-expenditure sign, provider fact
id), so the model is this strategy's own.
"""

from __future__ import annotations

from typing import Final

from src.core.analysis_status import CalculationStatus
from src.core.metric_result import ReasonCode
from src.data.financial.provenance import AccountingScope, CapitalExpenditureSign, PeriodKind, SourceKind
from src.reporting.documents.shared_parts import (
    DiagnosticEntry,
    DocumentPart,
    InstrumentKindPart,
    JsonNumber,
    MetricResultPart,
    SecurityIdentityPart,
)
from src.reporting.documents.timestamp import DocumentTimestamp
from src.strategies.fcf_growth.vocabulary import (
    AnalysisId,
    Classification,
    FCFClassificationBasis,
    ForwardEvidenceStatus,
    ForwardPolicy,
    HistoricalHorizon,
    MethodId,
    TrendClassification,
)

DOCUMENT_SCHEMA_VERSION: Final = 5


class FCFResolvedInputPart(DocumentPart):
    """One resolved input with its full provenance, including the annual-fact fields."""

    field_name: str
    value: JsonNumber
    source_kind: SourceKind
    resolved_at: DocumentTimestamp
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
    cache_schema_version: int | None
    lineage: FCFLineagePart | None
    notes: tuple[str, ...]
    fiscal_year: int | None
    period_kind: PeriodKind | None
    accounting_scope: AccountingScope | None
    capital_expenditure_sign: CapitalExpenditureSign | None
    provider_fact_id: str | None


class FCFLineagePart(DocumentPart):
    """How a derived input was composed from other inputs."""

    transformation: str
    components: tuple[FCFResolvedInputPart, ...]


FCFResolvedInputPart.model_rebuild()
FCFLineagePart.model_rebuild()


class FCFPolicyPart(DocumentPart):
    """The investor-selected controls of the run."""

    historical_horizon: HistoricalHorizon
    classification_basis: FCFClassificationBasis
    forward_policy: ForwardPolicy
    include_fcf_yield: bool


class FCFObservationPart(DocumentPart):
    """One completed fiscal year with every component preserved."""

    fiscal_year: int
    period_start: DocumentTimestamp
    period_end: DocumentTimestamp
    operating_cash_flow: FCFResolvedInputPart
    normalized_capital_expenditures: FCFResolvedInputPart
    free_cash_flow: FCFResolvedInputPart
    diluted_eps: FCFResolvedInputPart
    weighted_average_diluted_shares: FCFResolvedInputPart | None
    free_cash_flow_per_diluted_share: FCFResolvedInputPart | None


class FCFForwardEvidencePart(DocumentPart):
    """The analyst-consensus forward evidence for the next two fiscal years."""

    status: ForwardEvidenceStatus
    latest_actual_eps: FCFResolvedInputPart | None
    fy1_consensus_eps: FCFResolvedInputPart | None
    fy2_consensus_eps: FCFResolvedInputPart | None
    actual_to_fy1_growth: MetricResultPart
    fy1_to_fy2_growth: MetricResultPart
    confirms_positive_growth: bool | None


class FCFDiagnosticsPart(DocumentPart):
    """The ordered diagnostics of the run: resolver events, then the instrument-profile attempts."""

    events: tuple[DiagnosticEntry, ...]


class FCFDocument(DocumentPart):
    """The FCF Growth document, version 5, as ``fcf-growth --json`` and ``runs show --json`` write it."""

    schema_version: int
    result_schema_version: int
    strategy_id: AnalysisId
    method_id: MethodId
    method_version: int
    ticker: str
    security_identity: SecurityIdentityPart
    instrument_kind: InstrumentKindPart | None
    requested_as_of: DocumentTimestamp | None
    effective_as_of: DocumentTimestamp
    policy: FCFPolicyPart
    execution_status: CalculationStatus
    classification: Classification
    classification_reason_code: ReasonCode | None
    classification_reason: str | None
    selected_horizon_years: int | None
    selected_observation_count: int
    used_horizon_fallback: bool
    period_start: DocumentTimestamp | None
    period_end: DocumentTimestamp | None
    annual_observations: tuple[FCFObservationPart, ...]
    fcf_cagr: MetricResultPart
    fcf_per_share_cagr: MetricResultPart
    eps_cagr: MetricResultPart
    trend_classification: TrendClassification
    market_capitalization: FCFResolvedInputPart | None
    fcf_yield: MetricResultPart
    forward_evidence: FCFForwardEvidencePart
    warnings: tuple[str, ...]
    diagnostics: FCFDiagnosticsPart


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "FCFDiagnosticsPart",
    "FCFDocument",
    "FCFForwardEvidencePart",
    "FCFLineagePart",
    "FCFObservationPart",
    "FCFPolicyPart",
    "FCFResolvedInputPart",
]
