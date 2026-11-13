"""The documents of a refresh job: its events, its progress and the document a poll returns.

A refresh job records one event when a job of the refresh starts and one when it finishes. An event is built, and its
serialized size measured, once, when the application records it (:func:`event_recorder`); a poll builds nothing and
selects among the recorded events, and its response encodes the ones it returns. A finished event carries the job's
result as the refresh summary lists it and, unless the job raised, the job's analysis: the same document
``POST /v1/analyses`` returns, with its ``provider_check`` element null, as
``runs show --json`` writes a stored run, because the refresh's one provider check is reported in ``summary``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analysis_engine.api.documents import AnalysisDocument, AnalysisTextDocument
from investment_analysis_engine.api.responses import document_body
from investment_analysis_engine.application.refresh import build_refresh_result_document
from investment_analysis_engine.application.refresh_jobs import EventRecorder, RefreshJobView
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.workspace.refresh import RefreshJobFinished, RefreshJobStarted, RefreshProgress
from investment_analysis_engine.workspace_documents.refresh import RefreshResultDocument, RefreshSummaryDocument

type RefreshEventKind = Literal["started", "finished"]
"""Whether a refresh job's event records a job starting or finishing."""

REFRESH_EVENT_KIND_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {"started": "refresh-event", "finished": "refresh-event"}
)
"""The glossary term that explains each kind of refresh event; one entry explains both."""


class RefreshEventDocument(BaseModel):
    """One event of a refresh job: a job of the refresh started, or finished.

    ``sequence`` counts the job's events from 1 in the order they were recorded. ``position`` is the entry's 0-based
    place in the refresh, the same as a saved run's ``batch_position`` and the index of an ``entries[i]`` error; it is
    not the 1-based ``entry_number`` of a watchlist. ``result`` and ``analysis`` are null for a started event, and
    ``analysis`` is also null for a job that stopped because of an unexpected problem.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    kind: RefreshEventKind
    position: int = Field(ge=0)
    ticker: str
    method_id: str
    result: RefreshResultDocument | None = Field(
        description="The job's entry as the refresh summary lists it; null for a started event."
    )
    analysis: AnalysisDocument | None = Field(
        description=(
            "The job's analysis, as POST /v1/analyses returns it, with its provider_check element null; null for a "
            "started event and for a job that stopped because of an unexpected problem."
        )
    )

    @model_validator(mode="after")
    def _consistent(self) -> "RefreshEventDocument":
        """Require a finished event to carry its result and a started event to carry neither result nor analysis."""
        if (self.kind == "finished") != (self.result is not None):
            raise ValueError("result is set if and only if the event is finished.")
        if self.analysis is not None and self.result is None:
            raise ValueError("analysis is set only on a finished event.")
        return self


class RefreshTotalsDocument(BaseModel):
    """How far the refresh has come."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    admitted: int = Field(ge=0, description="Jobs that have started.")
    finished: int = Field(ge=0, description="Jobs that have finished.")
    remaining: int = Field(ge=0, description="Jobs not yet started; above zero after a stop.")


class RefreshJobDocument(BaseModel):
    """A refresh job as it is now, with the events recorded after the sequence the poll named.

    ``state`` is an open vocabulary: ``running``, ``stopping``, ``completed``, ``stopped`` and ``failed``. ``summary``
    is set for ``completed`` and ``stopped``, ``failure`` for ``failed``; the events already recorded are kept in
    either case.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    refresh_id: UUID = Field(description="The refresh's ID, which is the job's and the ID of every run it saves.")
    watchlist_id: UUID | None = Field(description="The watchlist refreshed; null for a refresh of a list of entries.")
    state: str = Field(description="running, stopping, completed, stopped or failed; treat any other value as running.")
    totals: RefreshTotalsDocument
    events: tuple[RefreshEventDocument, ...] = Field(
        description="The events after the requested sequence, up to 1,048,576 bytes; at least one when one is waiting."
    )
    next_after: int = Field(description="The last sequence in events, or the requested one when there are none.")
    has_more: bool = Field(description="Whether recorded events remain after those returned; poll again at once.")
    summary: RefreshSummaryDocument | None = Field(
        description="The refresh summary, provider check included, once the job completed or stopped; null otherwise."
    )
    failure: FailureEnvelope | None = Field(description="Why the job failed after it was accepted; null otherwise.")

    @model_validator(mode="after")
    def _consistent(self) -> "RefreshJobDocument":
        """Require the summary or the failure to match the state."""
        if (self.summary is not None) != (self.state in {"completed", "stopped"}):
            raise ValueError("summary is set if and only if the state is completed or stopped.")
        if (self.failure is not None) != (self.state == "failed"):
            raise ValueError("failure is set if and only if the state is failed.")
        return self


def _analysis_of(run: StrategyRun, result: RefreshResultDocument) -> AnalysisDocument:
    """Return a finished job's analysis document: the strategy's document and its text, with no provider check."""
    return AnalysisDocument(
        analysis_run_id=result.analysis_run_id,
        document=run.document(None),
        text=AnalysisTextDocument(
            concise=run.render_text(None, PresentationMode.CONCISE),
            details=run.render_text(None, PresentationMode.DETAILS),
            diagnostics=run.render_text(None, PresentationMode.DIAGNOSTICS),
        ),
    )


def _event_of(sequence: int, progress: RefreshProgress[StrategyRun]) -> RefreshEventDocument:
    """Build the event document of one progress event."""
    if isinstance(progress, RefreshJobStarted):
        return RefreshEventDocument(
            sequence=sequence,
            kind="started",
            position=progress.position,
            ticker=progress.ticker,
            method_id=progress.selection.method_id,
            result=None,
            analysis=None,
        )
    assert isinstance(progress, RefreshJobFinished)  # a progress event is one of the two
    result = build_refresh_result_document(progress.result)
    return RefreshEventDocument(
        sequence=sequence,
        kind="finished",
        position=progress.position,
        ticker=result.ticker,
        method_id=result.method_id,
        result=result,
        analysis=None if progress.produced is None else _analysis_of(progress.produced, result),
    )


def event_recorder() -> EventRecorder[RefreshEventDocument]:
    """Return the function that builds an event and measures it, which the refresh job calls once per event."""

    def record(sequence: int, progress: RefreshProgress[StrategyRun]) -> tuple[RefreshEventDocument, int]:
        event = _event_of(sequence, progress)
        return event, len(document_body(event))

    return record


def build_job_document(
    view: RefreshJobView[RefreshEventDocument], failure: FailureEnvelope | None
) -> RefreshJobDocument:
    """Build the job document of a view; ``failure`` is the envelope of the view's failure, when it has one."""
    return RefreshJobDocument(
        refresh_id=view.refresh_id,
        watchlist_id=view.watchlist_id,
        state=view.state.value,
        totals=RefreshTotalsDocument(
            admitted=view.totals.admitted, finished=view.totals.finished, remaining=view.totals.remaining
        ),
        events=tuple(item.event for item in view.events),
        next_after=view.next_after,
        has_more=view.has_more,
        summary=None if view.outcome is None else view.outcome.document,
        failure=failure,
    )


__all__ = [
    "REFRESH_EVENT_KIND_TERMS",
    "RefreshEventKind",
    "RefreshEventDocument",
    "RefreshJobDocument",
    "RefreshTotalsDocument",
    "build_job_document",
    "event_recorder",
]
