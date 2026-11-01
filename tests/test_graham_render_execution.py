"""The Graham commands render through the shared rule: the provider check runs once, on the run's exit code.

Each row is one reachable combination of the input assembly's status, the analysis' execution status and the run
outcome, as the plan's record of the Graham render lists them. The probe counts the checks it is asked for, so a row
states whether the provider check ran. Nothing reaches a provider.
"""

import importlib
import json
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.provider_probe import ProbeFinding, ProbeVerdict
from investment_analysis_engine.strategies.graham_growth.calculation import GrowthValueInputAssembly
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputAssembly
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests._strategy_document_output import CASES, Case, _arguments, _enter_providers, _with_ticker

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

runner = CliRunner()

_CHECK_LINE = "SEC EDGAR is not answering: a test request also failed."


class _CountingProbe:
    """A probe that finds every provider unreachable and records which providers it was asked about."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        del requested
        self.asked.append(provider_id)
        return ProbeFinding(provider_id, ProbeVerdict.UNREACHABLE)


def _stored(name: str) -> Case:
    return next(case for case in CASES if case.name == name)


_NUMBER_OVERFLOW = Case(
    "graham-number-overflow", "graham-number", _arguments("graham-number", "--eps", "1e200", "--bvps", "1e200"), 1
)
_NUMBER_BAD_QUOTE = Case(
    "graham-number-bad-quote", "graham-number", _arguments("graham-number", "--current-price", "-1"), 1
)
_GROWTH_BAD_QUOTE = Case(
    "graham-growth-bad-quote", "graham-growth", _arguments("graham-growth", "--current-price", "-1"), 1
)
_GROWTH_UNCLASSIFIED = Case(
    "graham-growth-provider-error-unclassified",
    "graham-growth",
    _with_ticker("graham-growth", "ERROR"),
    1,
    unclassified=True,
)
_GROWTH_NONPOSITIVE_PE = Case(
    "graham-growth-nonpositive-pe", "graham-growth", _arguments("graham-growth", "--expected-growth", "-100"), 1
)

# (case, assembly status, analysis execution status, run outcome, provider check runs)
_COMBINATIONS = (
    pytest.param(_stored("graham-number-success"), "ok", "ok", "completed", False, id="number-ok-ok"),
    pytest.param(
        _stored("graham-number-nonpositive-eps"), "ok", "not_applicable", "not_applicable", False, id="number-ok-na"
    ),
    pytest.param(_NUMBER_OVERFLOW, "ok", "invalid_input", "failed", False, id="number-ok-invalid"),
    pytest.param(
        _stored("graham-number-etf"), "not_applicable", "not_applicable", "not_applicable", False, id="number-na"
    ),
    pytest.param(_NUMBER_BAD_QUOTE, "invalid_input", "invalid_input", "failed", False, id="number-invalid"),
    pytest.param(
        _stored("graham-number-missing-input"),
        "input_unavailable",
        "input_unavailable",
        "unavailable",
        False,
        id="number-unavailable",
    ),
    pytest.param(
        _stored("graham-number-provider-error"),
        "provider_error",
        "provider_error",
        "failed",
        True,
        id="number-provider-error",
    ),
    pytest.param(
        _stored("graham-number-provider-error-unclassified"),
        "provider_error",
        "provider_error",
        "failed",
        False,
        id="number-provider-error-unclassified",
    ),
    pytest.param(_stored("graham-growth-success"), "ok", "ok", "completed", False, id="growth-ok-ok"),
    pytest.param(_GROWTH_NONPOSITIVE_PE, "ok", "invalid_input", "failed", False, id="growth-ok-invalid"),
    pytest.param(
        _stored("graham-growth-etf"), "not_applicable", "not_applicable", "not_applicable", False, id="growth-na"
    ),
    pytest.param(_GROWTH_BAD_QUOTE, "invalid_input", "invalid_input", "failed", False, id="growth-invalid"),
    pytest.param(
        _stored("graham-growth-missing-input"),
        "input_unavailable",
        "input_unavailable",
        "unavailable",
        False,
        id="growth-unavailable",
    ),
    pytest.param(
        _GROWTH_UNCLASSIFIED,
        "provider_error",
        "provider_error",
        "failed",
        False,
        id="growth-provider-error-unclassified",
    ),
    pytest.param(
        _stored("graham-growth-provider-error"),
        "provider_error",
        "provider_error",
        "failed",
        True,
        id="growth-provider-error",
    ),
)


@pytest.mark.parametrize(("case", "assembly", "execution", "outcome", "checked"), _COMBINATIONS)
def test_each_reachable_combination_renders_by_the_shared_rule(
    case: Case, assembly: str, execution: str, outcome: str, checked: bool
) -> None:
    probe = _CountingProbe()
    expected_exit = 1 if outcome in ("failed", "unavailable") else 0
    seen: list[tuple[str, str, str]] = []
    module = case.command.replace("-", "_")
    name = f"from_{module}_capture"
    real = getattr(importlib.import_module(f"investment_analysis_engine.strategies.{module}.cli"), name)

    def recording(capture: Any) -> ExecutionCapture:
        normalized: ExecutionCapture = real(capture)
        seen.append((capture.analysis.assembly.status.value, normalized.native_status.value, normalized.outcome.value))
        return normalized

    with ExitStack() as stack:
        _enter_providers(stack, case)
        stack.enter_context(patch(f"investment_analysis_engine.strategies.{module}.cli.{name}", recording))
        result = runner.invoke(app, [*case.arguments, "--json"], obj=probe)

    assert result.exit_code == expected_exit, result.output
    assert seen == [(assembly, execution, outcome)]
    assert probe.asked == (["sec_edgar"] if checked else [])
    assert (json.loads(result.stdout)["provider_check"] is not None) is checked


@pytest.mark.parametrize(
    ("case"),
    [_stored("graham-number-provider-error"), _stored("graham-growth-provider-error")],
    ids=["number", "growth"],
)
def test_a_failure_in_the_text_mode_is_preceded_by_the_provider_check_line(case: Case) -> None:
    probe = _CountingProbe()

    with ExitStack() as stack:
        _enter_providers(stack, case)
        result = runner.invoke(app, list(case.arguments), obj=probe)

    assert result.exit_code == 1
    assert result.stderr.splitlines()[0] == _CHECK_LINE
    assert probe.asked == ["sec_edgar"]


@pytest.mark.parametrize(
    "case",
    [_stored("graham-number-quote-provider-failure"), _stored("graham-growth-quote-provider-failure")],
    ids=["number", "growth"],
)
def test_a_failed_optional_quote_does_not_run_the_provider_check(case: Case) -> None:
    probe = _CountingProbe()

    with ExitStack() as stack:
        _enter_providers(stack, case)
        result = runner.invoke(app, list(case.arguments), obj=probe)

    assert result.exit_code == 0
    assert probe.asked == []


def test_an_assembly_records_a_provider_failure_only_with_the_provider_error_status() -> None:
    """A provider failure cannot sit on any other assembly status, so no other status can implicate a provider."""
    record = ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "sec_edgar")
    for assembly_type in (GrahamNumberInputAssembly, GrowthValueInputAssembly):
        assert (
            assembly_type(status=CalculationStatus.PROVIDER_ERROR, provider_failure=record).provider_failure == record
        )
        for status in (
            CalculationStatus.OK,
            CalculationStatus.NOT_APPLICABLE,
            CalculationStatus.INVALID_INPUT,
            CalculationStatus.INPUT_UNAVAILABLE,
        ):
            with pytest.raises(ValueError, match="requires a provider_error assembly"):
                assembly_type(status=status, provider_failure=record)
