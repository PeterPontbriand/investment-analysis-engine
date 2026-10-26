"""Cross-sectional ranking of members over several metrics.

A pure function over frozen types. It knows nothing about strategies, runs or persistence: the caller supplies members,
each with a ticker, an opaque issuer key and one ``MetricResult`` per requested metric, and the metrics with their
directions. The helper deduplicates share classes of one issuer, decides which members are eligible, and, when at least
``MINIMUM_ELIGIBLE_MEMBERS`` are, ranks each metric (rank 1 is best, tied values share the average rank), reports a
display percentile, sums the ranks with equal weights and assigns competition positions (1, 1, 3).

Ranks, percentiles, sums and positions are typed fields of the result. None of them is a ``MetricResult``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode

MINIMUM_ELIGIBLE_MEMBERS = 10
"""Fewest eligible members that are ranked; below it the result carries values and a diagnostic, and no ranks.

A rank among a handful of names says little, and percentiles over fewer than ten would suggest a precision the universe
does not have. It is a constant of the helper, not a parameter: a caller cannot lower it for one ranking.
"""


class RankDirection(StrEnum):
    """Which end of a metric's values is best."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class RankDiagnosticKind(StrEnum):
    """What a ranking diagnostic reports."""

    DUPLICATE_ISSUER = "duplicate_issuer"
    KEPT_CLASS_LACKS_METRIC = "kept_class_lacks_metric"
    BELOW_MINIMUM = "below_minimum"


@dataclass(frozen=True)
class RankMetric:
    """One metric to rank by: its name and which direction is better."""

    name: str
    direction: RankDirection


@dataclass(frozen=True)
class RankMember:
    """One candidate: a ticker, the issuer it belongs to and its result for every requested metric.

    ``issuer_key`` is opaque to the helper: members with an equal key are share classes of one issuer.
    """

    ticker: str
    issuer_key: str
    results: Mapping[str, MetricResult]

    def __post_init__(self) -> None:
        """Reject a blank ticker or issuer key."""
        if not self.ticker.strip():
            raise ValueError("A ranking member requires a non-empty ticker.")
        if not self.issuer_key.strip():
            raise ValueError(f"Ranking member {self.ticker!r} requires a non-empty issuer key.")


@dataclass(frozen=True)
class MetricExclusion:
    """Why one metric kept a member out of the ranking: the result's own status and reason."""

    metric: str
    status: MetricStatus
    reason_code: ReasonCode
    reason: str


@dataclass(frozen=True)
class RankExclusion:
    """A member that is not ranked, with a reason for every metric that excluded it and its values."""

    ticker: str
    issuer_key: str
    values: tuple[float | None, ...]
    reasons: tuple[MetricExclusion, ...]


@dataclass(frozen=True)
class RankDiagnostic:
    """A statement about the ranking the caller must be able to show."""

    kind: RankDiagnosticKind
    tickers: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class EligibleMember:
    """A member with a finite value for every metric, in the order of the requested metrics."""

    ticker: str
    issuer_key: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class RankedMember:
    """An eligible member with its ranks, display percentiles, rank sum and competition position.

    ``ranks`` and ``percentiles`` follow the order of the requested metrics. Rank 1 is best and tied values share the
    average rank; the percentile is higher for a better rank.
    """

    ticker: str
    issuer_key: str
    values: tuple[float, ...]
    ranks: tuple[float, ...]
    percentiles: tuple[float, ...]
    rank_sum: float
    position: int


@dataclass(frozen=True)
class RankingResult:
    """The outcome of one ranking.

    ``eligible`` lists every eligible member in ticker order. ``ranked`` is in display order (position, then ticker;
    ticker order carries no ranking meaning) and is empty when fewer than ``MINIMUM_ELIGIBLE_MEMBERS`` are eligible.
    """

    metrics: tuple[RankMetric, ...]
    eligible: tuple[EligibleMember, ...]
    ranked: tuple[RankedMember, ...]
    exclusions: tuple[RankExclusion, ...]
    diagnostics: tuple[RankDiagnostic, ...]
    minimum_eligible_members: int


