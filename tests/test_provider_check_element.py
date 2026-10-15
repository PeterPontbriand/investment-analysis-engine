"""The ``provider_check`` element in the ``--json`` documents that report an analysis outcome.

The element is the finding of the automatic provider check, as typed entries. These tests cover its model and its
consistency rules, the shared function that produces the findings once, each call site that writes it (the failure
envelope, the three result-returning strategy documents and the refresh summary), and the rule that a replay writes
null. The text lines are tested in ``tests/test_cli_provider_check.py``. No test reaches a provider: the probe is built
over fake check bodies and handed to the command through the Typer context.
"""

from __future__ import annotations

import ast
import json
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.cli import app
from src.cli_provider_check import ProviderCheckChoice, ProviderCheckFindings, provider_check_findings
from src.core.failure_codes import FailureReasonCode
from src.core.provider_check_element import (
    ProviderCheckItem,
    ProviderCheckVerdict,
    require_check_matches_failure,
    require_unique_providers,
)
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.base_client import DataFetchError
from src.data.provider_checks import CheckVerdict
from src.data.provider_probe import ProbeFinding, ProbeVerdict
from src.reporting.documents.failure import FailureEnvelope
from src.reporting.failure_envelope import failure_envelope
from src.strategy_wiring import STRATEGIES
from src.workspace_documents.refresh import RefreshSummaryDocument
from tests._cli_helpers import isolated_cli_database, stub_yahoo_identity_metadata  # noqa: F401
from tests._strategy_document_output import CASES, _enter_providers
from tests.test_cli_provider_check import (
    _SCENARIOS,
    _failing,
    _invoke,
    _probe,
    _refresh_failing,
    _seed_momentum,
    runner,
)

_REPOSITORY = Path(__file__).resolve().parent.parent
_CASE_OF_ALIAS = {
    "momentum": "momentum-success",
    "graham-number": "graham-number-provider-error",
    "graham-growth": "graham-growth-provider-error",
    "fcf-growth": "fcf-growth-provider-error",
}


def _element(*records: tuple[ProviderFailureKind, str]) -> Any:
    from src.core.failure_classification import provider_failure_of  # noqa: PLC0415 - one use

    element = provider_failure_of(tuple(ProviderFailureRecord(kind, provider) for kind, provider in records))
    assert element is not None
    return element


def _items(*pairs: tuple[str, ProviderCheckVerdict]) -> tuple[ProviderCheckItem, ...]:
    return tuple(ProviderCheckItem(provider_id=provider, verdict=verdict) for provider, verdict in pairs)


# ---------------------------------------------------------------------------
# The model.
# ---------------------------------------------------------------------------


def test_the_core_verdicts_equal_the_probes_values_in_the_same_order() -> None:
    """The model lives in ``core``, which cannot import the probe, so a test pins the two vocabularies together."""
    assert [item.value for item in ProviderCheckVerdict] == [item.value for item in ProbeVerdict]
    assert len(ProviderCheckVerdict) == 6


def test_every_health_outcome_maps_to_a_verdict_the_model_accepts() -> None:
    for outcome in CheckVerdict:
        assert outcome.value in {item.value for item in ProviderCheckVerdict} | {"ok", "not_configured", "failed"}


def test_an_entry_holds_a_provider_and_one_of_the_six_verdicts_and_nothing_else() -> None:
    item = ProviderCheckItem(provider_id="yfinance", verdict=ProviderCheckVerdict.HEALTHY)
    assert item.model_dump(mode="json") == {"provider_id": "yfinance", "verdict": "healthy"}
    with pytest.raises(ValidationError):
        ProviderCheckItem.model_validate({"provider_id": "yfinance", "verdict": "ok"})
    with pytest.raises(ValidationError):
        ProviderCheckItem.model_validate({"provider_id": "yfinance", "verdict": "healthy", "detail": "x"})


def test_the_consistency_rule_accepts_null_and_the_exact_providers_in_any_order() -> None:
    failure = _element((ProviderFailureKind.UNREACHABLE, "sec_edgar"), (ProviderFailureKind.NO_DATA, "yfinance"))
    require_check_matches_failure(None, None)
    require_check_matches_failure(failure, None)
    require_check_matches_failure(
        failure, _items(("sec_edgar", ProviderCheckVerdict.HEALTHY), ("yfinance", ProviderCheckVerdict.NO_DATA))
    )
    require_check_matches_failure(
        failure, _items(("yfinance", ProviderCheckVerdict.NO_DATA), ("sec_edgar", ProviderCheckVerdict.HEALTHY))
    )


