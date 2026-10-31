"""The ``runs compare`` text table's bands and wrapped lists, over documents built by hand."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from itertools import count
from uuid import UUID

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.reporting.headline import CellKind
from investment_analysis_engine.workspace_documents.runs_compare import (
    TEXT_WIDTH,
    CompareCellDocument,
    CompareEntryDocument,
    CompareHeadlineDocument,
    CompareRowDocument,
    CompareRunDocument,
    CompareStrategyDocument,
    HeadlineUnavailable,
    RunsCompareDocument,
    render_runs_compare_text,
)

_IDS = count(1)
_REFRESH = UUID("00000000-0000-4000-8000-0000000000aa")
_RUNS_HEADING = "Runs (open one with: ian runs show <run-id>)"
_UNREADABLE_LEAD_IN = "Could not be read (stored under an older version, or for a strategy no longer declared):"
_LEGEND = "† marks a value labelled FCF/share CAGR, not the first label of its column header"

Period = tuple[str, date | None]


def _text(label: str, value: str | None) -> CompareCellDocument:
    return CompareCellDocument(
        key=label, label=label, kind=CellKind.TEXT, value=value, unit=None, status=None, reason_code=None
    )


def _percent(label: str, value: float | None) -> CompareCellDocument:
    return CompareCellDocument(
        key=label, label=label, kind=CellKind.NUMBER, value=value, unit="percent", status="ok", reason_code=None
    )


def _money(label: str, value: float | None) -> CompareCellDocument:
    return CompareCellDocument(
        key=label, label=label, kind=CellKind.NUMBER, value=value, unit="USD per share", status="ok", reason_code=None
    )


def _run(
    cells: Sequence[CompareCellDocument] | None,
    outcome: str = "completed",
    period: Period | None = None,
    unavailable: HeadlineUnavailable = "no_result_stored",
) -> CompareRunDocument:
    """Return a run with ``cells``, or without a headline, for ``unavailable``, when ``cells`` is None."""
    headline = None
    if cells is not None:
        label, when = period if period is not None else (None, None)
        stamp = None if when is None else datetime(when.year, when.month, when.day, tzinfo=UTC)
        headline = CompareHeadlineDocument(cells=tuple(cells), period_end=stamp, period_end_label=label, taxonomy=None)
    return CompareRunDocument(
        analysis_run_id=UUID(int=next(_IDS)),
        outcome=RunOutcome(outcome),
        requested_as_of=None,
        headline=headline,
        headline_unavailable=None if cells is not None else unavailable,
    )


def _document(labels: Sequence[str], rows: dict[str, Sequence[CompareRunDocument | None]]) -> RunsCompareDocument:
    return RunsCompareDocument(
        refresh_id=_REFRESH,
        watchlist_id=None,
        watchlist_name=None,
        strategies=tuple(
            CompareStrategyDocument(
                analysis_id=f"a{index}", method_id=f"m{index}", alias=f"s{index}", label=label, declared=True
            )
            for index, label in enumerate(labels)
        ),
        rows=tuple(
            CompareRowDocument(
                ticker=ticker,
                entries=tuple(CompareEntryDocument(method_id=f"m{index}", run=run) for index, run in enumerate(runs)),
            )
            for ticker, runs in rows.items()
        ),
    )


def _table_lines(document: RunsCompareDocument) -> list[str]:
    """Return the table's lines: everything between the title and the legend, period ends or Runs block."""
    lines = render_runs_compare_text(document).split("\n")
    end = next(index for index, line in enumerate(lines) if line in {_LEGEND, "Period ends", _RUNS_HEADING})
    return lines[2 : end - 1]


def _section(text: str, heading: str) -> list[str]:
    lines = text.split("\n")
    start = lines.index(heading) + 1
    end = lines.index("", start) if "" in lines[start:] else len(lines)
    return lines[start:end]


