"""The ``runs compare`` document: the stored runs of one refresh as one table, and its text rendering.

The table is rebuilt from storage only. The builder reads the stored runs it is given and the headline function each
declared strategy supplies; it calls no provider, cache or clock and recalculates nothing. It names no strategy:
the columns, each with its evidence codec and headline function, are injected by the composition root.

Rows are the refresh's tickers in watchlist order, which is each ticker's lowest batch position. Columns are the
strategies present in the refresh, in the order the columns are given; a run of a strategy no longer declared
follows them, named by its stored method identifier.

A run the table cannot read still has its row. A run stored under an older version, or for a strategy no longer
declared, shows its outcome (read from the stored envelope's status, which needs no decoding) and "—" for its
cells, and the document states why its headline is missing. A run whose evidence is invalid refuses the whole table.
"""

import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.reporting.headline import (
    UNIT_MULTIPLE,
    UNIT_PERCENT,
    UNIT_POINTS,
    UNSPECIFIED_CURRENCY_PER_SHARE,
    CellKind,
    Headline,
    HeadlineCell,
)
from investment_analysis_engine.reporting.presentation import format_money
from investment_analysis_engine.workspace.codecs import (
    EvidenceCodec,
    InvalidStoredRunError,
    UnsupportedRunVersionError,
    decode_evidence,
)
from investment_analysis_engine.workspace.repositories.analysis_runs import StoredRefreshRun

CellStatusValue = Literal["ok", "unavailable", "not_applicable", "input_unavailable", "invalid_input", "provider_error"]
"""The values a cell's status takes: a calculation status or a metric status."""

HeadlineUnavailable = Literal["unsupported_version", "strategy_not_declared", "no_result_stored"]
"""Why a run has no headline: an older stored version, an undeclared strategy, or no stored result at all."""

MISSING: str = "—"
"""What the text table shows for a value that is absent."""

_NO_RUN = "no stored run"
_UNREADABLE = ("unsupported_version", "strategy_not_declared")
_PER_SHARE_SUFFIX = " per share"
_SUPPORTED_RUN_SCHEMA_VERSION = 3
_SUPPORTED_PROJECTION_VERSION = 1


def no_runs_message(refresh_id: UUID) -> str:
    """Return the one message for a refresh with no stored run.

    Storage cannot tell an unknown ID from a refresh run with ``--no-save``, so the message does not guess which.
    """
    return f"No runs are stored for refresh {refresh_id}. The ID is unknown, or the refresh was run with --no-save."


class DuplicateRefreshRunsError(ValueError):
    """The refresh holds more than one run of a ticker and strategy, which the table cannot show.

    The command reports it as ``invalid_input``; the runs themselves are valid, the refresh simply holds more than
    one table cell can show.
    """


class _Document(BaseModel):
    """Shared strictness: frozen, no extra keys."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CompareCellDocument(_Document):
    """One headline cell of a run."""

    key: str = Field(description="The cell's stable key.")
    label: str = Field(description="The column header the text table uses for the cell.")
    kind: CellKind
    value: float | str | None = Field(description="The number or text; null when the run has none.")
    unit: str | None = Field(description="The unit of a number: percent, points, multiple, or '<currency> per share'.")
    status: CellStatusValue | None = Field(description="The status of a number cell's value; null for a text cell.")
    reason_code: ReasonCode | None = Field(description="The reason code the result carries for the cell, if any.")


class CompareHeadlineDocument(_Document):
    """One run's headline: its cells, the fiscal period end it used and its taxonomy."""

    cells: tuple[CompareCellDocument, ...]
    period_end: DocumentTimestamp | None = Field(
        description="The fiscal period end the run used; null if not recorded."
    )
    period_end_label: str | None = Field(description="What the period end is, in the strategy's own words.")
    taxonomy: str | None = Field(description="The filing taxonomy; null where the run records none.")


class CompareRunDocument(_Document):
    """One stored run in the table."""

    analysis_run_id: UUID
    outcome: RunOutcome = Field(description="The run's outcome, read from its stored envelope.")
    requested_as_of: DocumentTimestamp | None = Field(
        description="The point in time the run asked for; null means now."
    )
    headline: CompareHeadlineDocument | None = Field(
        description="The run's cells; null when headline_unavailable is set."
    )
    headline_unavailable: HeadlineUnavailable | None = Field(description="Why the run has no headline, if it has none.")

    @model_validator(mode="after")
    def _one_of_headline_or_reason(self) -> Self:
        """Require exactly one of the headline and the reason it is missing."""
        if (self.headline is None) == (self.headline_unavailable is None):
            raise ValueError("A run has a headline or the reason it has none, and not both.")
        return self


