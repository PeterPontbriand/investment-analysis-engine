"""The ranking helper, on synthetic members. Expected ranks, percentiles and positions are written out by hand."""

import itertools
import math
import random
from collections.abc import Sequence

import pytest

from investment_analysis_engine.analysis.shared.ranking import (
    MINIMUM_ELIGIBLE_MEMBERS,
    RankDiagnosticKind,
    RankDirection,
    RankMember,
    RankMetric,
    rank_members,
)
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode

HIGHER = RankMetric("a", RankDirection.HIGHER_IS_BETTER)
LOWER = RankMetric("b", RankDirection.LOWER_IS_BETTER)


def _unavailable(code: ReasonCode = ReasonCode.MISSING_FACT, reason: str = "not reported") -> MetricResult:
    return MetricResult.failure(MetricStatus.UNAVAILABLE, code, reason)


def _not_applicable(code: ReasonCode = ReasonCode.INCOMPATIBLE_PERIOD, reason: str = "no meaning") -> MetricResult:
    return MetricResult.failure(MetricStatus.NOT_APPLICABLE, code, reason)


def _member(ticker: str, issuer: str | None = None, **results: MetricResult | float) -> RankMember:
    return RankMember(
        ticker,
        issuer or f"issuer-{ticker}",
        {name: value if isinstance(value, MetricResult) else MetricResult.ok(value) for name, value in results.items()},
    )


