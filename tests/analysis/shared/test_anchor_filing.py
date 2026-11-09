"""The stale-anchor rule: due dates per form, the relief period, the messages and the tables' agreement with the doc."""

import re
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from investment_analysis_engine.analysis.shared.anchor_filing import (
    ALLOWANCES,
    RELIEF_PERIODS,
    AnchorFilingEvidence,
    FormAllowance,
    assess_anchor_filing,
    boundary_date,
    next_report_due,
    stale_anchor_message,
    stale_anchor_warnings,
    stale_market_cap_reason,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd
from scripts.repository_root import REPOSITORY_ROOT

_SHARED_DEFINITIONS = (
    REPOSITORY_ROOT / "docs" / "project" / "milestones" / "v0.2" / "step-3.5" / "STEP_3_5_SHARED_DEFINITIONS.md"
)


def _anchor(year_end: date, form: str, filing_date: date | None = date(2024, 3, 1)) -> AnchorYearEnd:
    return AnchorYearEnd(
        year_end=year_end, accession="0000000000-24-000001", form=form, filing_date=filing_date, filing_dates={}
    )


def _at(day: date) -> datetime:
    """Return midday UTC of ``day``."""
    return datetime(day.year, day.month, day.day, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("form", "year_end", "due"),
    [
        ("10-K", date(2023, 12, 31), date(2025, 4, 22)),
        ("10-K/A", date(2023, 12, 31), date(2025, 4, 22)),
        ("10-K", date(2020, 2, 29), date(2021, 6, 21)),
        ("20-F", date(2011, 12, 14), date(2013, 7, 6)),
        ("20-F", date(2011, 12, 15), date(2013, 5, 7)),
        ("20-F/A", date(2011, 12, 15), date(2013, 5, 7)),
        ("20-F", date(2022, 10, 24), date(2024, 3, 15)),
        ("40-F", date(2023, 12, 31), date(2025, 5, 7)),
        ("40-F/A", date(2023, 12, 31), date(2025, 5, 7)),
    ],
)
def test_the_next_report_is_due_by_the_forms_allowance_and_the_day_after_it_the_anchor_is_stale(
    form: str, year_end: date, due: date
) -> None:
    assert next_report_due(year_end, form) == due
    on_the_day = assess_anchor_filing(_anchor(year_end, form), _at(due))
    after = assess_anchor_filing(_anchor(year_end, form), _at(due + timedelta(days=1)))
    assert (on_the_day.next_report_due, on_the_day.stale) == (due, False)
    assert (after.next_report_due, after.stale) == (due, True)


def test_a_twenty_f_year_end_a_day_before_the_four_month_rule_keeps_six_months() -> None:
    six = next_report_due(date(2011, 12, 14), "20-F")
    four = next_report_due(date(2011, 12, 15), "20-F")
    assert (six, four) == (date(2013, 7, 6), date(2013, 5, 7))


def test_a_month_end_clamps_to_the_last_day_of_a_shorter_month() -> None:
    # 2022-10-24 + 1 year + 7 days is 2023-10-31; four months on is 29 February 2024, plus 15 days.
    assert next_report_due(date(2022, 10, 24), "20-F") == date(2024, 3, 15)


def test_the_age_runs_from_the_year_end_never_from_the_filing_date() -> None:
    early = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K", date(2024, 2, 1)), _at(date(2025, 4, 23)))
    late = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K", date(2024, 12, 20)), _at(date(2025, 4, 23)))
    assert early.stale is late.stale is True
    assert early.next_report_due == late.next_report_due


def test_a_null_filing_date_is_kept_and_the_message_drops_its_clause() -> None:
    evidence = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K", None), _at(date(2025, 6, 1)))
    assert evidence.filing_date is None
    assert stale_anchor_message(evidence, _at(date(2025, 6, 1))) == (
        "The newest annual report filed by 2025-06-01 is for the fiscal year ended 2023-12-31 (10-K). "
        "The next one was due by 2025-04-22 at the latest, and none had been filed."
    )


def test_the_message_names_the_form_and_the_filing_date_in_iso_form() -> None:
    evidence = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K/A", date(2024, 3, 5)), _at(date(2025, 6, 1)))
    assert stale_anchor_message(evidence, _at(date(2025, 6, 1))) == (
        "The newest annual report filed by 2025-06-01 is for the fiscal year ended 2023-12-31 (10-K/A, filed "
        "2024-03-05). The next one was due by 2025-04-22 at the latest, and none had been filed."
    )


def test_a_fresh_or_absent_anchor_adds_no_warning() -> None:
    fresh = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K"), _at(date(2025, 4, 22)))
    stale = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K"), _at(date(2025, 4, 23)))
    assert stale_anchor_warnings(fresh, _at(date(2025, 4, 22))) == ()
    assert stale_anchor_warnings(None, _at(date(2025, 4, 22))) == ()
    assert stale_anchor_warnings(stale, _at(date(2025, 4, 23))) == (
        stale_anchor_message(stale, _at(date(2025, 4, 23))),
    )


def test_the_market_cap_message_names_the_boundary_date() -> None:
    assert stale_market_cap_reason(date(2025, 6, 1)) == (
        "Market cap unavailable: the anchor filing is stale, so its share count is not the count at 2025-06-01."
    )


def test_the_boundary_is_the_utc_date_of_the_effective_time() -> None:
    evening_in_the_us = datetime(2025, 4, 22, 21, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert evening_in_the_us.date() == date(2025, 4, 22)
    assert boundary_date(evening_in_the_us) == date(2025, 4, 23)
    assert assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K"), evening_in_the_us).stale is True


def test_a_boundary_without_a_time_zone_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        boundary_date(datetime(2025, 4, 22, 12))


def test_a_form_without_an_allowance_is_refused() -> None:
    with pytest.raises(ValueError, match="No annual-report allowance"):
        next_report_due(date(2023, 12, 31), "10-Q")


@pytest.mark.parametrize(
    ("year_end", "original", "due"),
    [
        (date(2018, 11, 9), date(2020, 2, 29), date(2020, 2, 29)),
        (date(2018, 11, 10), date(2020, 3, 1), date(2020, 4, 15)),
        (date(2018, 12, 31), date(2020, 4, 21), date(2020, 6, 5)),
        (date(2019, 3, 11), date(2020, 7, 1), date(2020, 8, 15)),
        (date(2019, 3, 12), date(2020, 7, 2), date(2020, 7, 2)),
    ],
)
def test_an_original_due_date_inside_the_relief_window_gets_forty_five_more_days(
    year_end: date, original: date, due: date
) -> None:
    assert date(year_end.year + 1, year_end.month, year_end.day) + timedelta(days=7 + 105) == original
    assert next_report_due(year_end, "10-K") == due


def test_the_relief_is_not_stale_until_forty_five_days_after_the_original_due_date() -> None:
    anchor = _anchor(date(2018, 12, 31), "10-K")
    assert assess_anchor_filing(anchor, _at(date(2020, 6, 5))).stale is False
    assert assess_anchor_filing(anchor, _at(date(2020, 6, 6))).stale is True


def test_the_relief_applies_to_every_form() -> None:
    assert next_report_due(date(2018, 12, 31), "40-F") == date(2020, 6, 20)
    assert next_report_due(date(2019, 1, 31), "20-F") == date(2020, 8, 6)


def _table_rows(heading: str, expected_columns: int) -> list[list[str]]:
    """Return the cells of the rows of the Shared definitions table whose header begins with ``heading``."""
    lines = _SHARED_DEFINITIONS.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(heading))
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == expected_columns, line
        rows.append(cells)
    return rows


def _allowance_key(row: FormAllowance, rows: tuple[FormAllowance, ...]) -> tuple[tuple[str, ...], str, int, int]:
    others = [other for other in rows if other is not row and other.forms == row.forms]
    if row.year_end_from is not None:
        condition = f"on or after {row.year_end_from.isoformat()}"
    elif others:
        condition = f"before {others[0].year_end_from}"
    else:
        condition = "every"
    return row.forms, condition, row.months, row.days


def test_the_allowance_table_in_the_code_is_the_table_in_the_shared_definitions() -> None:
    documented = []
    for forms, condition, allowance in _table_rows("| Forms | Fiscal year-ends | Allowance |", 3):
        match = re.fullmatch(r"(?:(\d+) calendar months \+ )?(\d+) days", allowance)
        assert match is not None, allowance
        documented.append((tuple(forms.split(", ")), condition, int(match.group(1) or 0), int(match.group(2))))
    declared = [_allowance_key(row, ALLOWANCES) for row in ALLOWANCES]
    assert sorted(documented) == sorted(declared)


def test_the_relief_table_in_the_code_is_the_table_in_the_shared_definitions() -> None:
    documented = []
    for window, days, _source in _table_rows("| Original due dates | Extra days | Source |", 3):
        first, last = window.split(" to ")
        documented.append((date.fromisoformat(first), date.fromisoformat(last), int(days)))
    declared = [(item.original_due_from, item.original_due_to, item.extra_days) for item in RELIEF_PERIODS]
    assert documented == declared


def test_the_evidence_is_a_plain_frozen_record() -> None:
    evidence = assess_anchor_filing(_anchor(date(2023, 12, 31), "10-K"), _at(date(2025, 4, 22)))
    assert isinstance(evidence, AnchorFilingEvidence)
    with pytest.raises(AttributeError):
        evidence.stale = True  # type: ignore[misc]