class CompareStrategyDocument(_Document):
    """One column group: a strategy present in the refresh."""

    analysis_id: str
    method_id: str
    alias: str | None = Field(description="The strategy's command alias; null for a strategy no longer declared.")
    label: str = Field(description="The strategy's display name; its stored method identifier if no longer declared.")
    declared: bool


class CompareEntryDocument(_Document):
    """One ticker's run of one strategy."""

    method_id: str
    run: CompareRunDocument | None = Field(description="The stored run; null when the ticker has none for this column.")


class CompareRowDocument(_Document):
    """One ticker, with an entry for each strategy in column order."""

    ticker: str
    entries: tuple[CompareEntryDocument, ...]


class RunsCompareDocument(_Document):
    """The whole ``runs compare --json`` output.

    ``schema_version`` is this document's own lineage and is independent of every other document's.
    """

    schema_version: Literal[1] = 1
    refresh_id: UUID
    watchlist_id: UUID | None = Field(description="The watchlist the refresh ran; null if no readable run records it.")
    watchlist_name: str | None = Field(description="The watchlist's name when the refresh ran.")
    strategies: tuple[CompareStrategyDocument, ...] = Field(description="The columns, in order.")
    rows: tuple[CompareRowDocument, ...] = Field(description="The tickers, in watchlist order.")


@dataclass(frozen=True)
class CompareColumn:
    """One declared strategy as the table needs it: its identity, display names, evidence codec and headline."""

    analysis_id: str
    method_id: str
    alias: str
    label: str
    codec: EvidenceCodec
    headline: Callable[[object], Headline]


@dataclass(frozen=True)
class _Resolved:
    """One run turned into its document entry, with the watchlist its envelope recorded, if it was decoded."""

    document: CompareRunDocument
    watchlist: tuple[UUID, str] | None


def _versions_supported(row: Mapping[str, Any], codec: EvidenceCodec) -> bool:
    """Apply the version rule of ``decode_evidence`` to a stored row's indexed columns, with no decoding.

    ``decode_evidence`` remains the authority; this lets a run of an older version be recognized without decoding an
    envelope whose other fields may no longer parse.
    """
    stored = (
        row["run_schema_version"],
        row["config_schema_version"],
        row["method_version"],
        row["result_schema_version"],
        row["evidence_codec_version"],
        row["projection_version"],
    )
    return stored == (
        _SUPPORTED_RUN_SCHEMA_VERSION,
        codec.config_schema_version,
        codec.method_version,
        codec.result_schema_version,
        codec.evidence_codec_version,
        _SUPPORTED_PROJECTION_VERSION,
    )


def _cell_document(cell: HeadlineCell) -> CompareCellDocument:
    return CompareCellDocument(
        key=cell.key,
        label=cell.label,
        kind=cell.kind,
        value=cell.value,
        unit=cell.unit,
        status=None if cell.status is None else cell.status.value,  # type: ignore[arg-type]
        reason_code=cell.reason_code,
    )


def _headline_document(headline: Headline) -> CompareHeadlineDocument:
    return CompareHeadlineDocument(
        cells=tuple(_cell_document(cell) for cell in headline.cells),
        period_end=headline.period_end,
        period_end_label=headline.period_end_label,
        taxonomy=headline.taxonomy,
    )


def _without_headline(record: StoredRefreshRun, reason: HeadlineUnavailable, requested: datetime | None) -> _Resolved:
    document = CompareRunDocument(
        analysis_run_id=record.analysis_run_id,
        outcome=record.status,
        requested_as_of=requested,
        headline=None,
        headline_unavailable=reason,
    )
    return _Resolved(document, None)


def _resolve(record: StoredRefreshRun, column: CompareColumn | None) -> _Resolved:
    """Turn one stored run into its entry.

    Raises:
        InvalidStoredRunError: If the run's envelope or evidence is invalid, naming the run.
    """
    if column is None:
        return _without_headline(record, "strategy_not_declared", None)
    if not _versions_supported(record.row, column.codec):
        return _without_headline(record, "unsupported_version", None)
    try:
        run = record.envelope()
    except ValueError as exc:
        raise InvalidStoredRunError(
            f"Analysis Run {record.analysis_run_id} could not be read: "
            "its stored record is malformed or does not match its summary."
        ) from exc
    codecs = {(column.analysis_id, column.method_id): column.codec}
    try:
        evidence = decode_evidence(run, codecs)
    except UnsupportedRunVersionError:
        return _without_headline(record, "unsupported_version", run.requested_as_of)
    except InvalidStoredRunError as exc:
        raise InvalidStoredRunError(
            f"Analysis Run {record.analysis_run_id} could not be read: its stored evidence is invalid."
        ) from exc
    watchlist = (
        None if run.watchlist_id is None or run.watchlist_name is None else (run.watchlist_id, run.watchlist_name)
    )
    if evidence is None:
        return _Resolved(_without_headline(record, "no_result_stored", run.requested_as_of).document, watchlist)
    document = CompareRunDocument(
        analysis_run_id=record.analysis_run_id,
        outcome=record.status,
        requested_as_of=run.requested_as_of,
        headline=_headline_document(column.headline(evidence)),
        headline_unavailable=None,
    )
    return _Resolved(document, watchlist)


