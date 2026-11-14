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
from types import MappingProxyType
from typing import Any, ClassVar, Final, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.reporting.documents.timestamp import DocumentAsOf, DocumentTimestamp
from investment_analysis_engine.reporting.headline import (
    CellKind,
    CellUnit,
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
from investment_analysis_engine.workspace.runs import AnalysisRun

type CellStatusValue = Literal[
    "ok", "unavailable", "not_applicable", "input_unavailable", "invalid_input", "provider_error"
]
"""The values a cell's status takes: a calculation status or a metric status."""

type HeadlineUnavailable = Literal["unsupported_version", "strategy_not_declared", "no_result_stored"]
"""Why a run has no headline: an older stored version, an undeclared strategy, or no stored result at all."""

HEADLINE_UNAVAILABLE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "unsupported_version": "headline-unavailable",
        "strategy_not_declared": "headline-unavailable",
        "no_result_stored": "headline-unavailable",
    }
)
"""The glossary term that explains each reason a run has no headline; one entry explains all three."""

MISSING: str = "—"
"""What the text table shows for a value that is absent."""

TEXT_WIDTH: int = 120
"""The width, in characters, the text table's bands and the lists under it are wrapped to.

A band holds as many strategies as fit; a strategy or an entry wider than this on its own is left whole."""

_GAP = 2
_GAP_TEXT = " " * _GAP
_NO_RUN = "no stored run"
_NOT_RECORDED = "not recorded"
_MARKERS = ("†", "‡", "§", "¶")
_UNREADABLE = ("unsupported_version", "strategy_not_declared")
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

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.INVALID_INPUT


class _Document(BaseModel):
    """Shared strictness: frozen, no extra keys."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CompareCellDocument(_Document):
    """One headline cell of a run."""

    key: str = Field(description="The cell's stable key.")
    label: str = Field(description="The column header the text table uses for the cell.")
    term: str = Field(description="The id of the glossary term that explains the label.")
    kind: CellKind
    value: float | str | None = Field(
        description=(
            "The number or text; null when the run has none. A percent value is the percentage itself: 18.4 means "
            "18.4 %."
        )
    )
    unit: CellUnit | None = Field(description="The unit of a number cell; null for a text cell.")
    currency: str | None = Field(
        description=(
            "The ISO 4217 currency of a per-share amount; null for any other cell, and for a per-share cell whose "
            "run recorded no currency."
        )
    )
    status: CellStatusValue | None = Field(description="The status of a number cell's value; null for a text cell.")
    reason_code: ReasonCode | None = Field(description="The reason code the result carries for the cell, if any.")

    @model_validator(mode="after")
    def _unit_and_currency_follow_the_kind(self) -> Self:
        """Require a unit for a number, no unit or currency for a text, and a currency only for a per-share unit."""
        if self.kind is CellKind.TEXT and (self.unit is not None or self.currency is not None):
            raise ValueError("A text cell has no unit and no currency.")
        if self.kind is CellKind.NUMBER and self.unit is None:
            raise ValueError("A number cell has a unit.")
        if self.currency is not None and self.unit is not CellUnit.PER_SHARE:
            raise ValueError("Only a per-share cell has a currency.")
        return self


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
    requested_as_of: DocumentAsOf | None = Field(
        description="The point in time the run asked for, as it was asked: a date or an instant; null means now."
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
    term: str | None = Field(
        description="The id of the glossary term that explains the strategy; null for a strategy no longer declared."
    )
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

    schema_version: Literal[6] = 6
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
    term: str
    codec: EvidenceCodec
    headline: Callable[[object], Headline]


class StoredRecord(Protocol):
    """What the headline builder needs of a stored run: its ID, its indexed row and its envelope."""

    @property
    def analysis_run_id(self) -> UUID:
        """The run's ID."""
        ...

    @property
    def row(self) -> Mapping[str, Any]:
        """The stored row, whose indexed columns carry the run's versions."""
        ...

    def envelope(self) -> AnalysisRun:
        """Return the fully decoded run, raising ``ValueError`` if the stored envelope is malformed."""
        ...


@dataclass(frozen=True)
class RunHeadline:
    """A run's headline, or the reason it has none, with the facts only its decoded envelope gives.

    Exactly one of ``headline`` and ``unavailable`` is set. ``requested_as_of`` and ``watchlist`` come from the
    envelope, so they are ``None`` for a run the builder did not decode.
    """

    headline: CompareHeadlineDocument | None
    unavailable: HeadlineUnavailable | None
    requested_as_of: datetime | None = None
    watchlist: tuple[UUID, str] | None = None


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
        term=cell.term,
        kind=cell.kind,
        value=cell.value,
        unit=cell.unit,
        currency=cell.currency,
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


class _EnvelopeRequest(BaseModel):
    """The one field of a stored envelope the run's request is read from, which no strategy's codec is needed for."""

    model_config = ConfigDict(extra="ignore")

    requested_as_of: datetime | None = None


