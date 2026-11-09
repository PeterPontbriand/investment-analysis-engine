"""Whether the anchor annual filing is stale at the boundary: the rule, its two tables and its messages.

The anchor annual filing is stale when the next annual report was overdue at the boundary and none had been filed by
it. The age runs from the anchor's fiscal year-end, never from its filing date. The rule never warns early: each
allowance is the most generous regular deadline for the form plus any automatic extension, and each relief period is
applied to every filer.

``next_report_due`` is the anchor ``year_end`` plus one calendar year, plus seven days (a 53-week fiscal year), plus
the form's allowance (:data:`ALLOWANCES`), then extended by the relief period its original due date falls in
(:data:`RELIEF_PERIODS`). The boundary's date is the UTC date of the effective execution time. The anchor is stale
when that date is after ``next_report_due``; on the due date itself it is not.

Both tables are the single declaration of these figures. ``STEP_3_5_SHARED_DEFINITIONS.md`` states the same tables and
a test compares the two.
"""

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final

from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd

NEXT_REPORT_SLACK_DAYS: Final = 7
"""Days added to the next fiscal year-end, so a 53-week fiscal year is never judged late."""


@dataclass(frozen=True)
class FormAllowance:
    """The time after a fiscal year-end that an annual report of one form may take, at its most generous.

    Attributes:
        forms: The forms the allowance applies to.
        year_end_from: The first fiscal year-end the allowance applies to; ``None`` for every year-end before the next
            row's. Rows of one form are listed newest first.
        months: Calendar months after the fiscal year-end.
        days: Days after those months.
    """

    forms: tuple[str, ...]
    year_end_from: date | None
    months: int
    days: int


ALLOWANCES: Final[tuple[FormAllowance, ...]] = (
    FormAllowance(("10-K", "10-K/A"), None, 0, 105),
    FormAllowance(("20-F", "20-F/A"), date(2011, 12, 15), 4, 15),
    FormAllowance(("20-F", "20-F/A"), None, 6, 15),
    FormAllowance(("40-F", "40-F/A"), None, 0, 120),
)
"""Every form's allowance after the fiscal year-end; the first row whose forms and year-end match applies."""


@dataclass(frozen=True)
class ReliefPeriod:
    """A regulator's blanket extension of annual-report deadlines.

    Attributes:
        original_due_from: The first original due date the relief covers.
        original_due_to: The last original due date the relief covers, inclusive.
        extra_days: The days granted.
    """

    original_due_from: date
    original_due_to: date
    extra_days: int


RELIEF_PERIODS: Final[tuple[ReliefPeriod, ...]] = (ReliefPeriod(date(2020, 3, 1), date(2020, 7, 1), 45),)
"""Relief periods, applied to every form and every filer."""


@dataclass(frozen=True)
class AnchorFilingEvidence:
    """The anchor annual filing and whether it is stale at the boundary.

    Attributes:
        year_end: The anchor's fiscal year-end.
        form: The anchor's form.
        accession: The anchor's accession.
        filing_date: The anchor's filing date; ``None`` when the submissions data does not date it.
        next_report_due: The latest date the next annual report was due.
        stale: Whether the boundary's date is after ``next_report_due``.
    """

    year_end: date
    form: str
    accession: str
    filing_date: date | None
    next_report_due: date
    stale: bool


def boundary_date(effective_as_of: datetime) -> date:
    """Return the date of the boundary: the UTC date of the effective execution time."""
    if effective_as_of.utcoffset() is None:
        raise ValueError("The boundary must be timezone-aware.")
    return effective_as_of.astimezone(UTC).date()


def _add_months(day: date, months: int) -> date:
    """Return ``day`` moved by calendar months, clamped to the end of a shorter month."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _next_year_end(year_end: date) -> date:
    """Return the same date one calendar year later; 29 February becomes 1 March, the later date."""
    try:
        return year_end.replace(year=year_end.year + 1)
    except ValueError:
        return date(year_end.year + 1, 3, 1)


def _allowance(form: str, year_end: date) -> FormAllowance:
    """Return the allowance for ``form`` at ``year_end``."""
    normalized = form.strip().upper()
    for row in ALLOWANCES:
        if normalized in row.forms and (row.year_end_from is None or year_end >= row.year_end_from):
            return row
    raise ValueError(f"No annual-report allowance is declared for form {form!r}.")


def next_report_due(year_end: date, form: str) -> date:
    """Return the latest date the annual report after the one for ``year_end`` was due.

    Raises:
        ValueError: If no allowance is declared for ``form``.
    """
    allowance = _allowance(form, year_end)
    shifted = _next_year_end(year_end) + timedelta(days=NEXT_REPORT_SLACK_DAYS)
    original = _add_months(shifted, allowance.months) + timedelta(days=allowance.days)
    for relief in RELIEF_PERIODS:
        if relief.original_due_from <= original <= relief.original_due_to:
            return original + timedelta(days=relief.extra_days)
    return original


def assess_anchor_filing(anchor: AnchorYearEnd, effective_as_of: datetime) -> AnchorFilingEvidence:
    """Return the anchor filing with its next due date and whether it is stale at the boundary."""
    due = next_report_due(anchor.year_end, anchor.form)
    return AnchorFilingEvidence(
        year_end=anchor.year_end,
        form=anchor.form,
        accession=anchor.accession,
        filing_date=anchor.filing_date,
        next_report_due=due,
        stale=boundary_date(effective_as_of) > due,
    )


def stale_anchor_message(evidence: AnchorFilingEvidence, effective_as_of: datetime) -> str:
    """Return the warning message for a stale anchor filing."""
    filed = "" if evidence.filing_date is None else f", filed {evidence.filing_date.isoformat()}"
    return (
        f"The newest annual report filed by {boundary_date(effective_as_of).isoformat()} is for the fiscal year ended "
        f"{evidence.year_end.isoformat()} ({evidence.form}{filed}). The next one was due by "
        f"{evidence.next_report_due.isoformat()} at the latest, and none had been filed."
    )


def stale_anchor_warnings(evidence: AnchorFilingEvidence | None, effective_as_of: datetime) -> tuple[str, ...]:
    """Return the warning a stale anchor adds to a result, and nothing for a fresh or absent one."""
    if evidence is None or not evidence.stale:
        return ()
    return (stale_anchor_message(evidence, effective_as_of),)


def stale_market_cap_reason(boundary: date) -> str:
    """Return the reason message of a market cap refused because the anchor filing is stale."""
    return (
        "Market cap unavailable: the anchor filing is stale, so its share count is not the count at "
        f"{boundary.isoformat()}."
    )