def _reviewed(strategies: int) -> RunsCompareDocument:
    """The reviewed refresh: four strategies, or five with a hand-built Piotroski F-Score."""
    graham = ("earnings input period end", date(2024, 6, 30))
    unrecorded = ("earnings input period end", None)
    span = ("selected span end", date(2025, 1, 1))
    rows: dict[str, list[CompareRunDocument | None]] = {
        "SYNTH": [
            _run([_text("Trend", "Bullish"), _text("RSI", "100.0")]),
            _run([_money("Max price", 36.69), _percent("Margin", None)], period=graham),
            _run([_money("Value", 66.28), _percent("Margin", None)], period=graham),
            _run([_percent("FCF CAGR", 10.2), _percent("EPS CAGR", 17.6), _text("Class", "PASS")], period=span),
            _run(
                [_text("Score", "7 of 9"), _text("Completeness", "complete")],
                period=("fiscal year-end", date(2024, 9, 28)),
            ),
        ],
        "MISSING": [
            _run([_text("Trend", None), _text("RSI", "100.0")], "unavailable"),
            _run([_money("Max price", None), _percent("Margin", None)], "unavailable", unrecorded),
            None,
            _run(
                [_percent("FCF CAGR", None), _percent("EPS CAGR", None), _text("Class", "INDETERMINATE")],
                "unavailable",
                ("selected span end", None),
            ),
            _run(
                [_text("Score", "5 of 7"), _text("Completeness", "partial")],
                period=("fiscal year-end", date(2025, 12, 31)),
            ),
        ],
        "ERROR": [
            _run(None, "failed"),
            _run([_money("Max price", None), _percent("Margin", None)], "failed", unrecorded),
            _run([_money("Value", None), _percent("Margin", None)], "failed", unrecorded),
            _run([_percent("FCF/share CAGR", 10.2), _percent("EPS CAGR", 17.6), _text("Class", "PASS")], period=span),
            _run(None, "failed"),
        ],
    }
    labels = ["Momentum", "Graham Number", "Graham Growth", "FCF Growth", "Piotroski F-Score"]
    return _document(labels[:strategies], {ticker: runs[:strategies] for ticker, runs in rows.items()})


def test_the_four_strategy_refresh_is_two_bands_and_its_period_ends_wrap() -> None:
    text = render_runs_compare_text(_reviewed(4))

    assert text.split("\n")[2:16] == [
        "         Momentum                      Graham Number                       Graham Growth",
        "Ticker   Trend     RSI    Outcome      Max price      Margin  Outcome      Value          Margin  Outcome",
        "SYNTH    Bullish   100.0  completed    36.69 USD      —       completed    66.28 USD      —       completed",
        "MISSING  —         100.0  unavailable  —              —       unavailable  no stored run  —       —",
        "ERROR    —         —      failed       —              —       failed       —              —       failed",
        "",
        "         FCF Growth",
        "Ticker   FCF CAGR / FCF/share CAGR  EPS CAGR  Class          Outcome",
        "SYNTH    10.2%                      17.6%     PASS           completed",
        "MISSING  —                          —         INDETERMINATE  unavailable",
        "ERROR    10.2%†                     17.6%     PASS           completed",
        "",
        _LEGEND,
        "",
    ]
    assert _section(text, "Period ends") == [
        "  SYNTH    Graham Number: earnings input period end 2024-06-30 · Graham Growth: earnings input period end"
        " 2024-06-30",
        "           FCF Growth: selected span end 2025-01-01",
        "  MISSING  Graham Number: earnings input period end not recorded · FCF Growth: selected span end not recorded",
        "  ERROR    Graham Number: earnings input period end not recorded · Graham Growth: earnings input period end"
        " not recorded",
        "           FCF Growth: selected span end 2025-01-01",
    ]


