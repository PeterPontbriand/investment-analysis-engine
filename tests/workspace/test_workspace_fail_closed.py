"""Workspace dispatch fails closed: nothing that matches no declared strategy is handled as Momentum."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest

from src.cli_workspace import _method_id_for_alias
from src.core.strategy_errors import UndeclaredStrategyError
from src.strategies.fcf_growth.selection import FCFGrowthSelection
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.selection import MomentumSelection
from src.strategy_wiring import EVIDENCE_BY_KEY, RUN_SPECS_BY_KEY, STRATEGIES, run_spec_for
from src.workspace.capture import ExecutionCapture
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError, decode_evidence
from src.workspace.models import RunOutcome
from src.workspace.refresh import refresh_watchlist
from src.workspace.runs import AnalysisRun, Watchlist, WatchlistEntry
from src.workspace.strategy_types import NativeEvidence, SelectionMember
from tests._wiring import failure_code

STAMP = datetime(2026, 9, 10, 12, tzinfo=UTC)
RUN_ID = UUID("11111111-1111-4111-8111-111111111111")


@dataclass(frozen=True)
class _UndeclaredEvidence:
    """Evidence of a strategy that no descriptor declares."""

    ticker: str = "AAPL"


class _SubclassedMomentumRun(MomentumRun):
    """A subclass of a declared result type, which is not itself declared."""


def _run(analysis_id: str = "momentum", method_id: str = "sma_crossover") -> AnalysisRun:
    run = AnalysisRun(
        analysis_run_id=RUN_ID,
        ticker="AAPL",
        analysis_id="momentum",
        method_id="sma_crossover",
        config_schema_version=2,
        requested_config=MomentumSelection(short_window=2, long_window=3),
        started_at=STAMP,
        completed_at=STAMP,
        method_version=1,
        result_schema_version=3,
        evidence_codec_version=2,
        status=RunOutcome.FAILED,
        failure_reason_code="execution_error",
    )
    return run.model_copy(update={"analysis_id": analysis_id, "method_id": method_id})


def _encode(selection: SelectionMember, evidence: object) -> object:
    """Encode ``evidence`` the way a run does: with the run spec of ``selection``'s declared strategy."""
    return run_spec_for(selection).encode(cast(NativeEvidence, evidence))


def test_an_undeclared_evidence_type_is_rejected_not_encoded_as_momentum() -> None:
    with pytest.raises(UndeclaredStrategyError, match="_UndeclaredEvidence"):
        _encode(MomentumSelection(short_window=2, long_window=3), _UndeclaredEvidence())


def test_a_subclass_of_a_declared_result_type_is_rejected() -> None:
    subclassed = object.__new__(_SubclassedMomentumRun)
    with pytest.raises(UndeclaredStrategyError, match="_SubclassedMomentumRun") as error:
        _encode(MomentumSelection(short_window=2, long_window=3), subclassed)
    assert not isinstance(error.value, InvalidStoredRunError)


@pytest.mark.parametrize(
    "selection",
    [
        MomentumSelection(short_window=2, long_window=3),
        GrahamNumberSelection(),
        GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5),
        FCFGrowthSelection(),
    ],
    ids=["momentum", "graham-number", "graham-growth", "fcf-growth"],
)
def test_another_strategys_result_is_rejected_by_every_run_spec(selection: SelectionMember) -> None:
    others = [item for item in STRATEGIES if item.method_id != selection.method_id]
    for other in others:
        foreign = object.__new__(other.behavior.result_type)
        with pytest.raises(UndeclaredStrategyError, match=other.behavior.result_type.__name__):
            _encode(selection, foreign)


@pytest.mark.parametrize(
    ("analysis_id", "method_id"),
    [("undeclared", "undeclared"), ("momentum", "graham_number"), ("graham_number", "sma_crossover")],
)
def test_an_undeclared_analysis_method_pair_is_rejected_not_decoded_as_momentum(
    analysis_id: str, method_id: str
) -> None:
    with pytest.raises(UnsupportedRunVersionError, match="Unsupported") as error:
        decode_evidence(_run(analysis_id, method_id), EVIDENCE_BY_KEY)
    assert error.value.reason_code == "unsupported_run_version"


def test_a_run_with_no_result_decodes_to_none_when_its_pair_is_declared() -> None:
    assert decode_evidence(_run(), EVIDENCE_BY_KEY) is None


def test_decoding_with_no_codecs_rejects_even_a_momentum_run() -> None:
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(_run(), {})


def test_an_undeclared_alias_is_rejected_where_the_command_line_resolves_it() -> None:
    assert _method_id_for_alias("momentum") == "sma_crossover"
    for alias in ("undeclared", "Momentum", "sma_crossover", ""):
        with pytest.raises(UndeclaredStrategyError, match="alias"):
            _method_id_for_alias(alias)


def test_run_spec_for_names_a_selection_whose_strategy_is_not_declared() -> None:
    selection = MomentumSelection(short_window=2, long_window=3)
    assert run_spec_for(selection) is RUN_SPECS_BY_KEY[("momentum", "sma_crossover")]
    with pytest.raises(UndeclaredStrategyError, match="sma_crossover"):
        run_spec_for(selection, {})


class _Lookup:
    def __init__(self, watchlist: Watchlist) -> None:
        self._watchlist = watchlist

    def get(self, name: str) -> Watchlist | None:
        del name
        return self._watchlist


class _Sink:
    def insert(self, run: AnalysisRun) -> None:
        del run
        raise AssertionError("A job with no run spec must not be stored.")


def test_a_refresh_job_whose_strategy_has_no_run_spec_fails_as_that_jobs_error() -> None:
    selection = MomentumSelection(short_window=2, long_window=3)
    watchlist = Watchlist(
        watchlist_id=RUN_ID,
        display_name="W",
        normalized_name="w",
        created_at=STAMP,
        entries=(WatchlistEntry(ticker="AAPL", selection=selection),),
    )

    def executor(ticker: str, chosen: object) -> ExecutionCapture:
        del ticker, chosen
        return ExecutionCapture(native_evidence=object.__new__(MomentumRun), profile=None, outcome=RunOutcome.COMPLETED)

    summary = refresh_watchlist(
        "W", watchlists=_Lookup(watchlist), repository=_Sink(), executor=executor, run_specs={}, classify=failure_code
    )
    assert [result.error for result in summary.results] == [
        "No declared strategy for run spec ('momentum', 'sma_crossover')."
    ]