def rank_members(members: Sequence[RankMember], metrics: Sequence[RankMetric]) -> RankingResult:
    """Rank ``members`` over ``metrics`` with equal weights.

    Steps, in order: deduplicate by issuer key (the member whose upper-cased ticker sorts first in ordinal order is
    kept), exclude members without an ``ok`` result for every metric, stop without ranks below
    ``MINIMUM_ELIGIBLE_MEMBERS``, then rank each metric, sum the ranks and assign competition positions. The output
    does not depend on the order of ``members``.

    Raises:
        ValueError: If no metric is requested, metric names repeat, tickers repeat after upper-casing, or a member has
            no result for a requested metric. A missing entry is a caller error, unlike an unavailable value.
    """
    metric_tuple = tuple(metrics)
    _validate(members, metric_tuple)
    normalized = sorted(
        (RankMember(member.ticker.upper(), member.issuer_key, member.results) for member in members),
        key=lambda member: member.ticker,
    )
    kept, diagnostics = _deduplicate(normalized)
    eligible: list[EligibleMember] = []
    exclusions: list[RankExclusion] = []
    for member in kept:
        outcome = _eligibility(member, metric_tuple)
        if isinstance(outcome, EligibleMember):
            eligible.append(outcome)
        else:
            exclusions.append(outcome)
    diagnostics = diagnostics + _lacking_kept_class_diagnostics(normalized, kept, exclusions, metric_tuple)
    if len(eligible) < MINIMUM_ELIGIBLE_MEMBERS:
        diagnostics += (
            RankDiagnostic(
                RankDiagnosticKind.BELOW_MINIMUM,
                tuple(member.ticker for member in eligible),
                f"{len(eligible)} eligible members; at least {MINIMUM_ELIGIBLE_MEMBERS} are required to rank, "
                "so no ranks, percentiles or positions are reported.",
            ),
        )
        ranked: tuple[RankedMember, ...] = ()
    else:
        ranked = _rank(eligible, metric_tuple)
    return RankingResult(
        metrics=metric_tuple,
        eligible=tuple(eligible),
        ranked=ranked,
        exclusions=tuple(exclusions),
        diagnostics=diagnostics,
        minimum_eligible_members=MINIMUM_ELIGIBLE_MEMBERS,
    )


def _validate(members: Sequence[RankMember], metrics: tuple[RankMetric, ...]) -> None:
    """Raise ``ValueError`` for a request no ranking can be built from."""
    if not metrics:
        raise ValueError("Ranking requires at least one metric.")
    names = [metric.name for metric in metrics]
    if len(set(names)) != len(names):
        raise ValueError(f"Ranking metric names must be unique (received {names!r}).")
    seen: set[str] = set()
    for member in members:
        ticker = member.ticker.upper()
        if ticker in seen:
            raise ValueError(f"Ranking tickers must be unique after upper-casing (repeated {ticker!r}).")
        seen.add(ticker)
        missing = [name for name in names if name not in member.results]
        if missing:
            raise ValueError(f"Ranking member {ticker!r} has no result for metric(s) {missing!r}.")


def _deduplicate(members: Sequence[RankMember]) -> tuple[list[RankMember], tuple[RankDiagnostic, ...]]:
    """Keep the ordinal-first ticker of each issuer and report the others."""
    by_issuer: dict[str, list[RankMember]] = {}
    for member in members:
        by_issuer.setdefault(member.issuer_key, []).append(member)
    kept: list[RankMember] = []
    diagnostics: list[RankDiagnostic] = []
    for issuer_key in sorted(by_issuer):
        group = by_issuer[issuer_key]  # already in ticker order: members is sorted
        kept.append(group[0])
        if len(group) > 1:
            dropped = tuple(member.ticker for member in group[1:])
            diagnostics.append(
                RankDiagnostic(
                    RankDiagnosticKind.DUPLICATE_ISSUER,
                    (group[0].ticker, *dropped),
                    f"Issuer {issuer_key!r} has several members. {group[0].ticker} is kept as a canonical "
                    f"representative for ranking only; {', '.join(dropped)} are not ranked. The rule does not "
                    "assert that the share classes are economically equivalent: their prices and rights can differ.",
                )
            )
    kept.sort(key=lambda member: member.ticker)
    return kept, tuple(diagnostics)