@pytest.mark.parametrize(
    "check",
    [
        _items(("yfinance", ProviderCheckVerdict.HEALTHY)),
        _items(
            ("sec_edgar", ProviderCheckVerdict.HEALTHY),
            ("yfinance", ProviderCheckVerdict.HEALTHY),
            ("other", ProviderCheckVerdict.HEALTHY),
        ),
        _items(("sec_edgar", ProviderCheckVerdict.HEALTHY), ("sec_edgar", ProviderCheckVerdict.NOT_CHECKED)),
        (),
    ],
    ids=["missing-a-provider", "names-an-extra-provider", "duplicate-provider", "empty-list"],
)
def test_the_consistency_rule_rejects_a_check_that_is_not_exactly_the_implicated_providers(
    check: tuple[ProviderCheckItem, ...],
) -> None:
    failure = _element((ProviderFailureKind.UNREACHABLE, "sec_edgar"), (ProviderFailureKind.NO_DATA, "yfinance"))
    with pytest.raises(ValueError, match="provider_check"):
        require_check_matches_failure(failure, check)


def test_the_consistency_rule_rejects_a_check_beside_a_null_provider_failure() -> None:
    with pytest.raises(ValueError, match="only when provider_failure is set"):
        require_check_matches_failure(None, _items(("yfinance", ProviderCheckVerdict.HEALTHY)))


def test_uniqueness_is_by_provider() -> None:
    require_unique_providers(None)
    require_unique_providers(_items(("a", ProviderCheckVerdict.HEALTHY), ("b", ProviderCheckVerdict.HEALTHY)))
    with pytest.raises(ValueError, match="more than once"):
        require_unique_providers(_items(("a", ProviderCheckVerdict.HEALTHY), ("a", ProviderCheckVerdict.NO_DATA)))


# ---------------------------------------------------------------------------
# Each model rejects what the rules forbid.
# ---------------------------------------------------------------------------


def _written_document(alias: str) -> dict[str, Any]:
    """Run the strategy's command against its fixtures with ``--json`` and return the document it writes."""
    case = next(item for item in CASES if item.name == _CASE_OF_ALIAS[alias])
    with ExitStack() as stack:
        _enter_providers(stack, case)
        result = _invoke(list(case.arguments), _probe().probe, "--json", "--no-provider-check")
    document: dict[str, Any] = json.loads(result.stdout)
    return document


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_each_strategy_document_accepts_a_check_that_names_its_providers_and_rejects_every_other(
    descriptor: Any,
) -> None:
    model = descriptor.json_envelope
    document = _written_document(descriptor.alias)
    assert model.model_validate(document)  # the written document validates as written

    if document["provider_failure"] is None:
        # Momentum never records a provider failure (it raises), so no check is ever consistent with its document.
        document["provider_check"] = [{"provider_id": "yfinance", "verdict": "healthy"}]
        with pytest.raises(ValidationError, match="only when provider_failure is set"):
            model.model_validate(document)
        return

    provider = document["provider_failure"]["inputs"][0]["provider_id"]
    document["provider_check"] = [{"provider_id": provider, "verdict": "healthy"}]
    assert model.model_validate(document).provider_check == _items((provider, ProviderCheckVerdict.HEALTHY))

    for wrong in (
        [{"provider_id": "other", "verdict": "healthy"}],
        [{"provider_id": provider, "verdict": "healthy"}, {"provider_id": "other", "verdict": "healthy"}],
        [{"provider_id": provider, "verdict": "healthy"}, {"provider_id": provider, "verdict": "no_data"}],
        [{"provider_id": provider, "verdict": "ok"}],
    ):
        document["provider_check"] = wrong
        with pytest.raises(ValidationError):
            model.model_validate(document)

    document["provider_failure"] = None
    document["provider_check"] = [{"provider_id": provider, "verdict": "healthy"}]
    with pytest.raises(ValidationError, match="only when provider_failure is set"):
        model.model_validate(document)