def _requested_as_of(record: StoredRecord) -> datetime | None:
    """Read the point in time a run asked for from its stored envelope, with no decoding of its strategy's parts.

    ``None`` means the run asked for now. A run of a strategy no longer declared, or stored under an older version,
    still has this field, so it is read without the strategy's codec.

    Raises:
        InvalidStoredRunError: If the stored envelope cannot be read, naming the run.
    """
    try:
        return _EnvelopeRequest.model_validate_json(record.row["envelope_json"]).requested_as_of
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidStoredRunError(
            f"Analysis Run {record.analysis_run_id} could not be read: "
            "its stored record is malformed or does not match its summary."
        ) from exc


def resolve_headline(record: StoredRecord, column: CompareColumn | None) -> RunHeadline:
    """Build a stored run's headline, or say why it has none: the one builder the table and the overview share.

    A run of a strategy no longer declared, or stored under an older version, or with no stored result, has no
    headline and says which; no other run is without one. Every run reports the point in time it asked for, read
    from its envelope, so ``None`` there always means "now".

    Raises:
        InvalidStoredRunError: If the run's envelope or evidence is invalid, naming the run.
    """
    if column is None:
        return RunHeadline(None, "strategy_not_declared", _requested_as_of(record))
    if not _versions_supported(record.row, column.codec):
        return RunHeadline(None, "unsupported_version", _requested_as_of(record))
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
        return RunHeadline(None, "unsupported_version", run.requested_as_of)
    except InvalidStoredRunError as exc:
        raise InvalidStoredRunError(
            f"Analysis Run {record.analysis_run_id} could not be read: its stored evidence is invalid."
        ) from exc
    watchlist = (
        None if run.watchlist_id is None or run.watchlist_name is None else (run.watchlist_id, run.watchlist_name)
    )
    if evidence is None:
        return RunHeadline(None, "no_result_stored", run.requested_as_of, watchlist)
    return RunHeadline(_headline_document(column.headline(evidence)), None, run.requested_as_of, watchlist)


