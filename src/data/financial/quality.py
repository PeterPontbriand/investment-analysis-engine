"""Temporal quality enforcement shared by scalar, derived and series facts."""

from datetime import datetime, timedelta

from src.data.financial.facts import ProviderFact
from src.data.financial.provenance import ResolvedInput
from src.data.quality import FreshnessPolicy, QualityContext, QualityOutcome, evaluate_freshness
from src.data.quality_reporting import publish_quality


def financial_cache_eligible(  # noqa: PLR0913
    value: ResolvedInput,
    *,
    input_id: str,
    now: datetime,
    as_of: datetime | None,
    cached_at: datetime,
    ttl: timedelta | None,
) -> bool:
    """Retain storage TTL/availability semantics; consumers validate observations."""
    decisions = evaluate_freshness(
        context=QualityContext(input_id, now, analysis_as_of=as_of, retrieved_at=value.retrieved_at),
        policy=FreshnessPolicy(cache_ttl=ttl),
        cached_at=cached_at,
        available_at=value.available_at if as_of is not None else None,
    )
    publish_quality(decisions)
    return not any(item.outcome is QualityOutcome.FAIL for item in decisions)


def financial_quality_error(  # noqa: PLR0913
    value: ProviderFact | ResolvedInput,
    *,
    input_id: str,
    now: datetime,
    as_of: datetime | None,
    cached_at: datetime | None = None,
    ttl: timedelta | None = None,
) -> str | None:
    """Reject future/ineligible evidence and expired cache entries.

    Reporting-age limits remain unset: historical annual observations are not
    expired merely because they are old. Derived inputs also validate lineage.
    """
    context = QualityContext(input_id, now, analysis_as_of=as_of, retrieved_at=value.retrieved_at)
    observation_times = tuple(
        stamp
        for stamp in (value.observed_at, value.observation_period_start, value.observation_period_end)
        if stamp is not None
    )
    decisions = evaluate_freshness(
        context=context,
        policy=FreshnessPolicy(cache_ttl=ttl),
        cached_at=cached_at,
        observed_at=max(observation_times) if observation_times else None,
        available_at=value.available_at,
    )
    publish_quality(decisions)
    for decision in decisions:
        if decision.outcome is QualityOutcome.FAIL:
            return f"{decision.rule_id}: {decision.reason}"
    if isinstance(value, ResolvedInput) and value.lineage is not None:
        for component in value.lineage.components:
            error = financial_quality_error(component, input_id=input_id, now=now, as_of=as_of)
            if error is not None:
                return error
    return None