def _duplicates(runs: Sequence[StoredRefreshRun], columns: Mapping[tuple[str, str], CompareColumn]) -> list[str]:
    """Name each ticker and strategy that more than one run holds."""
    counts = Counter((run.ticker, run.analysis_id, run.method_id) for run in runs)
    return [
        f"{ticker} {columns[(analysis, method)].alias if (analysis, method) in columns else method}"
        for (ticker, analysis, method), count in counts.items()
        if count > 1
    ]


def build_runs_compare(
    refresh_id: UUID, runs: Sequence[StoredRefreshRun], columns: Sequence[CompareColumn]
) -> RunsCompareDocument:
    """Build the table of one refresh from its stored runs, in batch order.

    Args:
        refresh_id: The refresh the runs belong to.
        runs: The refresh's stored runs, in batch order.
        columns: The declared strategies in column order.

    Raises:
        ValueError: If there are no runs; the command checks for that first.
        DuplicateRefreshRunsError: If a ticker has more than one run of a strategy.
        InvalidStoredRunError: If a run's envelope or evidence is invalid.
    """
    if not runs:
        raise ValueError(no_runs_message(refresh_id))
    declared = {(column.analysis_id, column.method_id): column for column in columns}
    duplicates = _duplicates(runs, declared)
    if duplicates:
        raise DuplicateRefreshRunsError(
            f"Refresh {refresh_id} holds more than one run of the same ticker and strategy: "
            f"{', '.join(duplicates)}. The table shows one run in each cell and cannot choose between them."
        )
    present = {(run.analysis_id, run.method_id) for run in runs}
    ordered = [key for key in declared if key in present]
    ordered += [key for key in dict.fromkeys((run.analysis_id, run.method_id) for run in runs) if key not in declared]
    resolved = {run.analysis_run_id: _resolve(run, declared.get((run.analysis_id, run.method_id))) for run in runs}
    tickers = list(dict.fromkeys(run.ticker for run in runs))
    rows = []
    for ticker in tickers:
        mine = {
            (run.analysis_id, run.method_id): resolved[run.analysis_run_id].document
            for run in runs
            if run.ticker == ticker
        }
        rows.append(
            CompareRowDocument(
                ticker=ticker,
                entries=tuple(CompareEntryDocument(method_id=key[1], run=mine.get(key)) for key in ordered),
            )
        )
    watchlist = next((item.watchlist for item in resolved.values() if item.watchlist is not None), None)
    return RunsCompareDocument(
        refresh_id=refresh_id,
        watchlist_id=None if watchlist is None else watchlist[0],
        watchlist_name=None if watchlist is None else watchlist[1],
        strategies=tuple(
            CompareStrategyDocument(
                analysis_id=key[0],
                method_id=key[1],
                alias=declared[key].alias if key in declared else None,
                label=declared[key].label if key in declared else key[1],
                declared=key in declared,
            )
            for key in ordered
        ),
        rows=tuple(rows),
    )


# The text rendering ---------------------------------------------------------------------------------------------


def _minus(text: str) -> str:
    """Write a leading minus as the true minus sign."""
    return "−" + text[1:] if text.startswith("-") else text


def format_cell(cell: CompareCellDocument) -> str:
    """Format a cell's value for the table: percent as ``18.4%``, points bare, multiples as ``12.3x``, money prefixed.

    A per-share amount is written by ``format_money``: the number, then the currency, or ``(currency unspecified)``.
    A value that is absent is "—".
    """
    value = cell.value
    if value is None:
        return MISSING
    if cell.kind is CellKind.TEXT:
        return str(value)
    number = float(value)
    if not math.isfinite(number):
        return MISSING
    unit = cell.unit or ""
    if unit == UNIT_PERCENT:
        text = f"{number:.1f}%"
    elif unit == UNIT_POINTS:
        text = f"{number:.1f}"
    elif unit == UNIT_MULTIPLE:
        text = f"{number:.1f}x"
    elif unit.endswith(_PER_SHARE_SUFFIX):
        currency = None if unit == UNSPECIFIED_CURRENCY_PER_SHARE else unit.removesuffix(_PER_SHARE_SUFFIX)
        text = format_money(number, currency)
    else:
        text = f"{number:.2f} {unit}".strip()
    return _minus(text)


