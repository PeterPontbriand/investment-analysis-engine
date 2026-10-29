"""The FCF Growth ``--json`` document: its version and typed model.

The identifiers and enumerations the document writes are read from the strategy's ``vocabulary.py``, the one place
they are declared; this module imports nothing else from the package.
The same model backs a direct command and a ``runs show`` replay.

The document is the complete result plus the presentation fields (the shared header and tail, and
``result_schema_version``). Its resolved inputs are wider than the Graham family's: they carry the annual-fact
fields (fiscal year, period kind, accounting scope, capital-expenditure sign, provider fact id), so the model is this
strategy's own.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from investment_analysis_engine.analysis.shared.market_cap import ShareCountBasis
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    PeriodKind,
    SourceKind,
)
from investment_analysis_engine.reporting.documents.shared_parts import DocumentPart, JsonNumber, MetricResultPart
from investment_analysis_engine.reporting.documents.strategy_document import (
    StrategyDocumentHeader,
    StrategyDocumentTail,
)
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    AnalysisId,
    Classification,
    FCFClassificationBasis,
    ForwardEvidenceStatus,
    ForwardPolicy,
    HistoricalHorizon,
    MethodId,
    TrendClassification,
)

DOCUMENT_SCHEMA_VERSION: Final = 10


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


class FCFSplitPart(DocumentPart):
    """One split of the provider's history: its ex-date and the new shares per old share."""

    ex_date: date
    ratio: float


class FCFListingRenamePart(DocumentPart):
    """The two covers that show one share line renamed, with the symbols as filed."""

    anchor_accession: str
    anchor_form: str
    anchor_symbol: str
    latest_accession: str
    latest_form: str
    latest_symbol: str


class FCFListingCheckPart(DocumentPart):
    """The listing check's outcome: affirmed with the accession read, or refused with its code and reason."""

    affirmed: bool
    accession: str | None
    reason_code: ReasonCode | None
    reason: str | None
    rename: FCFListingRenamePart | None


class FCFMarketCapPart(DocumentPart):
    """Market capitalization at the boundary with the share count, price and splits behind it."""

    result: MetricResultPart
    share_count: FCFResolvedInputPart | None
    share_count_basis: ShareCountBasis | None
    share_count_date: date | None
    share_count_filing_date: date | None
    scaled_share_count: float | None
    splits_applied: tuple[FCFSplitPart, ...]
    price: float | None
    price_date: date | None
    form: str | None
    filing_currency: str | None
    quote_currency: str | None
    listing_check: FCFListingCheckPart | None


class FCFBody(DocumentPart):
    """The keys only the FCF Growth document writes."""

    result_schema_version: int
    method_version: int
    policy: FCFPolicyPart
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
    market_capitalization: FCFMarketCapPart | None
    fcf_yield: MetricResultPart
    forward_evidence: FCFForwardEvidencePart


class FCFDocument(StrategyDocumentTail, FCFBody, StrategyDocumentHeader[AnalysisId, MethodId]):
    """The FCF Growth document, version 10, as ``fcf-growth --json`` and ``runs show --json`` write it.

    The shared header and tail come from :mod:`investment_analysis_engine.reporting.documents.strategy_document`.
    """


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "FCFBody",
    "FCFDocument",
    "FCFForwardEvidencePart",
    "FCFLineagePart",
    "FCFListingCheckPart",
    "FCFListingRenamePart",
    "FCFMarketCapPart",
    "FCFObservationPart",
    "FCFPolicyPart",
    "FCFResolvedInputPart",
    "FCFSplitPart",
]
