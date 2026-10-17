"""A Graham Number calculation that does not apply (``--eps -1``) is a not-applicable run, not a failed one.

The assembly resolves every input and the calculation returns ``not_applicable``: the method does not apply to a
company with negative earnings. The run stores that outcome and no failure code, and a refresh job carries no
reason code, with saving on or off. The direct command's output and exit code do not depend on the stored outcome.
"""

from __future__ import annotations

import json

import pytest

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.strategies.graham_number.execution import (
    GrahamNumberCapture,
    classify_graham_number_outcome,
    from_graham_number_capture,
)
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.strategy_wiring import EVIDENCE_BY_KEY, RUN_SPECS_BY_KEY
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.codecs import decode_evidence
from investment_analysis_engine.workspace.refresh import refresh_watchlist
from tests._strategy_document_output import CASES, run_saved
from tests._wiring import failure_text
from tests.workspace.test_refresh import _FakeSink, _FakeWatchlists, _watchlist

_CASE = next(item for item in CASES if item.name == "graham-number-nonpositive-eps")


def test_the_saved_run_is_not_applicable_with_no_failure_code() -> None:
    direct, replayed, run = run_saved(_CASE)

    assert run.status is RunOutcome.NOT_APPLICABLE
    assert run.failure_reason_code is None
    assert json.loads(direct.stdout)["status"] == "not_applicable"
    assert direct.exit_code == 0


def test_the_direct_and_replayed_documents_still_agree() -> None:
    direct, replayed, _run = run_saved(_CASE)

    assert replayed.exit_code == 0
    assert direct.stdout == replayed.stdout


@pytest.mark.parametrize("save", [True, False])
def test_a_refresh_job_for_it_carries_no_reason_code(save: bool) -> None:
    _direct, _replayed, run = run_saved(_CASE)
    analysis = decode_evidence(run, EVIDENCE_BY_KEY)
    assert isinstance(analysis, GrahamNumberAnalysis)
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.result.status is CalculationStatus.NOT_APPLICABLE
    assert run.instrument_profile is not None
    profile = run.instrument_profile

    def executor(_ticker: str, _selection: object) -> ExecutionCapture:
        # The capture is rebuilt through the real mapping, so a regression in it would show here.
        return from_graham_number_capture(
            GrahamNumberCapture(analysis, profile, classify_graham_number_outcome(analysis))
        )

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": _watchlist((run.ticker,), (run.requested_config,))}),
        repository=_FakeSink(),
        executor=executor,
        run_specs=RUN_SPECS_BY_KEY,
        describe=failure_text,
        save=save,
    )

    result = summary.results[0]
    assert result.reason_code is None
    assert result.error is None
    assert (result.run.status if result.run is not None else result.outcome) is RunOutcome.NOT_APPLICABLE
    assert summary.counts == {"not_applicable": 1}
