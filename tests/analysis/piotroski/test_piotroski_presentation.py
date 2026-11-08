"""The Piotroski presenter, replay and headline: the approved layouts, display precision and the stored-run replay."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from itertools import count
from uuid import UUID

import pytest

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricResult
from investment_analysis_engine.reporting.headline import CellKind
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from investment_analysis_engine.strategies.piotroski import analyzer as analyzer_module
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiResult
from investment_analysis_engine.strategies.piotroski.calculation import NamedMetric
from investment_analysis_engine.strategies.piotroski.codec import decode_piotroski, encode_piotroski
from investment_analysis_engine.strategies.piotroski.presenter import (
    _against_zero,
    _multiple,
    _pair,
    _percent,
    _test_figures,
    completeness_text,
    render_piotroski,
    score_text,
)
from investment_analysis_engine.strategies.piotroski.replay import headline_piotroski, project_piotroski
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategies.piotroski.vocabulary import CheckOutcome
from investment_analysis_engine.workspace_documents.runs_compare import (
    CompareEntryDocument,
    CompareRowDocument,
    CompareRunDocument,
    CompareStrategyDocument,
    RunsCompareDocument,
    _headline_document,
    render_runs_compare_text,
)
from tests.analysis.piotroski._statements_rig import run

AAPL_AS_OF = datetime(2025, 1, 15, tzinfo=UTC)
MNST_AS_OF = datetime(2026, 3, 31, tzinfo=UTC)
LIMITATION = (
    "Limitation: Follows the Piotroski nine-test structure, with the net change in shares outstanding in place of "
    "the paper's equity-issuance test; not an investment recommendation."
)

APPLE_LAYOUT = f"""AAPL — Piotroski F-Score: 7 of 9 (complete)
Fiscal year-end: 2024-09-28 · 10-K 0000320193-24-000123 · us-gaap
Industry class: manufacturer (SIC code as filed)

Profitability
  1 Positive ROA          pass         ROA 26.59% > 0
  2 Positive CFO          pass         CFO / assets 33.54% > 0
  3 Improving ROA         fail         ROA 26.59%, prior 27.50%
  4 Cash exceeds income   pass         CFO 118,254,000,000 USD > net income 93,736,000,000 USD
Leverage and liquidity
  5 Falling leverage      pass         long-term debt / assets 26.94%, prior 29.80%
  6 Improving liquidity   fail         current ratio 0.87x, prior 0.99x
  7 No dilution           pass         shares 15,116,786,000, prior 15,550,061,000
Efficiency
  8 Improving margin      pass         gross margin 46.21%, prior 44.13%
  9 Improving turnover    pass         asset turnover 1.11x, prior 1.09x