def strategy_document(analysis_id: str, method_id: str, column: CompareColumn | None) -> CompareStrategyDocument:
    """Return the strategy of a stored run: the declared column's names, or the stored method identifier if none."""
    return CompareStrategyDocument(
        analysis_id=analysis_id,
        method_id=method_id,
        alias=None if column is None else column.alias,
        label=method_id if column is None else column.label,
        term=None if column is None else column.term,
        declared=column is not None,
    )


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
    resolved = {
        run.analysis_run_id: resolve_headline(run, declared.get((run.analysis_id, run.method_id))) for run in runs
    }
    documents = {
        run.analysis_run_id: CompareRunDocument(
            analysis_run_id=run.analysis_run_id,
            outcome=run.status,
            requested_as_of=resolved[run.analysis_run_id].requested_as_of,
            headline=resolved[run.analysis_run_id].headline,
            headline_unavailable=resolved[run.analysis_run_id].unavailable,
        )
        for run in runs
    }
    tickers = list(dict.fromkeys(run.ticker for run in runs))
    rows = []
    for ticker in tickers:
        mine = {
            (run.analysis_id, run.method_id): documents[run.analysis_run_id] for run in runs if run.ticker == ticker
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
        strategies=tuple(strategy_document(key[0], key[1], declared.get(key)) for key in ordered),
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
    match cell.unit:
        case CellUnit.PERCENT:
            text = f"{number:.1f}%"
        case CellUnit.POINTS:
            text = f"{number:.1f}"
        case CellUnit.MULTIPLE:
            text = f"{number:.1f}x"
        case CellUnit.PER_SHARE:
            text = format_money(number, cell.currency)
        case None:
            text = f"{number:.2f}"
    return _minus(text)


def _column_labels(document: RunsCompareDocument) -> list[list[list[str]]]:
    """Return, for each strategy's cell columns, the distinct labels its runs give each, first seen first."""
    result: list[list[list[str]]] = []
    for index in range(len(document.strategies)):
        runs = [row.entries[index].run for row in document.rows]
        labelled = [[cell.label for cell in run.headline.cells] for run in runs if run is not None and run.headline]
        width = max((len(item) for item in labelled), default=0)
        result.append(
            [
                list(dict.fromkeys(item[position] for item in labelled if position < len(item)))
                for position in range(width)
            ]
        )
    return result


def _markers(labels: list[list[list[str]]]) -> dict[tuple[int, int, str], str]:
    """Assign a marker to each label that is not the first of its column, in the order the columns are met.

    A column whose runs give different labels (FCF-Growth on the total basis and on the per-share basis) is headed by
    all of them, and a value whose label is not the first one carries its marker, which the legend explains.
    """
    found = [
        (index, position, label)
        for index, columns in enumerate(labels)
        for position, column in enumerate(columns)
        for label in column[1:]
    ]
    return {key: _MARKERS[number] if number < len(_MARKERS) else f"[{number + 1}]" for number, key in enumerate(found)}


def _legend_lines(markers: dict[tuple[int, int, str], str]) -> list[str]:
    """Return one line per marker, naming the label it stands for; none when no column mixes labels."""
    return [
        f"{marker} marks a value labelled {label}, not the first label of its column header"
        for (_i, _p, label), marker in markers.items()
    ]


def _entry_cells(
    run: CompareRunDocument | None, headers: list[str], markers: dict[tuple[int, int, str], str], index: int
) -> list[str]:
    """Return the formatted cells of one entry, then its outcome, matched to the strategy's cell columns."""
    if run is None:
        absent = [_NO_RUN, *([MISSING] * len(headers))]
        return absent if headers else [_NO_RUN]
    cells = [MISSING] * len(headers)
    if run.headline is not None:
        for position, cell in enumerate(run.headline.cells):
            cells[position] = format_cell(cell) + markers.get((index, position, cell.label), "")
    return [*cells, run.outcome.value]


def _table(
    document: RunsCompareDocument, labels: list[list[list[str]]], markers: dict[tuple[int, int, str], str]
) -> list[str]:
    """Return the table as bands of strategies, each at most ``TEXT_WIDTH`` wide unless one strategy alone is wider.

    Strategies fill a band in column order; a strategy is never split or moved. Every band repeats the Ticker column,
    its strategy-name row, its column-heading row and every ticker row, and bands are separated by one blank line.
    """
    headers = [[" / ".join(column) for column in columns] for columns in labels]
    blocks = [
        [
            [strategy.label, *([""] * len(headers[index]))],
            [*headers[index], "Outcome"],
            *[_entry_cells(row.entries[index].run, headers[index], markers, index) for row in document.rows],
        ]
        for index, strategy in enumerate(document.strategies)
    ]
    ticker_column = ["", "Ticker", *[row.ticker for row in document.rows]]
    ticker_width = max(len(text) for text in ticker_column)
    widths = [[max(len(line[column]) for line in block) for column in range(len(block[0]))] for block in blocks]
    sizes = [sum(item) + _GAP * (len(item) - 1) for item in widths]
    bands: list[list[int]] = []
    used = 0
    for index, size in enumerate(sizes):
        if bands and used + _GAP + size <= TEXT_WIDTH:
            bands[-1].append(index)
            used += _GAP + size
        else:
            bands.append([index])
            used = ticker_width + _GAP + size
    lines: list[str] = []
    for band in bands:
        if lines:
            lines.append("")
        column_widths = [ticker_width, *[width for index in band for width in widths[index]]]
        for position, ticker_cell in enumerate(ticker_column):
            cells = [ticker_cell, *[text for index in band for text in blocks[index][position]]]
            lines.append(
                _GAP_TEXT.join(text.ljust(width) for text, width in zip(cells, column_widths, strict=True)).rstrip()
            )
    return lines


def _wrapped(first: str, entries: Sequence[str], separator: str, carry: str, indent: str) -> list[str]:
    """Join ``entries`` after ``first`` with ``separator``, starting a new line when the next would pass ``TEXT_WIDTH``.

    A line that breaks ends with ``carry`` in place of the separator, and the next line starts with ``indent``. An
    entry wider than the limit on its own is left whole.
    """
    lines: list[str] = []
    current = first + entries[0]
    for entry in entries[1:]:
        if len(current) + len(separator) + len(entry) > TEXT_WIDTH:
            lines.append(current + carry)
            current = indent + entry
        else:
            current += separator + entry
    lines.append(current)
    return lines


def _period_lines(document: RunsCompareDocument) -> list[str]:
    lines: list[str] = []
    width = max(len(row.ticker) for row in document.rows)
    for row in document.rows:
        parts = []
        for index, entry in enumerate(row.entries):
            headline = None if entry.run is None else entry.run.headline
            if headline is None or headline.period_end_label is None:
                continue
            when = _NOT_RECORDED if headline.period_end is None else headline.period_end.date().isoformat()
            parts.append(f"{document.strategies[index].label}: {headline.period_end_label} {when}")
        if parts:
            prefix = f"  {row.ticker:<{width}}  "
            lines += _wrapped(prefix, parts, " · ", "", " " * len(prefix))
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
    labels = _column_labels(document)
    markers = _markers(labels)
    lines = [title, "", *_table(document, labels, markers)]
    legend = _legend_lines(markers)
    if legend:
        lines += ["", *legend]
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
            "Could not be read (stored under an older version, or for a strategy no longer declared):",
            *_wrapped("  ", [str(item) for item in unreadable], ", ", ",", "  "),
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
    "HEADLINE_UNAVAILABLE_TERMS",
    "MISSING",
    "TEXT_WIDTH",
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
    "RunHeadline",
    "RunsCompareDocument",
    "StoredRecord",
    "build_runs_compare",
    "format_cell",
    "no_runs_message",
    "render_runs_compare_text",
    "resolve_headline",
    "strategy_document",
]