def test_a_fifth_strategy_joins_the_second_band() -> None:
    text = render_runs_compare_text(_reviewed(5))

    assert text.split("\n")[2:16] == [
        "         Momentum                      Graham Number                       Graham Growth",
        "Ticker   Trend     RSI    Outcome      Max price      Margin  Outcome      Value          Margin  Outcome",
        "SYNTH    Bullish   100.0  completed    36.69 USD      —       completed    66.28 USD      —       completed",
        "MISSING  —         100.0  unavailable  —              —       unavailable  no stored run  —       —",
        "ERROR    —         —      failed       —              —       failed       —              —       failed",
        "",
        "         FCF Growth                                                       Piotroski F-Score",
        "Ticker   FCF CAGR / FCF/share CAGR  EPS CAGR  Class          Outcome      Score              Completeness"
        "  Outcome",
        "SYNTH    10.2%                      17.6%     PASS           completed    7 of 9             complete"
        "      completed",
        "MISSING  —                          —         INDETERMINATE  unavailable  5 of 7             partial"
        "       completed",
        "ERROR    10.2%†                     17.6%     PASS           completed    —                  —"
        "             failed",
        "",
        _LEGEND,
        "",
    ]
    assert _section(text, "Period ends") == [
        "  SYNTH    Graham Number: earnings input period end 2024-06-30 · Graham Growth: earnings input period end"
        " 2024-06-30",
        "           FCF Growth: selected span end 2025-01-01 · Piotroski F-Score: fiscal year-end 2024-09-28",
        "  MISSING  Graham Number: earnings input period end not recorded · FCF Growth: selected span end not recorded",
        "           Piotroski F-Score: fiscal year-end 2025-12-31",
        "  ERROR    Graham Number: earnings input period end not recorded · Graham Growth: earnings input period end"
        " not recorded",
        "           FCF Growth: selected span end 2025-01-01",
    ]


def _sized(widths: Sequence[int]) -> RunsCompareDocument:
    """Strategies whose single value column is ``widths`` wide, so each is that plus ``2 + 9`` characters wide."""
    return _document(
        [f"S{index}" for index in range(len(widths))],
        {"T": [_run([_text("V", "x" * width)]) for width in widths]},
    )


def _bands(lines: list[str]) -> list[list[str]]:
    return [band.split("\n") for band in "\n".join(lines).split("\n\n")]


def test_strategies_that_fit_share_one_band() -> None:
    bands = _bands(_table_lines(_sized([20, 20])))

    assert len(bands) == 1
    assert bands[0][0].split() == ["S0", "S1"]


def test_a_band_may_be_exactly_the_text_width() -> None:
    bands = _bands(_table_lines(_sized([44, 44])))

    assert len(bands) == 1, "Two strategies of 55 characters, a 6 character ticker column and gaps make 120."
    assert max(len(line) for line in bands[0]) == TEXT_WIDTH


def test_one_character_over_the_text_width_starts_a_new_band() -> None:
    bands = _bands(_table_lines(_sized([44, 45])))

    assert [band[0].split() for band in bands] == [["S0"], ["S1"]]
    assert all(len(line) <= TEXT_WIDTH for band in bands for line in band)


def test_eleven_strategies_fill_bands_in_order_and_are_never_reordered() -> None:
    document = _document(
        [f"S{index:02d}" for index in range(11)],
        {ticker: [_run([_text("V", "x" * 19)]) for _ in range(11)] for ticker in ("AAA", "BB")},
    )

    bands = _bands(_table_lines(document))

    assert [band[0].split() for band in bands] == [
        ["S00", "S01", "S02"],
        ["S03", "S04", "S05"],
        ["S06", "S07", "S08"],
        ["S09", "S10"],
    ]
    assert all(len(line) <= TEXT_WIDTH for band in bands for line in band)


def test_a_strategy_wider_than_the_text_width_has_a_band_of_its_own() -> None:
    bands = _bands(_table_lines(_sized([20, 130, 20])))

    assert [band[0].split() for band in bands] == [["S0"], ["S1"], ["S2"]]
    assert [max(len(line) for line in band) > TEXT_WIDTH for band in bands] == [False, True, False]


