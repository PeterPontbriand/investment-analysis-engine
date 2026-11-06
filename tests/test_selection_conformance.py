"""Each strategy's selection options, descriptions and settings-filled fields agree with its model (T27)."""

from collections.abc import Callable
from dataclasses import replace
from typing import Annotated

import pytest
import typer
from pydantic import BaseModel, Field

from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, CliStrategy
from investment_analysis_engine.cli_support import SelectionOption
from investment_analysis_engine.strategy_wiring import FCF_GROWTH, MOMENTUM, STRATEGIES, StrategyDescriptor
from scripts import strategy_conformance as conformance
from tests.specimen.cli_tier import SPECIMEN_CLI_STRATEGIES
from tests.specimen.wiring import SPECIMEN_STRATEGIES


def _entry_of(descriptor: StrategyDescriptor) -> CliStrategy:
    return next(entry for entry in CLI_STRATEGIES if entry.behavior is descriptor.behavior)


def test_every_declared_strategy_has_consistent_selection_options() -> None:
    assert conformance.selection_options_gaps(STRATEGIES) == []


def test_the_specimen_has_consistent_selection_options() -> None:
    assert conformance.selection_options_gaps(SPECIMEN_STRATEGIES, SPECIMEN_CLI_STRATEGIES) == []


def test_an_add_selection_option_the_direct_command_lacks_is_reported() -> None:
    def add_selection(
        name: str,
        tickers: list[str],
        *,
        extra: Annotated[int, typer.Option("--extra")] = 1,
        json_output: bool = False,
    ) -> None:
        del name, tickers, extra, json_output

    entry = replace(_entry_of(MOMENTUM), add_selection=add_selection)
    gaps = conformance.selection_options_gaps((MOMENTUM,), (entry,))

    assert any("add-selection options ['extra'] differ" in gap for gap in gaps)


def test_an_option_declared_differently_in_the_two_commands_is_reported() -> None:
    original = _entry_of(MOMENTUM)

    def add_selection(  # noqa: PLR0913
        name: str,
        tickers: list[str],
        *,
        short_window: Annotated[int | None, typer.Option("--short-window", "-s", help="Other")] = None,
        long_window: Annotated[int | None, typer.Option("--long-window")] = None,
        rsi_period: Annotated[int | None, typer.Option("--rsi-period")] = None,
        as_of: Annotated[str | None, typer.Option("--as-of")] = None,
        no_cache: Annotated[bool, typer.Option("--no-cache")] = False,
        json_output: bool = False,
    ) -> None:
        del name, tickers, short_window, long_window, rsi_period, as_of, no_cache, json_output

    gaps = conformance.selection_options_gaps((MOMENTUM,), (replace(original, add_selection=add_selection),))

    assert any("short_window is declared differently" in gap for gap in gaps)


def test_a_selection_field_the_option_table_does_not_cover_is_reported() -> None:
    entry = replace(_entry_of(MOMENTUM), selection_options=_entry_of(MOMENTUM).selection_options[:-1])

    gaps = conformance.selection_options_gaps((MOMENTUM,), (entry,))

    assert gaps == [
        f"strategy {conformance.label(MOMENTUM)}: the option table does not cover the selection field use_cache"
    ]


def test_a_row_for_a_field_that_does_not_exist_or_a_parameter_the_command_lacks_is_reported() -> None:
    rows = (
        *_entry_of(MOMENTUM).selection_options,
        SelectionOption("ghost", "ghost_field", "--ghost"),
    )
    gaps = conformance.selection_options_gaps((MOMENTUM,), (replace(_entry_of(MOMENTUM), selection_options=rows),))

    assert any("names ghost_field, which is not a selection field" in gap for gap in gaps)
    assert any("names the parameter ghost, which the command lacks" in gap for gap in gaps)


class _NoDescription(BaseModel):
    value: int = Field(default=1)


def test_a_field_without_a_description_is_reported() -> None:
    infos = conformance._selection_field_infos(_NoDescription)  # noqa: SLF001 - the helper under test
    assert not (infos["value"].description or "").strip()


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_every_form_field_has_a_description(descriptor: StrategyDescriptor) -> None:
    infos = conformance._selection_field_infos(descriptor.behavior.selection_type)  # noqa: SLF001
    assert [name for name, info in infos.items() if not (info.description or "").strip()] == []


def test_a_settings_filled_field_must_be_required_and_a_settings_field() -> None:
    not_required = replace(MOMENTUM, selection_settings_fields=("use_cache",))
    unknown = replace(MOMENTUM, selection_settings_fields=("short_window", "not_a_field"))

    assert any(
        "use_cache in selection_settings_fields is not a required selection field" in gap
        for gap in conformance.selection_options_gaps((not_required,), (_entry_of(MOMENTUM),))
    )
    assert any(
        "use_cache in selection_settings_fields is not a field of the settings model" in gap
        for gap in conformance.selection_options_gaps((not_required,), (_entry_of(MOMENTUM),))
    )
    assert any(
        "not_a_field in selection_settings_fields is not a required selection field" in gap
        for gap in conformance.selection_options_gaps((unknown,), (_entry_of(MOMENTUM),))
    )


def test_a_literal_default_that_converts_to_another_value_than_the_model_default_is_reported() -> None:
    entry = _entry_of(FCF_GROWTH)

    def command(  # noqa: PLR0913
        ticker: str,
        *,
        growth_years: int | None = None,
        forward_policy: str = "hard-gate",
        classification_basis: str = "total-fcf",
        as_of: str | None = None,
        currency: str = "USD",
        no_cache: bool = False,
        details: bool = False,
        diagnostics: bool = False,
        json_output: bool = False,
        save_run: bool = False,
        no_provider_check: bool = False,
    ) -> None:
        del ticker, growth_years, forward_policy, classification_basis, as_of, currency, no_cache
        del details, diagnostics, json_output, save_run, no_provider_check

    mismatched: CliStrategy = replace(entry, command=command)
    gaps = conformance.selection_options_gaps((FCF_GROWTH,), (mismatched,))

    assert (
        f"strategy {conformance.label(FCF_GROWTH)}: the default of --forward-policy "
        "does not convert to the default of policy.forward_policy"
    ) in gaps


def test_the_production_defaults_that_duplicate_a_model_default_are_checked() -> None:
    check: Callable[..., list[str]] = conformance.selection_options_gaps
    assert check(STRATEGIES) == []
