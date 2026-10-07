"""Workspace dispatch fails closed: nothing that matches no declared strategy is handled as Momentum."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.core.strategy_errors import UndeclaredStrategyError
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.selection import MomentumSelection
from src.strategy_wiring import EVIDENCE_BY_KEY, EVIDENCE_BY_TYPE, PARSERS_BY_ALIAS, RUN_SPECS_BY_KEY, run_spec_for
from src.workspace.capture import ExecutionCapture
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError, decode_evidence, encode_evidence
from src.workspace.models import RunOutcome
from src.workspace.refresh import refresh_watchlist
from src.workspace.requests import parse_selection
from src.workspace.runs import AnalysisRun, Watchlist, WatchlistEntry
from src.workspace.strategy_types import NativeEvidence
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
        result_schema_version=2,
        evidence_codec_version=1,
        status=RunOutcome.FAILED,
        failure_reason_code="execution_failed",
    )
    return run.model_copy(update={"analysis_id": analysis_id, "method_id": method_id})


def test_an_undeclared_evidence_type_is_rejected_not_encoded_as_momentum() -> None:
    undeclared: NativeEvidence = _UndeclaredEvidence()  # type: ignore[assignment]
    with pytest.raises(UndeclaredStrategyError, match="_UndeclaredEvidence"):
        encode_evidence(undeclared, EVIDENCE_BY_TYPE)


def test_a_subclass_of_a_declared_result_type_is_rejected() -> None:
    subclassed = object.__new__(_SubclassedMomentumRun)
    with pytest.raises(UndeclaredStrategyError, match="_SubclassedMomentumRun"):
        encode_evidence(subclassed, EVIDENCE_BY_TYPE)


def test_encoding_with_no_codec_is_a_programming_error_not_a_stored_run_error() -> None:
    subclassed = object.__new__(_SubclassedMomentumRun)
    with pytest.raises(UndeclaredStrategyError) as error:
        encode_evidence(subclassed, {})
    assert not isinstance(error.value, InvalidStoredRunError)


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


def test_an_unknown_alias_is_rejected_by_the_injected_parsers() -> None:
    with pytest.raises(ValueError, match="Unknown analysis alias: 'momentum'"):
        parse_selection("momentum", "{}", {})
    with pytest.raises(ValueError, match="Unknown analysis alias: 'unknown'"):
        parse_selection("unknown", "{}", PARSERS_BY_ALIAS)


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