def test_the_failure_envelope_accepts_a_matching_check_and_rejects_every_other() -> None:
    cause = DataFetchError("detail", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance")
    envelope = failure_envelope(FailureReasonCode.PROVIDER_UNREACHABLE, "message", cause=cause)
    assert envelope.provider_check is None

    checked = envelope.with_provider_check(_items(("yfinance", ProviderCheckVerdict.UNREACHABLE)))
    assert checked.provider_check == _items(("yfinance", ProviderCheckVerdict.UNREACHABLE))
    assert envelope.with_provider_check(None).provider_check is None

    for wrong in (
        _items(("sec_edgar", ProviderCheckVerdict.HEALTHY)),
        _items(("yfinance", ProviderCheckVerdict.HEALTHY), ("sec_edgar", ProviderCheckVerdict.HEALTHY)),
        _items(("yfinance", ProviderCheckVerdict.HEALTHY), ("yfinance", ProviderCheckVerdict.HEALTHY)),
    ):
        with pytest.raises(ValidationError):
            envelope.with_provider_check(wrong)


@pytest.mark.parametrize(
    "code",
    [FailureReasonCode.PROVIDER_ERROR, FailureReasonCode.EXECUTION_ERROR, FailureReasonCode.INVALID_INPUT],
)
def test_a_failure_that_is_not_a_provider_failure_rejects_a_check(code: FailureReasonCode) -> None:
    envelope = failure_envelope(code, "message")
    assert envelope.provider_failure is None
    with pytest.raises(ValidationError, match="only when provider_failure is set"):
        envelope.with_provider_check(_items(("yfinance", ProviderCheckVerdict.HEALTHY)))
    assert envelope.with_provider_check(None) == envelope


def test_the_refresh_summary_rejects_two_entries_for_one_provider_and_accepts_null_or_unique() -> None:
    base: dict[str, Any] = {
        "refresh_id": "00000000-0000-0000-0000-000000000001",
        "watchlist_id": "00000000-0000-0000-0000-000000000002",
        "watchlist_name": "Seeded",
        "results": [],
        "counts": {},
    }
    assert RefreshSummaryDocument.model_validate({**base, "provider_check": None}).provider_check is None
    unique = [{"provider_id": "yfinance", "verdict": "healthy"}, {"provider_id": "sec_edgar", "verdict": "no_data"}]
    assert len(RefreshSummaryDocument.model_validate({**base, "provider_check": unique}).provider_check or ()) == 2
    with pytest.raises(ValidationError, match="more than once"):
        RefreshSummaryDocument.model_validate(
            {**base, "provider_check": [unique[0], {"provider_id": "yfinance", "verdict": "no_data"}]}
        )
    with pytest.raises(ValidationError):
        RefreshSummaryDocument.model_validate(base)  # the key is required, so a document always states it


# ---------------------------------------------------------------------------
# One function produces the findings once; the lines and the element are both built from them.
# ---------------------------------------------------------------------------


def test_the_probe_is_called_once_per_provider_when_both_the_lines_and_the_element_are_built() -> None:
    fake = _probe({"yfinance": CheckVerdict.NO_DATA})
    choice = ProviderCheckChoice(fake.probe, requested=True)

    findings = provider_check_findings([_element((ProviderFailureKind.NO_DATA, "yfinance"))], choice)
    lines = findings.lines()
    element = findings.element()
    assert findings.lines() == lines
    assert findings.element() == element

    assert fake.calls == ["yfinance"]
    assert element == _items(("yfinance", ProviderCheckVerdict.NO_DATA))
    assert lines == ("Yahoo Finance returned no data for a known test ticker. It may be limiting requests.",)


def test_the_element_follows_the_kind_order_and_names_each_provider_once() -> None:
    fake = _probe({"sec_edgar": CheckVerdict.UNREACHABLE, "yfinance": CheckVerdict.RATE_LIMITED})
    failures = [
        _element((ProviderFailureKind.NO_DATA, "yfinance")),
        _element((ProviderFailureKind.UNREACHABLE, "sec_edgar"), (ProviderFailureKind.RATE_LIMITED, "yfinance")),
        None,
    ]

    findings = provider_check_findings(failures, ProviderCheckChoice(fake.probe, requested=True))

    assert findings.element() == _items(
        ("sec_edgar", ProviderCheckVerdict.UNREACHABLE), ("yfinance", ProviderCheckVerdict.RATE_LIMITED)
    )
    assert [line.split(" ")[0] for line in findings.lines()] == ["SEC", "Yahoo"]


def test_no_failure_gives_a_null_element_and_no_lines() -> None:
    fake = _probe()
    findings = provider_check_findings([None], ProviderCheckChoice(fake.probe, requested=True))
    assert findings == ProviderCheckFindings()
    assert findings.element() is None
    assert findings.lines() == ()
    assert fake.calls == []


def test_a_switched_off_check_gives_present_entries_with_not_checked() -> None:
    fake = _probe(enabled=False)
    failure = _element((ProviderFailureKind.UNREACHABLE, "yfinance"))

    from_setting = provider_check_findings([failure], ProviderCheckChoice(fake.probe, requested=True))
    from_option = provider_check_findings([failure], ProviderCheckChoice(_probe().probe, requested=False))

    for findings in (from_setting, from_option):
        assert findings.element() == _items(("yfinance", ProviderCheckVerdict.NOT_CHECKED))
        assert findings.lines() == ("Yahoo Finance was not checked (the provider check is turned off).",)
    assert fake.calls == []


def test_a_probe_that_fails_gives_not_checked_in_the_element_and_the_lines_alike() -> None:
    class _Raising:
        def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
            raise RuntimeError(provider_id, requested)

    findings = provider_check_findings(
        [_element((ProviderFailureKind.UNREACHABLE, "yfinance"))], ProviderCheckChoice(_Raising(), requested=True)
    )

    assert findings.element() == _items(("yfinance", ProviderCheckVerdict.NOT_CHECKED))
    assert findings.lines() == ("Yahoo Finance could not be checked.",)


def _attribute_calls(path: Path, name: str) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == name
    ]