def _cell_columns(document: RunsCompareDocument) -> list[list[str]]:
    """Return, for each strategy, the headers of its cell columns, taken verbatim from the runs' cell labels."""
    result: list[list[str]] = []
    for index in range(len(document.strategies)):
        labels: list[list[str]] = []
        for row in document.rows:
            run = row.entries[index].run
            if run is not None and run.headline is not None:
                labels.append([cell.label for cell in run.headline.cells])
        width = max((len(item) for item in labels), default=0)
        result.append(
            [
                " / ".join(dict.fromkeys(item[position] for item in labels if position < len(item)))
                for position in range(width)
            ]
        )
    return result


def _entry_cells(run: CompareRunDocument | None, headers: list[str]) -> list[str]:
    """Return the formatted cells of one entry, then its outcome, matched to the strategy's cell columns."""
    if run is None:
        absent = [_NO_RUN, *([MISSING] * len(headers))]
        return absent if headers else [_NO_RUN]
    cells = [MISSING] * len(headers)
    if run.headline is not None:
        for position, cell in enumerate(run.headline.cells):
            cells[position] = format_cell(cell)
    return [*cells, run.outcome.value]


def _table(document: RunsCompareDocument) -> list[str]:
    headers = _cell_columns(document)
    group_row = [
        "",
        *[
            value
            for index, strategy in enumerate(document.strategies)
            for value in [strategy.label, *([""] * len(headers[index]))]
        ],
    ]
    label_row = ["Ticker", *[value for item in headers for value in [*item, "Outcome"]]]
    body = [
        [
            row.ticker,
            *[value for index, entry in enumerate(row.entries) for value in _entry_cells(entry.run, headers[index])],
        ]
        for row in document.rows
    ]
    grid = [group_row, label_row, *body]
    widths = [max(len(line[column]) for line in grid) for column in range(len(label_row))]
    return ["  ".join(text.ljust(width) for text, width in zip(line, widths, strict=True)).rstrip() for line in grid]


def _period_lines(document: RunsCompareDocument) -> list[str]:
    lines: list[str] = []
    width = max(len(row.ticker) for row in document.rows)
    for row in document.rows:
        parts = []
        for index, entry in enumerate(row.entries):
            headline = None if entry.run is None else entry.run.headline
            if headline is None or headline.period_end_label is None:
                continue
            when = MISSING if headline.period_end is None else headline.period_end.date().isoformat()
            parts.append(f"{document.strategies[index].label}: {headline.period_end_label} {when}")
        if parts:
            lines.append(f"  {row.ticker:<{width}}  " + " · ".join(parts))
    return lines


def _count(number: int, singular: str, plural: str) -> str:
    return f"{number} {singular if number == 1 else plural}"


def render_runs_compare_text(document: RunsCompareDocument) -> str:
    """Render the table, then the period ends, any unreadable runs, the requested as-of dates and the run IDs."""
    title = f"Refresh {document.refresh_id}"
    if document.watchlist_name is not None:
        title += f' · watchlist "{document.watchlist_name}"'
    tickers = _count(len(document.rows), "ticker", "tickers")
    strategies = _count(len(document.strategies), "strategy", "strategies")
    title += f" · {tickers} · {strategies}"
    lines = [title, "", *_table(document)]
    runs = [
        (row.ticker, document.strategies[index], entry.run)
        for row in document.rows
        for index, entry in enumerate(row.entries)
        if entry.run is not None
    ]
    period = _period_lines(document)
    if period:
        lines += ["", "Period ends", *period]
    unreadable = [run.analysis_run_id for _t, _s, run in runs if run.headline_unavailable in _UNREADABLE]
    if unreadable:
        lines += [
            "",
            "Could not be read (stored under an older version, or for a strategy no longer declared): "
            + ", ".join(str(item) for item in unreadable),
        ]
    requested = list(
        dict.fromkeys(
            "now" if run.requested_as_of is None else run.requested_as_of.date().isoformat() for _t, _s, run in runs
        )
    )
    if len(requested) > 1:
        lines += ["", "Requested as-of: " + ", ".join(requested)]
    lines += ["", "Runs (open one with: ian runs show <run-id>)"]
    width = max(len(row.ticker) for row in document.rows)
    lines += [
        f"  {ticker:<{width}}  {strategy.alias or strategy.method_id:<14} {run.analysis_run_id}"
        for ticker, strategy, run in runs
    ]
    return "\n".join(lines)


__all__ = [
    "MISSING",
    "CellStatusValue",
    "CompareCellDocument",
    "CompareColumn",
    "CompareEntryDocument",
    "CompareHeadlineDocument",
    "CompareRowDocument",
    "CompareRunDocument",
    "CompareStrategyDocument",
    "DuplicateRefreshRunsError",
    "HeadlineUnavailable",
    "RunsCompareDocument",
    "build_runs_compare",
    "format_cell",
    "no_runs_message",
    "render_runs_compare_text",
]