def _ten_members() -> list[RankMember]:
    """Ten members; ``a`` is higher-better and ``b`` is lower-better, with a hand-worked outcome."""
    a_values = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    b_values = [5.0, 1.0, 2.0, 3.0, 4.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    return [_member(f"T{n:02d}", a=a, b=b) for n, (a, b) in enumerate(zip(a_values, b_values, strict=True), start=1)]


def _single_metric(values: Sequence[float]) -> list[RankMember]:
    return [_member(f"T{n:02d}", a=value) for n, value in enumerate(values, start=1)]


def test_the_minimum_is_ten() -> None:
    assert MINIMUM_ELIGIBLE_MEMBERS == 10


def test_two_metrics_with_opposite_directions() -> None:
    result = rank_members(_ten_members(), [HIGHER, LOWER])

    # a ranks, high is best: T01..T10 = 1..10. b ranks, low is best: T02=1, T03=2, T04=3, T05=4, T01=5, T06..T10=6..10.
    # Rank sums: T02=3, T03=5, T01=6, T04=7, T05=9, T06=12, T07=14, T08=16, T09=18, T10=20.
    assert [(m.ticker, m.ranks, m.rank_sum, m.position) for m in result.ranked] == [
        ("T02", (2.0, 1.0), 3.0, 1),
        ("T03", (3.0, 2.0), 5.0, 2),
        ("T01", (1.0, 5.0), 6.0, 3),
        ("T04", (4.0, 3.0), 7.0, 4),
        ("T05", (5.0, 4.0), 9.0, 5),
        ("T06", (6.0, 6.0), 12.0, 6),
        ("T07", (7.0, 7.0), 14.0, 7),
        ("T08", (8.0, 8.0), 16.0, 8),
        ("T09", (9.0, 9.0), 18.0, 9),
        ("T10", (10.0, 10.0), 20.0, 10),
    ]
    assert result.exclusions == ()
    assert result.diagnostics == ()
    t01 = next(m for m in result.ranked if m.ticker == "T01")
    assert t01.values == (10.0, 5.0)
    # Percentile = 100 * (10 - rank) / 9: rank 1 -> 900/9, rank 5 -> 500/9, rank 2 -> 800/9.
    assert t01.percentiles == pytest.approx((900 / 9, 500 / 9))
    t02 = next(m for m in result.ranked if m.ticker == "T02")
    assert t02.percentiles == pytest.approx((800 / 9, 900 / 9))


def test_percentile_endpoints() -> None:
    result = rank_members(_ten_members(), [HIGHER, LOWER])
    by_ticker = {m.ticker: m for m in result.ranked}
    assert by_ticker["T01"].percentiles[0] == 100.0  # rank 1 on a
    assert by_ticker["T10"].percentiles == (0.0, 0.0)  # rank 10 on both


def test_lower_is_better_alone() -> None:
    lower_a = RankMetric("a", RankDirection.LOWER_IS_BETTER)
    result = rank_members(_single_metric([3.0, 1.0, 2.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]), [lower_a])
    assert [(m.ticker, m.ranks[0]) for m in result.ranked[:3]] == [("T02", 1.0), ("T03", 2.0), ("T01", 3.0)]


def test_tied_values_share_the_average_rank_and_tied_sums_share_a_position() -> None:
    # Higher is best. 10, 10 -> ranks 1 and 2 -> 1.5 each; 8, 8, 8 -> ranks 3, 4, 5 -> 4 each; the rest 6..10.
    result = rank_members(_single_metric([10.0, 10.0, 8.0, 8.0, 8.0, 5.0, 4.0, 3.0, 2.0, 1.0]), [HIGHER])

    assert [(m.ticker, m.ranks[0], m.position) for m in result.ranked] == [
        ("T01", 1.5, 1),
        ("T02", 1.5, 1),
        ("T03", 4.0, 3),
        ("T04", 4.0, 3),
        ("T05", 4.0, 3),
        ("T06", 6.0, 6),
        ("T07", 7.0, 7),
        ("T08", 8.0, 8),
        ("T09", 9.0, 9),
        ("T10", 10.0, 10),
    ]
    assert result.ranked[0].percentiles[0] == pytest.approx(850 / 9)  # 100 * (10 - 1.5) / 9
    assert result.ranked[2].percentiles[0] == pytest.approx(600 / 9)  # 100 * (10 - 4) / 9


def test_tied_sums_of_different_ranks_share_a_position_and_the_next_skips() -> None:
    a_values = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    b_values = [9.0, 10.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    members = [_member(f"T{n:02d}", a=a, b=b) for n, (a, b) in enumerate(zip(a_values, b_values, strict=True), start=1)]
    result = rank_members(members, [HIGHER, RankMetric("b", RankDirection.HIGHER_IS_BETTER)])

    # T01 has ranks (1, 2) and T02 (2, 1): both sum to 3. T03 (3, 3) sums to 6, T04 (4, 4) to 8, and so on.
    assert [(m.ticker, m.rank_sum, m.position) for m in result.ranked[:4]] == [
        ("T01", 3.0, 1),
        ("T02", 3.0, 1),
        ("T03", 6.0, 3),
        ("T04", 8.0, 4),
    ]


def test_all_values_tied() -> None:
    result = rank_members(_single_metric([5.0] * 10), [HIGHER])

    for member in result.ranked:
        assert member.ranks == (5.5,)
        assert member.percentiles == (50.0,)  # 100 * (10 - 5.5) / 9
        assert member.rank_sum == 5.5
        assert member.position == 1
    assert [m.ticker for m in result.ranked] == [f"T{n:02d}" for n in range(1, 11)]


def test_ties_display_in_ordinal_ticker_order_after_upper_casing() -> None:
    members = [_member(ticker, a=1.0) for ticker in ("z1", "ZA", "b", "a", "T5", "t4", "T3", "T2", "T1", "T0")]
    result = rank_members(members, [HIGHER])

    assert [m.ticker for m in result.ranked] == ["A", "B", "T0", "T1", "T2", "T3", "T4", "T5", "Z1", "ZA"]
    assert {m.position for m in result.ranked} == {1}


def test_every_number_is_finite() -> None:
    result = rank_members(_ten_members(), [HIGHER, LOWER])
    for member in result.ranked:
        numbers = (*member.values, *member.ranks, *member.percentiles, member.rank_sum, float(member.position))
        assert all(math.isfinite(number) for number in numbers)


def test_nine_eligible_members_return_values_and_no_ranks() -> None:
    members = _ten_members()[:9]
    result = rank_members(members, [HIGHER, LOWER])

    assert result.ranked == ()
    assert [m.ticker for m in result.eligible] == [f"T{n:02d}" for n in range(1, 10)]
    assert result.eligible[0].values == (10.0, 5.0)
    assert [d.kind for d in result.diagnostics] == [RankDiagnosticKind.BELOW_MINIMUM]
    assert "9 eligible" in result.diagnostics[0].message


def test_ten_eligible_members_return_ranks() -> None:
    result = rank_members(_ten_members(), [HIGHER, LOWER])
    assert len(result.ranked) == 10
    assert len(result.eligible) == 10


def test_nine_eligible_after_an_exclusion_return_no_ranks_and_ten_return_ranks() -> None:
    members = _ten_members()
    members.append(_member("T11", a=MetricResult.ok(0.0), b=_unavailable()))
    result = rank_members(members, [HIGHER, LOWER])
    assert len(result.ranked) == 10
    assert [e.ticker for e in result.exclusions] == ["T11"]

    short = rank_members(members[:9] + members[10:], [HIGHER, LOWER])
    assert short.ranked == ()
    assert len(short.eligible) == 9
    assert [e.ticker for e in short.exclusions] == ["T11"]


def test_nine_eligible_after_deduplication_return_no_ranks() -> None:
    members = _ten_members()[:9]
    members.append(_member("T10", issuer="issuer-T01", a=1.0, b=10.0))
    result = rank_members(members, [HIGHER, LOWER])

    assert result.ranked == ()
    assert len(result.eligible) == 9
    assert [d.kind for d in result.diagnostics] == [
        RankDiagnosticKind.DUPLICATE_ISSUER,
        RankDiagnosticKind.BELOW_MINIMUM,
    ]


def test_ten_eligible_after_deduplication_return_ranks() -> None:
    members = _ten_members()
    members.append(_member("T11", issuer="issuer-T01", a=0.5, b=11.0))
    result = rank_members(members, [HIGHER, LOWER])

    assert len(result.ranked) == 10
    assert "T11" not in {m.ticker for m in result.ranked}


def test_excluded_members_carry_their_values_and_every_reason() -> None:
    members = _ten_members()[:9]
    members.append(
        _member(
            "T10",
            a=_unavailable(ReasonCode.MISSING_FACT, "no sales"),
            b=_not_applicable(ReasonCode.INCOMPATIBLE_PERIOD, "ends before the anchor"),
        )
    )
    members.append(_member("T11", a=3.0, b=_unavailable(ReasonCode.PROVIDER_ERROR, "provider down")))
    result = rank_members(members, [HIGHER, LOWER])

    first, second = result.exclusions
    assert (first.ticker, first.values) == ("T10", (None, None))
    assert [(r.metric, r.status, r.reason_code, r.reason) for r in first.reasons] == [
        ("a", MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "no sales"),
        ("b", MetricStatus.NOT_APPLICABLE, ReasonCode.INCOMPATIBLE_PERIOD, "ends before the anchor"),
    ]
    assert (second.ticker, second.values) == ("T11", (3.0, None))
    assert [(r.metric, r.status, r.reason_code) for r in second.reasons] == [
        ("b", MetricStatus.UNAVAILABLE, ReasonCode.PROVIDER_ERROR)
    ]


def test_a_not_applicable_metric_and_an_unavailable_one_each_exclude_with_their_own_code() -> None:
    members = _ten_members()[:8]
    members.append(_member("N1", a=_not_applicable(ReasonCode.NONPOSITIVE_ENDING, "negative"), b=1.0))
    members.append(_member("U1", a=1.0, b=_unavailable(ReasonCode.NOT_AVAILABLE_AS_OF, "after the boundary")))
    result = rank_members(members, [HIGHER, LOWER])

    codes = {e.ticker: (e.reasons[0].status, e.reasons[0].reason_code) for e in result.exclusions}
    assert codes == {
        "N1": (MetricStatus.NOT_APPLICABLE, ReasonCode.NONPOSITIVE_ENDING),
        "U1": (MetricStatus.UNAVAILABLE, ReasonCode.NOT_AVAILABLE_AS_OF),
    }


def test_duplicate_issuers_keep_the_ordinal_first_ticker_and_say_so() -> None:
    members = _ten_members()[:9]
    members.append(_member("googl", issuer="alphabet", a=2.0, b=9.5))
    members.append(_member("GOOG", issuer="alphabet", a=2.5, b=9.2))
    result = rank_members(members, [HIGHER, LOWER])

    assert "GOOG" in {m.ticker for m in result.ranked}
    assert "GOOGL" not in {m.ticker for m in result.ranked}
    (diagnostic,) = result.diagnostics
    assert diagnostic.kind is RankDiagnosticKind.DUPLICATE_ISSUER
    assert diagnostic.tickers == ("GOOG", "GOOGL")
    assert "canonical representative for ranking only" in diagnostic.message
    assert "does not assert that the share classes are economically equivalent" in diagnostic.message


def test_a_kept_class_that_lacks_a_metric_excludes_the_issuer_and_names_both_classes() -> None:
    members = _ten_members()[:9]
    members.append(_member("GOOG", issuer="alphabet", a=_unavailable(ReasonCode.MISSING_FACT, "no sales"), b=9.2))
    members.append(_member("GOOGL", issuer="alphabet", a=2.5, b=9.5))
    result = rank_members(members, [HIGHER, LOWER])

    assert [e.ticker for e in result.exclusions] == ["GOOG"]
    assert "GOOGL" not in {e.ticker for e in result.eligible}
    lacking = [d for d in result.diagnostics if d.kind is RankDiagnosticKind.KEPT_CLASS_LACKS_METRIC]
    assert len(lacking) == 1
    assert lacking[0].tickers == ("GOOG", "GOOGL")
    assert "GOOG" in lacking[0].message
    assert "GOOGL" in lacking[0].message


def test_a_kept_class_that_lacks_a_metric_no_other_class_has_adds_no_naming_diagnostic() -> None:
    members = _ten_members()[:9]
    members.append(_member("GOOG", issuer="alphabet", a=_unavailable(), b=9.2))
    members.append(_member("GOOGL", issuer="alphabet", a=_unavailable(), b=9.5))
    result = rank_members(members, [HIGHER, LOWER])

    assert [e.ticker for e in result.exclusions] == ["GOOG"]
    assert RankDiagnosticKind.KEPT_CLASS_LACKS_METRIC not in {d.kind for d in result.diagnostics}


def test_a_dropped_class_missing_a_metric_does_not_matter() -> None:
    members = _ten_members()
    members.append(_member("ZZZ", issuer="issuer-T01", a=_unavailable(), b=_unavailable()))
    result = rank_members(members, [HIGHER, LOWER])

    assert len(result.ranked) == 10
    assert result.exclusions == ()


def test_the_output_is_the_same_for_every_permutation_of_a_small_set() -> None:
    members = [
        _member("T1", a=3.0, b=1.0),
        _member("T2", a=2.0, b=_unavailable()),
        _member("ALPHA", issuer="dual", a=1.0, b=2.0),
        _member("ALPHB", issuer="dual", a=9.0, b=9.0),
        _member("T5", a=2.0, b=1.0),
    ]
    baseline = rank_members(members, [HIGHER, LOWER])
    for permutation in itertools.permutations(members):
        assert rank_members(permutation, [HIGHER, LOWER]) == baseline


def test_the_output_is_the_same_for_shuffles_of_a_ten_member_set() -> None:
    members = _ten_members()
    baseline = rank_members(members, [HIGHER, LOWER])
    shuffler = random.Random(20261026)
    for _ in range(8):
        shuffled = list(members)
        shuffler.shuffle(shuffled)
        assert rank_members(shuffled, [HIGHER, LOWER]) == baseline


def test_the_order_of_the_metrics_orders_the_columns() -> None:
    result = rank_members(_ten_members(), [LOWER, HIGHER])
    top = result.ranked[0]
    assert (top.ticker, top.values, top.ranks) == ("T02", (1.0, 9.0), (1.0, 2.0))


def test_an_empty_universe_is_below_the_minimum() -> None:
    result = rank_members([], [HIGHER])
    assert result.ranked == ()
    assert result.eligible == ()
    assert [d.kind for d in result.diagnostics] == [RankDiagnosticKind.BELOW_MINIMUM]


def test_results_for_metrics_that_were_not_requested_are_ignored() -> None:
    members = [_member(f"T{n:02d}", a=float(n), extra=_unavailable()) for n in range(1, 11)]
    result = rank_members(members, [HIGHER])
    assert len(result.ranked) == 10
    assert result.ranked[0].ticker == "T10"


def test_no_metrics_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one metric"):
        rank_members(_ten_members(), [])


def test_duplicate_metric_names_are_refused() -> None:
    with pytest.raises(ValueError, match="unique"):
        rank_members(_ten_members(), [HIGHER, RankMetric("a", RankDirection.LOWER_IS_BETTER)])


def test_tickers_repeated_after_upper_casing_are_refused() -> None:
    members = [_member("abc", a=1.0), _member("ABC", issuer="other", a=2.0)]
    with pytest.raises(ValueError, match="unique after upper-casing"):
        rank_members(members, [HIGHER])


def test_a_ticker_with_surrounding_whitespace_is_stored_stripped_and_upper_cased() -> None:
    assert RankMember("  goog \t", "alphabet", {}).ticker == "GOOG"


def test_tickers_that_differ_only_in_whitespace_and_case_are_refused() -> None:
    members = [_member(" goog", issuer="a", a=1.0), _member("GOOG", issuer="b", a=2.0)]
    with pytest.raises(ValueError, match="unique after upper-casing"):
        rank_members(members, [HIGHER])


def test_the_issuer_key_is_compared_exactly() -> None:
    members = [_member("T01", issuer="Alphabet", a=1.0), _member("T02", issuer="alphabet", a=2.0)]
    result = rank_members(members, [HIGHER])
    assert [m.ticker for m in result.eligible] == ["T01", "T02"]
    assert result.diagnostics[0].kind is RankDiagnosticKind.BELOW_MINIMUM


def test_a_member_without_an_entry_for_a_requested_metric_is_refused() -> None:
    members = [_member("T01", a=1.0), _member("T02", b=1.0)]
    with pytest.raises(ValueError, match="no result for metric"):
        rank_members(members, [HIGHER])


@pytest.mark.parametrize(("ticker", "issuer"), [("", "x"), ("  ", "x"), ("T", ""), ("T", "  ")])
def test_a_blank_ticker_or_issuer_key_is_refused(ticker: str, issuer: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        RankMember(ticker, issuer, {})


def test_a_result_that_lost_its_reason_is_refused_rather_than_ranked() -> None:
    broken = _unavailable()
    object.__setattr__(broken, "reason_code", None)
    members = [_member("T01", a=broken)]
    with pytest.raises(ValueError, match="carries no reason"):
        rank_members(members, [HIGHER])
