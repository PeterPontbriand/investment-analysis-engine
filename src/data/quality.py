"""Pure data-quality decisions with explicit evidence and temporal policy.

Rules never fetch, write, transform observations, or infer exchange calendars.
An insufficient-evidence outcome is not proof of validity: consumers retain
their method-specific requirements for using an input.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

import numpy as np
import pandas as pd

from src.data.base_client import DataFetchError
from src.data.market_data import HistoricalMarketData


class QualityOutcome(StrEnum):
    """Distinguish verified results from unavailable supporting evidence."""

    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


def _aware(value: datetime | None) -> None:
    if value is not None and value.utcoffset() is None:
        raise ValueError("Quality timestamps must be timezone-aware.")


@dataclass(frozen=True)
class QualityContext:
    """Identify the evaluated input and retain execution and evidence times."""

    input_id: str
    evaluated_at: datetime
    analysis_as_of: datetime | None = None
    retrieved_at: datetime | None = None

    def __post_init__(self) -> None:
        """Reject unidentified inputs and ambiguous timestamps."""
        if not self.input_id.strip():
            raise ValueError("Quality input_id must be non-empty.")
        for value in (self.evaluated_at, self.analysis_as_of, self.retrieved_at):
            _aware(value)


@dataclass(frozen=True)
class QualityDecision:
    """One rule result with its reason and original evaluation context."""

    rule_id: str
    outcome: QualityOutcome
    reason: str
    context: QualityContext
    evidence_at: datetime | None = None

    def __post_init__(self) -> None:
        """Require stable identifiers and explanatory reasons."""
        if not self.rule_id.strip() or not self.reason.strip():
            raise ValueError("Quality rule_id and reason must be non-empty.")
        _aware(self.evidence_at)


class HistoricalDataQualityError(DataFetchError):
    """Sanitized historical validation failure with bounded field/date evidence."""

    def __init__(self, decisions: tuple[QualityDecision, ...], frame: pd.DataFrame) -> None:
        """Retain rule decisions without exposing raw observations or provider payloads."""
        self.decisions = decisions
        self.invalid_observations: tuple[str, ...] = self._invalid_observations(frame)
        reasons = [item.reason for item in decisions if item.outcome is QualityOutcome.FAIL]
        detail = "; ".join(self.invalid_observations)
        super().__init__("; ".join(reasons) + (f" Affected observations: {detail}." if detail else ""))

    @staticmethod
    def _invalid_observations(frame: pd.DataFrame) -> tuple[str, ...]:
        invalid: list[str] = []
        if not frame.columns.is_unique:
            return ()
        for column in ("Close", "Open", "High", "Low", "Adj Close", "Volume"):
            if column not in frame.columns:
                continue
            try:
                values = frame[column].to_numpy(dtype=float)
            except (ValueError, TypeError, OverflowError):
                invalid.append(f"{column}: invalid numeric type")
                continue
            for index in np.flatnonzero(~np.isfinite(values))[:5]:
                stamp = frame.index[index]
                label = stamp.isoformat() if isinstance(stamp, (date, datetime)) else f"row {index}"
                invalid.append(f"{column} at {label}")
        return tuple(invalid[:10])


@dataclass(frozen=True)
class HistoricalQualityPolicy:
    """Optional comparison evidence for one historical request.

    Expected sessions must be sorted, unique exchange-local dates for the exact
    daily request. None means no schedule was supplied, not a weekday calendar.
    Currency and adjustment expectations compare evidence without converting it.
    """

    expected_currency: str | None = None
    expected_adjustment: str | None = None
    expected_sessions: tuple[date, ...] | None = None

    def __post_init__(self) -> None:
        """Normalize labels and reject empty or ambiguous schedule evidence."""
        for name, value in (
            ("expected_currency", self.expected_currency),
            ("expected_adjustment", self.expected_adjustment),
        ):
            if value is not None:
                if not value.strip():
                    raise ValueError(f"{name} must be non-empty.")
                normalized = value.strip().upper() if name == "expected_currency" else value.strip().lower()
                object.__setattr__(self, name, normalized)
        sessions = self.expected_sessions
        if sessions is not None and (
            not sessions
            or any(type(session) is not date for session in sessions)
            or tuple(sorted(set(sessions))) != sessions
        ):
            raise ValueError("Expected sessions must be non-empty, sorted, unique dates.")


@dataclass(frozen=True)
class FreshnessPolicy:
    """Independent maximum cache and observation ages; None disables a limit.

    Equality is eligible. No reporting deadline or market closure policy is
    inferred. Production composition retains ownership of capability defaults.
    """

    cache_ttl: timedelta | None = None
    observation_max_age: timedelta | None = None

    def __post_init__(self) -> None:
        """Reject negative lifetime policies."""
        for value in (self.cache_ttl, self.observation_max_age):
            if value is not None and value < timedelta(0):
                raise ValueError("Quality age limits must be non-negative.")


def _numeric_error(frame: pd.DataFrame) -> str | None:
    if frame.empty or "Close" not in frame.columns or not frame.columns.is_unique:
        return "Historical data requires non-empty Close and unique columns."
    for column in ("Open", "High", "Low", "Close", "Adj Close", "Volume"):
        if column not in frame.columns:
            continue
        values = frame[column]
        if pd.api.types.is_complex_dtype(values.dtype) or pd.api.types.is_bool_dtype(values.dtype):
            return "Historical observations must be real numeric values, not complex or boolean values."
        # Object columns can contain booleans/complex values mixed with numbers.
        if values.dtype == object and any(
            isinstance(value, (bool, complex, np.bool_, np.complexfloating)) for value in values
        ):
            return "Historical observations must not contain boolean or complex values."
        try:
            numeric = values.to_numpy(dtype=float)
        except (TypeError, ValueError, OverflowError):
            return "Historical observations must be numeric and finite."
        if not np.isfinite(numeric).all():
            return "Historical observations must be numeric and finite."
    return None


def _index_result(frame: pd.DataFrame) -> tuple[QualityOutcome, str]:
    if not isinstance(frame.index, pd.DatetimeIndex):
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "No supported DatetimeIndex is available."
    if frame.empty or frame.index.hasnans or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        return QualityOutcome.FAIL, "Historical dates must be present, unique and increasing."
    return QualityOutcome.PASS, "Historical timestamps are present, unique and increasing."


def _context_result(data: HistoricalMarketData) -> tuple[QualityOutcome, str]:
    metadata = data.context
    if metadata.observation_count is not None and metadata.observation_count != len(data.frame):
        return QualityOutcome.FAIL, "Retained observation count differs from the frame."
    if _index_result(data.frame)[0] is not QualityOutcome.PASS:
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "Observation date cannot be verified against the frame."
    if metadata.data_as_of is not None and metadata.data_as_of != data.frame.index[-1].date():
        return QualityOutcome.FAIL, "Retained observation date differs from the final bar."
    if metadata.observation_count is None or metadata.data_as_of is None:
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "Observation count or date metadata is missing."
    return QualityOutcome.PASS, "Retained observation count and date match the frame."


def _metadata_result(actual: str | None, expected: str | None) -> tuple[QualityOutcome, str]:
    if actual is None:
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "Provider metadata is unavailable."
    if expected is not None and actual != expected:
        return QualityOutcome.FAIL, "Provider metadata conflicts with the requested comparison basis."
    return QualityOutcome.PASS, "Provider metadata is present and has no declared comparison conflict."


def _sessions_result(data: HistoricalMarketData, policy: HistoricalQualityPolicy) -> tuple[QualityOutcome, str]:
    if policy.expected_sessions is None or data.context.observation_interval != "1d":
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "No supported daily session schedule is available."
    if _index_result(data.frame)[0] is not QualityOutcome.PASS:
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "Session coverage requires valid historical dates."
    observed = tuple(timestamp.date() for timestamp in data.frame.index)
    if len(set(observed)) != len(observed):
        return QualityOutcome.FAIL, "Daily data contains more than one bar for a session date."
    if set(policy.expected_sessions) - set(observed):
        return QualityOutcome.FAIL, "Historical data is missing one or more explicitly expected sessions."
    return QualityOutcome.PASS, "All explicitly expected daily sessions are present."


DEFAULT_HISTORICAL_QUALITY_POLICY = HistoricalQualityPolicy()


def evaluate_historical_quality(
    data: HistoricalMarketData,
    *,
    context: QualityContext,
    policy: HistoricalQualityPolicy = DEFAULT_HISTORICAL_QUALITY_POLICY,
) -> tuple[QualityDecision, ...]:
    """Evaluate numeric, ordering and context evidence without mutating data.

    Args:
        data: Original observations and provider metadata.
        context: Identity and timestamps of the evaluated request or cache entry.
        policy: Optional expected currency, adjustment basis and daily sessions.

    Returns:
        Ordered rule decisions; callers enforce method-specific evidence needs.
    """
    numeric_error = _numeric_error(data.frame)
    results = (
        (
            "historical.numeric",
            (QualityOutcome.FAIL, numeric_error)
            if numeric_error
            else (QualityOutcome.PASS, "Required observations are non-empty, numeric and finite."),
        ),
        ("historical.index", _index_result(data.frame)),
        ("historical.context", _context_result(data)),
        ("historical.currency", _metadata_result(data.context.currency, policy.expected_currency)),
        ("historical.adjustment", _metadata_result(data.context.price_adjustment, policy.expected_adjustment)),
        ("historical.sessions", _sessions_result(data, policy)),
    )
    return tuple(QualityDecision(rule, outcome, reason, context) for rule, (outcome, reason) in results)


def _age_result(
    timestamp: datetime | None, boundary: datetime, limit: timedelta | None, *, cache: bool
) -> tuple[QualityOutcome, str]:
    if timestamp is None:
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "Age evidence is unavailable."
    age = boundary - timestamp
    if age < timedelta(0):
        if cache:
            return QualityOutcome.INSUFFICIENT_EVIDENCE, "Cache timestamp is in the future; clock drift is unverified."
        return QualityOutcome.FAIL, "Observation is later than the analysis boundary."
    if limit is None:
        return QualityOutcome.INSUFFICIENT_EVIDENCE, "No maximum age policy is configured."
    if age > limit:
        return QualityOutcome.FAIL, "Age exceeds the configured maximum."
    return QualityOutcome.PASS, "Age is within the configured maximum, including equality."


def evaluate_freshness(  # noqa: PLR0913
    *,
    context: QualityContext,
    policy: FreshnessPolicy,
    cached_at: datetime | None = None,
    observed_at: datetime | None = None,
    available_at: datetime | None = None,
) -> tuple[QualityDecision, ...]:
    """Evaluate residence age, observation age and point-in-time availability.

    Args:
        context: Input identity, current evaluation time and optional historical boundary.
        policy: Independent cache and observation lifetime limits.
        cached_at: Cache insertion timestamp, not the financial observation date.
        observed_at: Actual observation or reporting-period end supplied by the caller.
        available_at: Publication/availability evidence, never inferred from retrieval.

    Returns:
        Ordered decisions retaining the evaluation context. Missing availability
        fails historical use; missing current availability remains unverified.

    Raises:
        ValueError: Any supplied timestamp is naive.
    """
    for timestamp in (cached_at, observed_at, available_at):
        _aware(timestamp)
    boundary = context.analysis_as_of or context.evaluated_at
    if available_at is None:
        availability = (
            QualityOutcome.FAIL if context.analysis_as_of is not None else QualityOutcome.INSUFFICIENT_EVIDENCE,
            "Availability evidence is missing; historical use requires it.",
        )
    elif available_at > boundary:
        availability = (QualityOutcome.FAIL, "Availability is later than the analysis boundary.")
    else:
        availability = (QualityOutcome.PASS, "Availability is no later than the analysis boundary.")
    results = (
        ("freshness.cache_age", _age_result(cached_at, context.evaluated_at, policy.cache_ttl, cache=True)),
        ("freshness.observation_age", _age_result(observed_at, boundary, policy.observation_max_age, cache=False)),
        ("freshness.availability", availability),
    )
    return tuple(
        QualityDecision(rule, outcome, reason, context, evidence_at=timestamp)
        for (rule, (outcome, reason)), timestamp in zip(results, (cached_at, observed_at, available_at), strict=True)
    )