def test_only_the_shared_function_calls_the_probe() -> None:
    """Neither the text path nor the document path may call the probe on its own."""
    source = _REPOSITORY / "src"
    callers = {
        path.relative_to(_REPOSITORY).as_posix()
        for path in source.rglob("*.py")
        if _attribute_calls(path, "check") and path.name != "provider_probe.py"
    }
    assert callers == {"src/cli_provider_check.py"}

    module = ast.parse((source / "cli_provider_check.py").read_text(encoding="utf-8"))
    function_of_call: dict[str, set[str]] = {}
    for function in (node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)):
        for call in ast.walk(function):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                function_of_call.setdefault(call.func.id, set()).add(function.name)
    assert function_of_call["_finding_of"] == {"provider_check_findings"}


def test_a_presenter_does_not_call_the_probe() -> None:
    """A presenter receives the finding as data; it imports neither the probe nor the module that runs it."""
    forbidden = ("src.data.provider_probe", "src.cli_provider_check")
    paths = [
        *(_REPOSITORY / "src" / "strategies").glob("*/presenter.py"),
        *(_REPOSITORY / "src" / "strategies").glob("*/replay.py"),
        *(_REPOSITORY / "src" / "reporting").rglob("*.py"),
    ]
    assert paths
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module not in forbidden, (path, node.module)
            if isinstance(node, ast.Import):
                assert not any(alias.name in forbidden for alias in node.names), path


# ---------------------------------------------------------------------------
# The call sites.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", list(_SCENARIOS))
def test_json_runs_the_check_once_and_writes_the_finding_and_nothing_else(command: str) -> None:
    scenario = _SCENARIOS[command]
    fake = _probe({scenario.provider_id: CheckVerdict.NO_DATA})

    with _failing(command) as arguments:
        result = _invoke(arguments, fake.probe, "--json")

    assert result.exit_code == 1
    assert fake.calls == [scenario.provider_id]
    assert result.stderr == ""
    document = json.loads(result.stdout)
    assert document["provider_check"] == [{"provider_id": scenario.provider_id, "verdict": "no_data"}]


@pytest.mark.parametrize("command", list(_SCENARIOS))
@pytest.mark.parametrize("mode", ["", "--details", "--diagnostics"], ids=["concise", "details", "diagnostics"])
def test_a_text_mode_runs_the_check_once(command: str, mode: str) -> None:
    scenario = _SCENARIOS[command]
    fake = _probe({scenario.provider_id: CheckVerdict.NO_DATA})

    with _failing(command) as arguments:
        result = _invoke(arguments, fake.probe, *([mode] if mode else []))

    assert result.exit_code == 1
    assert fake.calls == [scenario.provider_id]


@pytest.mark.parametrize("command", list(_SCENARIOS))
def test_json_with_the_check_switched_off_writes_the_entries_with_not_checked(command: str) -> None:
    scenario = _SCENARIOS[command]
    by_option = _probe()
    by_setting = _probe(enabled=False)

    with _failing(command) as arguments:
        declined = _invoke(arguments, by_option.probe, "--json", "--no-provider-check")
        disabled = _invoke(arguments, by_setting.probe, "--json")

    for result in (declined, disabled):
        assert result.exit_code == 1
        assert result.stderr == ""
        assert json.loads(result.stdout)["provider_check"] == [
            {"provider_id": scenario.provider_id, "verdict": "not_checked"}
        ]
    assert by_option.calls == by_setting.calls == []