def _eligibility(member: RankMember, metrics: tuple[RankMetric, ...]) -> EligibleMember | RankExclusion:
    """Return the member as eligible when every metric is ``ok``, else its exclusion with every reason."""
    values: list[float | None] = []
    reasons: list[MetricExclusion] = []
    for metric in metrics:
        result = member.results[metric.name]
        if result.status is MetricStatus.OK and result.value is not None:
            values.append(result.value)
            continue
        values.append(None)
        if result.reason_code is None or result.reason is None:
            raise ValueError(f"Metric {metric.name!r} of {member.ticker!r} is not ok and carries no reason.")
        reasons.append(MetricExclusion(metric.name, result.status, result.reason_code, result.reason))
    if reasons:
        return RankExclusion(member.ticker, member.issuer_key, tuple(values), tuple(reasons))
    return EligibleMember(member.ticker, member.issuer_key, tuple(v for v in values if v is not None))


def _lacking_kept_class_diagnostics(
    all_members: Sequence[RankMember],
    kept: Sequence[RankMember],
    exclusions: Sequence[RankExclusion],
    metrics: tuple[RankMetric, ...],
) -> tuple[RankDiagnostic, ...]:
    """Name both classes when the kept class lacks a metric that another class of the issuer has."""
    kept_by_ticker = {member.ticker: member for member in kept}
    diagnostics: list[RankDiagnostic] = []
    for exclusion in exclusions:
        member = kept_by_ticker[exclusion.ticker]
        lacking = {reason.metric for reason in exclusion.reasons}
        for other in all_members:
            if other.issuer_key != member.issuer_key or other.ticker == member.ticker:
                continue
            covered = [
                metric.name
                for metric in metrics
                if metric.name in lacking and other.results[metric.name].status is MetricStatus.OK
            ]
            if covered:
                diagnostics.append(
                    RankDiagnostic(
                        RankDiagnosticKind.KEPT_CLASS_LACKS_METRIC,
                        (member.ticker, other.ticker),
                        f"Issuer {member.issuer_key!r} is excluded: {member.ticker}, kept for ranking, has no value "
                        f"for {', '.join(covered)}, although {other.ticker} has one. Values are never taken from "
                        "another share class.",
                    )
                )
    return tuple(diagnostics)


def _average_ranks(values: Sequence[float], direction: RankDirection) -> list[float]:
    """Return the average rank of each value, rank 1 best; equal values (compared exactly) share their average."""
    descending = direction is RankDirection.HIGHER_IS_BETTER
    order = sorted(range(len(values)), key=lambda index: values[index], reverse=descending)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        shared = (start + 1 + end + 1) / 2
        for index in order[start : end + 1]:
            ranks[index] = shared
        start = end + 1
    return ranks


def _rank(eligible: Sequence[EligibleMember], metrics: tuple[RankMetric, ...]) -> tuple[RankedMember, ...]:
    """Rank the eligible members: per-metric average ranks, percentiles, rank sums and competition positions."""
    count = len(eligible)
    per_metric = [
        _average_ranks([member.values[column] for member in eligible], metric.direction)
        for column, metric in enumerate(metrics)
    ]
    ranks_of = [tuple(per_metric[column][row] for column in range(len(metrics))) for row in range(count)]
    sums = [sum(ranks) for ranks in ranks_of]
    positions = [1 + sum(1 for other in sums if other < own) for own in sums]
    ranked = [
        RankedMember(
            ticker=member.ticker,
            issuer_key=member.issuer_key,
            values=member.values,
            ranks=ranks_of[row],
            percentiles=tuple(100.0 * (count - rank) / (count - 1) for rank in ranks_of[row]),
            rank_sum=sums[row],
            position=positions[row],
        )
        for row, member in enumerate(eligible)
    ]
    return tuple(sorted(ranked, key=lambda member: (member.position, member.ticker)))