def test_a_wide_strategy_first_still_leaves_the_rest_to_share_a_band() -> None:
    bands = _bands(_table_lines(_sized([130, 20, 20])))

    assert [band[0].split() for band in bands] == [["S0"], ["S1", "S2"]]


def test_every_band_repeats_the_rows_in_the_same_order() -> None:
    bands = _bands(_table_lines(_reviewed(5)))

    assert len(bands) == 2
    first, second = ([line.split()[0] for line in band[1:]] for band in bands)
    assert first == second == ["Ticker", "SYNTH", "MISSING", "ERROR"]


def test_the_legend_comes_once_after_the_last_band_wherever_the_marker_is() -> None:
    document = _document(
        ["FCF Growth", "Wide"],
        {
            "A": [_run([_percent("FCF CAGR", 1.0)]), _run([_text("V", "x" * 100)])],
            "B": [_run([_percent("FCF/share CAGR", 2.0)]), _run([_text("V", "x" * 100)])],
        },
    )

    lines = render_runs_compare_text(document).split("\n")

    assert lines.count(_LEGEND) == 1
    marked = next(index for index, line in enumerate(lines) if "2.0%†" in line)
    last_row = max(index for index, line in enumerate(lines) if line.startswith("B "))
    assert marked < last_row < lines.index(_LEGEND)
    assert lines[lines.index(_LEGEND) - 1] == ""


def test_period_ends_wrap_before_the_entry_that_would_pass_the_limit() -> None:
    label = "p" * 20
    when = date(2024, 1, 2)
    document = _document(
        ["One", "Two", "Three"],
        {"AB": [_run([_text("V", "x")], period=(label, when)) for _ in range(3)]},
    )

    assert _section(render_runs_compare_text(document), "Period ends") == [
        f"  AB  One: {label} 2024-01-02 · Two: {label} 2024-01-02",
        f"      Three: {label} 2024-01-02",
    ]


def test_a_period_entry_wider_than_the_text_width_is_left_whole() -> None:
    long_label = "q" * 130
    document = _document(
        ["One", "Two"],
        {
            "AB": [
                _run([_text("V", "x")], period=(long_label, date(2024, 1, 2))),
                _run([_text("V", "x")], period=("end", None)),
            ]
        },
    )

    block = _section(render_runs_compare_text(document), "Period ends")

    assert block == [f"  AB  One: {long_label} 2024-01-02", "      Two: end not recorded"]
    assert len(block[0]) > TEXT_WIDTH


def _unreadable_lines(count_of_ids: int) -> tuple[list[str], list[str]]:
    """Return the rendered lines from the lead-in on, and the IDs of the unreadable runs."""
    document = _document(
        ["One"],
        {f"T{index}": [_run(None, "failed", unavailable="unsupported_version")] for index in range(count_of_ids)},
    )
    ids = [str(entry.run.analysis_run_id) for row in document.rows for entry in row.entries if entry.run is not None]
    lines = render_runs_compare_text(document).split("\n")
    return lines[lines.index(_UNREADABLE_LEAD_IN) :], ids


def test_the_unreadable_run_ids_wrap_after_a_comma_under_a_lead_in_of_their_own() -> None:
    lines, ids = _unreadable_lines(5)

    assert lines[:4] == [
        _UNREADABLE_LEAD_IN,
        f"  {ids[0]}, {ids[1]}, {ids[2]},",
        f"  {ids[3]}, {ids[4]}",
        "",
    ]
    assert all(len(line) <= TEXT_WIDTH for line in lines[:3])


def test_a_single_unreadable_run_id_is_on_the_line_after_the_lead_in() -> None:
    lines, ids = _unreadable_lines(1)

    assert lines[:3] == [_UNREADABLE_LEAD_IN, f"  {ids[0]}", ""]
    assert len(lines[1]) <= TEXT_WIDTH
