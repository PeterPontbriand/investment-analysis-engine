"""Quote response reuse policy, distinct from market trade timing."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from src.data.financial.provenance import ResolvedInput, SourceKind


@dataclass(frozen=True)
class QuoteFreshnessPolicy:
    """Maximum age of an original provider response, not of an exchange trade."""

    max_retrieval_age: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        """Require a nonnegative finite duration."""
        if self.max_retrieval_age < timedelta(0):
            raise ValueError("Quote retrieval age must be nonnegative.")


DEFAULT_QUOTE_FRESHNESS_POLICY = QuoteFreshnessPolicy()


@dataclass(frozen=True)
class QuoteFreshnessEvidence:
    """Retain the evaluated response age and independently known market timestamp."""

    status: Literal[
        "recent_retrieval", "expired", "unknown_retrieval_time", "future_timestamp", "user_supplied", "historical"
    ]
    evaluated_at: datetime
    retrieved_at: datetime | None
    retrieval_age_seconds: float | None
    max_retrieval_age_seconds: float
    market_observed_at: datetime | None


def evaluate_quote_freshness(
    value: ResolvedInput, *, now: datetime, policy: QuoteFreshnessPolicy = DEFAULT_QUOTE_FRESHNESS_POLICY
) -> QuoteFreshnessEvidence:
    """Evaluate retained timing without inventing provider observation evidence."""
    if now.utcoffset() is None:
        raise ValueError("Quote evaluation time must be timezone-aware.")
    observed = value.observed_at
    if value.provider_id == "yfinance" and any("conservatively use retrieval time" in note for note in value.notes):
        observed = None
    age = (now - value.retrieved_at).total_seconds() if value.retrieved_at is not None else None
    status: Literal[
        "recent_retrieval", "expired", "unknown_retrieval_time", "future_timestamp", "user_supplied", "historical"
    ]
    if value.source_kind is SourceKind.OVERRIDE:
        status = "user_supplied"
    elif value.as_of is not None:
        status = "historical"
    elif (age is not None and age < 0) or (observed is not None and observed > now):
        status = "future_timestamp"
    elif age is None:
        status = "unknown_retrieval_time"
    elif age > policy.max_retrieval_age.total_seconds():
        status = "expired"
    else:
        status = "recent_retrieval"
    return QuoteFreshnessEvidence(
        status, now, value.retrieved_at, age, policy.max_retrieval_age.total_seconds(), observed
    )
