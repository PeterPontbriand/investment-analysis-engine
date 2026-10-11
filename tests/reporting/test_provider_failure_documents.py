"""A stored provider failure reaches the strategy document, the saved run and the replay as the same code.

Each case runs one direct command whose fixture provider fails with a chosen kind, saves the run, and replays it.
The direct document, the replayed document and the saved run's failure code come from that one run.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from src.core.failure_codes import PROVIDER_CODE_BY_KIND
from src.core.provider_failure_kind import ProviderFailureKind
from src.workspace.models import RunOutcome
from tests._strategy_document_output import CASES, Case, run_saved, without_excluded_keys

_BASE_CASES = {
    case.name: case
    for case in CASES
    if case.name in {"graham-number-provider-error", "graham-growth-provider-error", "fcf-growth-provider-error"}
}
_INPUT = {
    "graham-number-provider-error": "eps",
    "graham-growth-provider-error": "eps",
    "fcf-growth-provider-error": "operating_cash_flow",
}


def _case(name: str, kind: ProviderFailureKind) -> Case:
    return replace(_BASE_CASES[name], failure_kind=kind)


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
@pytest.mark.parametrize("name", sorted(_BASE_CASES))
def test_the_document_the_replay_and_the_saved_run_agree_on_the_code(name: str, kind: ProviderFailureKind) -> None:
    direct, replayed, run = run_saved(_case(name, kind))

    code = PROVIDER_CODE_BY_KIND[kind].value
    expected = {
        "reason_code": code,
        "inputs": [{"input": _INPUT[name], "provider_id": "sec_edgar", "kind": kind.value}],
    }
    assert json.loads(direct.stdout)["provider_failure"] == expected
    assert json.loads(replayed.stdout)["provider_failure"] == expected
    assert json.loads(direct.stdout)["provider_check"] == [{"provider_id": "sec_edgar", "verdict": "not_checked"}]
    assert json.loads(replayed.stdout)["provider_check"] is None
    assert without_excluded_keys(direct.stdout) == without_excluded_keys(replayed.stdout)
    assert json.loads(direct.stdout)["status"] == "provider_error"
    assert run.status is RunOutcome.FAILED
    assert run.failure_reason_code == code


def test_the_one_deliberate_unclassified_failure_is_a_provider_error_with_no_element_and_the_generic_code() -> None:
    case = next(item for item in CASES if item.name == "graham-number-provider-error-unclassified")

    direct, replayed, run = run_saved(case)

    assert json.loads(direct.stdout)["status"] == "provider_error"
    assert json.loads(direct.stdout)["provider_failure"] is None
    assert direct.stdout == replayed.stdout
    assert run.failure_reason_code == "provider_error"


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
@pytest.mark.parametrize("name", ["graham-number-quote-provider-failure", "graham-growth-quote-provider-failure"])
def test_a_failed_optional_quote_carries_its_kind_direct_and_replayed(name: str, kind: ProviderFailureKind) -> None:
    case = replace(next(item for item in CASES if item.name == name), quote_failure_kind=kind)

    direct, replayed, run = run_saved(case)

    document = json.loads(direct.stdout)
    assert document["quote"]["status"] == "provider_error"
    assert document["quote"]["provider_failure"] == {
        "input": "current_price",
        "provider_id": "yfinance",
        "kind": kind.value,
    }
    assert document["status"] == "ok"
    assert document["provider_failure"] is None
    assert direct.stdout == replayed.stdout
    assert run.status is RunOutcome.COMPLETED


@pytest.mark.parametrize(
    "name", ["graham-number-success", "graham-growth-success", "fcf-growth-success", "momentum-success"]
)
def test_a_successful_run_has_no_element_and_no_failure_code(name: str) -> None:
    case = next(item for item in CASES if item.name == name)

    direct, replayed, run = run_saved(case)

    assert json.loads(direct.stdout)["provider_failure"] is None
    assert json.loads(replayed.stdout)["provider_failure"] is None
    assert run.failure_reason_code is None