@pytest.mark.parametrize("command", ["momentum", "graham-number"])
def test_json_for_a_failure_that_names_no_provider_has_a_null_element_and_runs_no_probe(command: str) -> None:
    fake = _probe()

    with _failing(command, kind=None) as arguments:
        result = _invoke(arguments, fake.probe, "--json")

    assert result.exit_code == 1
    assert json.loads(result.stdout)["provider_check"] is None
    assert fake.calls == []


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
def test_json_for_a_failed_optional_quote_on_a_successful_analysis_has_a_null_element(command: str) -> None:
    fake = _probe()
    case = next(item for item in CASES if item.name == f"{command}-quote-provider-failure")

    with ExitStack() as stack:
        _enter_providers(stack, case)
        result = _invoke(list(case.arguments), fake.probe, "--json")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["provider_check"] is None
    assert fake.calls == []


@pytest.mark.parametrize("name", ["momentum-success", "graham-number-success", "fcf-growth-success"])
def test_json_for_a_success_has_a_null_element_and_runs_no_probe(name: str) -> None:
    fake = _probe()
    case = next(item for item in CASES if item.name == name)

    with ExitStack() as stack:
        _enter_providers(stack, case)
        result = _invoke(list(case.arguments), fake.probe, "--json")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["provider_check"] is None
    assert fake.calls == []


def test_a_failure_in_json_mode_still_exits_one_and_writes_one_document() -> None:
    fake = _probe({"yfinance": CheckVerdict.UNREACHABLE})

    with _failing("momentum") as arguments:
        result = _invoke(arguments, fake.probe, "--json")

    assert result.exit_code == 1
    envelope = FailureEnvelope.model_validate_json(result.stdout)
    assert envelope.provider_check == _items(("yfinance", ProviderCheckVerdict.UNREACHABLE))
    assert envelope.reason_code is FailureReasonCode.PROVIDER_UNREACHABLE


# ---------------------------------------------------------------------------
# The refresh summary.
# ---------------------------------------------------------------------------


def test_the_refresh_summary_carries_one_entry_per_implicated_provider_in_the_kind_order() -> None:
    fake = _probe({"sec_edgar": CheckVerdict.UNREACHABLE, "yfinance": CheckVerdict.RATE_LIMITED})
    _seed_momentum("Two Providers", ["AAPL", "MSFT", "KO"])

    calls: list[int] = []

    def failing(**_kwargs: object) -> None:
        # AAPL and KO fail on Yahoo (no data); MSFT fails on SEC EDGAR (unreachable): SEC EDGAR is the more severe.
        calls.append(1)
        if len(calls) == 2:
            raise DataFetchError("detail", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
        raise DataFetchError("detail", kind=ProviderFailureKind.NO_DATA, provider_id="yfinance")

    with patch("src.strategies.momentum.execution.MomentumAnalyzer.run_analysis", side_effect=failing):
        result = runner.invoke(app, ["refresh", "Two Providers", "--workers", "1", "--json"], obj=fake.probe)

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["provider_check"] == [
        {"provider_id": "sec_edgar", "verdict": "unreachable"},
        {"provider_id": "yfinance", "verdict": "rate_limited"},
    ]
    assert list(document)[-1] == "provider_check"
    assert sorted(fake.calls) == ["sec_edgar", "yfinance"]


def test_the_refresh_summary_is_null_when_no_job_failed_on_a_provider() -> None:
    fake = _probe()

    result = _refresh_failing(fake.probe, "--json", kind=None)

    assert result.exit_code == 1
    assert json.loads(result.stdout)["provider_check"] is None
    assert fake.calls == []


def test_the_refresh_summary_with_the_check_switched_off_has_the_entry_with_not_checked() -> None:
    fake = _probe()

    result = _refresh_failing(fake.probe, "--json", "--no-provider-check")

    assert json.loads(result.stdout)["provider_check"] == [{"provider_id": "yfinance", "verdict": "not_checked"}]
    assert result.stderr == ""
    assert fake.calls == []


def test_the_refresh_text_and_the_summary_come_from_the_same_findings() -> None:
    text_probe = _probe({"yfinance": CheckVerdict.NO_DATA})
    json_probe = _probe({"yfinance": CheckVerdict.NO_DATA})

    text = _refresh_failing(text_probe.probe)
    document = _refresh_failing(json_probe.probe, "--json")

    assert text.stdout.splitlines()[0].startswith("Yahoo Finance returned no data")
    assert json.loads(document.stdout)["provider_check"] == [{"provider_id": "yfinance", "verdict": "no_data"}]
    assert text_probe.calls == json_probe.calls == ["yfinance"]