Source: SEC EDGAR; latest evidence available 2024-11-01
{LIMITATION}"""

NOTE = "Note: The usual reading of high and low scores applies to complete scores only."


def apple() -> PiotroskiResult:
    return run("aapl", as_of=AAPL_AS_OF)


def monster() -> PiotroskiResult:
    return run("mnst", as_of=MNST_AS_OF)


def test_apples_concise_output_is_the_approved_layout_exactly() -> None:
    assert render_piotroski(apple()) == APPLE_LAYOUT
    assert NOTE not in render_piotroski(apple())


def test_monsters_concise_output_is_a_partial_score_with_its_note() -> None:
    lines = render_piotroski(monster()).split("\n")
    assert lines[0] == "MNST — Piotroski F-Score: 5 of 6 (partial: tests 1, 3, 4 unavailable)"
    assert lines[1] == "Fiscal year-end: 2025-12-31 · 10-K 0001104659-26-020831 · us-gaap"
    by_number = {line.split()[0]: line for line in lines if line.startswith("  ")}
    for number in ("1", "3", "4"):
        assert " unavailable " in by_number[number]
        assert "Net income for 2025-12-31 is unavailable" in by_number[number]
    assert by_number["2"].endswith("pass         CFO / assets 27.18% > 0")
    assert by_number["5"].endswith("pass         long-term debt / assets 0.00%, prior 4.30%")
    assert by_number["6"].endswith("pass         current ratio 3.70x, prior 3.32x")
    assert by_number["7"].endswith("fail         shares 978,113,000, prior 973,079,000")
    assert by_number["8"].endswith("pass         gross margin 55.85%, prior 54.04%")
    assert by_number["9"].endswith("pass         asset turnover 1.07x, prior 0.77x")
    assert NOTE in lines
    assert lines.index(NOTE) < lines.index(next(line for line in lines if line.startswith("Source:")))


def test_a_partial_score_is_never_a_bare_number_or_x_of_nine() -> None:
    result = monster()
    assert score_text(result) == "5 of 6"
    assert completeness_text(result) == "partial (1, 3, 4 unavailable)"
    for mode in (PresentationMode.CONCISE, PresentationMode.DETAILS, PresentationMode.DIAGNOSTICS):
        first = render_piotroski(result, mode).split("\n")[0]
        assert " of 9" not in first
        assert "5 of 6" in first
    assert score_text(apple()) == "7 of 9"
    assert completeness_text(apple()) == "complete"


@pytest.mark.parametrize(
    ("left", "right", "shown"),
    [
        (0.123456, 0.123461, ("12.3456%", "12.3461%")),
        (0.5, 0.5, ("50.00%", "50.00%")),
        (0.2659, 0.2750, ("26.59%", "27.50%")),
        (0.123401, 0.123404, ("12.3401%", "12.3404%")),
    ],
)
def test_two_compared_values_that_round_equal_but_differ_show_more_digits_in_both(
    left: float, right: float, shown: tuple[str, str]
) -> None:
    assert _pair(left, right, _percent) == shown


def test_display_precision_adds_digits_for_multiples_and_for_a_value_compared_with_zero() -> None:
    assert _pair(1.0000001, 1.0000002, _multiple) == ("1.0000001x", "1.0000002x")
    assert _pair(0.87, 0.99, _multiple) == ("0.87x", "0.99x")
    assert _against_zero(0.0000004) == "0.00004%"
    assert _against_zero(0.1) == "10.00%"


def test_a_test_whose_two_ratios_differ_only_beyond_two_decimals_shows_both_with_enough_digits() -> None:
    base = apple().f_score
    assert base is not None
    third = base.tests[2]
    close = replace(
        third,
        ratios=(
            NamedMetric("roa_t", MetricResult.ok(0.26581)),
            NamedMetric("roa_t1", MetricResult.ok(0.26584)),
        ),
    )
    assert _test_figures(close) == "ROA 26.581%, prior 26.584%"
    assert close.outcome is CheckOutcome.FAIL


def test_details_add_each_operand_with_its_year_end_and_value() -> None:
    text = render_piotroski(apple(), PresentationMode.DETAILS)
    assert text.startswith(APPLE_LAYOUT)
    assert "Details — operands of each test" in text
    assert "1 Positive ROA — pass" in text
    assert "  net_income_t: 93.736 billion USD at 2024-09-28" in text
    assert "  total_assets_t1: 352.583 billion USD at 2023-09-30" in text
    assert "  shares_t: 15.117 billion shares at 2024-09-28" in text


def test_diagnostics_add_provenance_and_the_assembly_notes() -> None:
    text = render_piotroski(apple(), PresentationMode.DIAGNOSTICS)
    assert "Provenance" in text
    assert (
        "- 1 net_income_t: provider field us-gaap:NetIncomeLoss; accession 0000320193-24-000123; filing date 2024-11-01"
    ) in text
    assert "accession 0000320193-23-000106; filing date 2023-11-03" in text
    assert "- Fiscal year-end t: 2024-09-28." in text
    assert "- Fiscal year-end t-2: 2022-09-24." in text
    assert "Execution status: ok" in text


def test_a_run_without_tests_says_why_and_shows_no_score() -> None:
    result = run("aapl", as_of=datetime(2022, 6, 1, tzinfo=UTC))
    lines = render_piotroski(result).split("\n")
    assert lines[0] == "AAPL — Piotroski F-Score: unavailable"
    assert "Fiscal year-end: unavailable" in lines
    assert any(line.startswith("Reason: ") for line in lines)
    assert score_text(result) is None
    assert completeness_text(result) is None


def test_the_json_document_holds_the_nine_tests_and_the_result_fields() -> None:
    document = json.loads(render_piotroski(apple(), PresentationMode.JSON))
    assert list(document)[:3] == ["schema_version", "analysis", "method"]
    assert document["analysis"] == "piotroski"
    assert document["score"] == {"status": "ok", "value": 7.0, "reason_code": None, "reason": None}
    assert document["completeness"] == "complete"
    assert document["available_count"] == 9
    assert [test["number"] for test in document["tests"]] == list(range(1, 10))
    assert document["tests"][2]["outcome"] == "fail"
    assert document["anchor"]["accession"] == "0000320193-24-000123"
    assert document["industry_class"] == "manufacturer"
    assert document["taxonomy"] == "us-gaap"
    assert document["input_failure"] is None
    assert list(document)[-3:] == ["warnings", "limitations", "diagnostics"]


def test_the_stored_evidence_decodes_to_the_same_result_and_replays_the_live_text() -> None:
    result = monster()
    payload = encode_piotroski(result)
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
    restored = decode_piotroski(payload)
    assert restored == result
    for mode in (PresentationMode.CONCISE, PresentationMode.DETAILS, PresentationMode.DIAGNOSTICS):
        live = render_piotroski(result, mode)
        stored = project_piotroski(
            ReplayInputs(ticker="MNST", instrument_profile=None, presentation_inputs=None),
            restored,
            PiotroskiSelection(),
            ReplayOptions(mode=mode),
        )
        assert stored == live


def test_a_replay_calls_no_provider_resolver_clock_or_calculator(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = encode_piotroski(apple())

    def refuse(*_arguments: object, **_keywords: object) -> None:
        raise AssertionError("a replay renders stored evidence only")

    for name in (
        "calculate_f_score",
        "resolve_year_ends",
        "resolve_balance_sheet_values_at",
        "resolve_annual_values_at",
        "resolve_share_count_series",
        "resolve_industry_class",
        "anchor_year_end_scope",
    ):
        monkeypatch.setattr(analyzer_module, name, refuse)
    text = project_piotroski(
        ReplayInputs(ticker="AAPL", instrument_profile=None, presentation_inputs=None),
        decode_piotroski(payload),
        PiotroskiSelection(),
        ReplayOptions(),
    )
    assert text == APPLE_LAYOUT


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["result"].update({"method_version": 2}),
        lambda payload: payload["result"].update({"schema_version": "1"}),
        lambda payload: payload["result"].update({"strategy_id": "other"}),
        lambda payload: payload["result"].update({"unexpected": 1}),
        lambda payload: payload["result"].pop("taxonomy"),
        lambda payload: payload["result"].update({"ticker": "aapl"}),
    ],
)
def test_the_codec_rejects_evidence_that_does_not_match_the_declared_shape(mutate: object) -> None:
    payload = encode_piotroski(apple())
    assert callable(mutate)
    mutate(payload)
    with pytest.raises(ValueError, match=r"."):
        decode_piotroski(payload)


def test_the_headline_has_a_score_cell_a_completeness_cell_the_year_end_and_the_taxonomy() -> None:
    headline = headline_piotroski(apple())
    assert [(cell.key, cell.label, cell.kind, cell.value) for cell in headline.cells] == [
        ("score", "Score", CellKind.TEXT, "7 of 9"),
        ("completeness", "Completeness", CellKind.TEXT, "complete"),
    ]
    assert headline.period_end == datetime(2024, 9, 28, tzinfo=UTC)
    assert headline.period_end_label == "fiscal year-end"
    assert headline.taxonomy == "us-gaap"
    partial = headline_piotroski(monster())
    assert [cell.value for cell in partial.cells] == ["5 of 6", "partial (1, 3, 4 unavailable)"]
    none = headline_piotroski(run("aapl", as_of=datetime(2022, 6, 1, tzinfo=UTC)))
    assert [cell.value for cell in none.cells] == [None, None]
    assert none.period_end is None


_IDS = count(1)


def _compare_run(result: PiotroskiResult) -> CompareRunDocument:
    outcome = RunOutcome.from_status(result.execution_status)
    return CompareRunDocument(
        analysis_run_id=UUID(int=next(_IDS)),
        outcome=outcome,
        requested_as_of=None,
        headline=_headline_document(headline_piotroski(result)),
        headline_unavailable=None,
    )


def test_the_side_by_side_table_shows_the_score_and_completeness_cells() -> None:
    document = RunsCompareDocument(
        refresh_id=UUID(int=999),
        watchlist_id=None,
        watchlist_name=None,
        strategies=(
            CompareStrategyDocument(
                analysis_id="piotroski",
                method_id="piotroski",
                alias="piotroski",
                label="Piotroski F-Score",
                term="piotroski-strategy",
                declared=True,
            ),
        ),
        rows=tuple(
            CompareRowDocument(
                ticker=ticker, entries=(CompareEntryDocument(method_id="piotroski", run=_compare_run(result)),)
            )
            for ticker, result in (
                ("AAPL", apple()),
                ("MNST", monster()),
                ("BOLT", run("aapl", as_of=datetime(2022, 6, 1, tzinfo=UTC))),
            )
        ),
    )
    lines = render_runs_compare_text(document).split("\n")
    start = lines.index(next(line for line in lines if line.strip() == "Piotroski F-Score"))
    # The Score column is as wide as the strategy name above it, which the shared layout sizes by.
    assert lines[start : start + 5] == [
        "        Piotroski F-Score",
        f"{'Ticker':<8}{'Score':<19}{'Completeness':<31}Outcome",
        f"{'AAPL':<8}{'7 of 9':<19}{'complete':<31}completed",
        f"{'MNST':<8}{'5 of 6':<19}{'partial (1, 3, 4 unavailable)':<31}completed",
        f"{'BOLT':<8}{'—':<19}{'—':<31}unavailable",
    ]
    assert "fiscal year-end" in render_runs_compare_text(document)


def test_a_result_that_did_not_run_is_replayed_without_tests() -> None:
    failure = run("aapl", as_of=datetime(2022, 6, 1, tzinfo=UTC))
    assert failure.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    restored = decode_piotroski(encode_piotroski(failure))
    assert restored == failure
    assert restored.f_score is not None
    assert restored.anchor is None
