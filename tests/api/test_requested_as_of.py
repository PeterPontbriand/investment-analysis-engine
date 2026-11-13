"""A run's requested point in time is read from its envelope for every run, so null always means now."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.runs import compare_refresh_runs, get_run_overview
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from tests._runs_compare_refresh import MOMENTUM, alter_row, refresh, run_ids

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

_ASKED = "2025-12-31T00:00:00Z"


def _retire(document: dict[str, Any]) -> None:
    document.update(analysis_id="retired", method_id="retired_method", requested_as_of=_ASKED)


def _age(document: dict[str, Any]) -> None:
    document.update(result_schema_version=99, requested_as_of=_ASKED)


def _compared(context: ApplicationContext, refresh_id: UUID, method_id: str) -> Any:
    document = compare_refresh_runs(context, refresh_id)
    index = next(i for i, item in enumerate(document.strategies) if item.method_id == method_id)
    run = document.rows[0].entries[index].run
    assert run is not None
    return run


@pytest.mark.parametrize(
    ("columns", "change", "method_id", "unavailable"),
    [
        ({"analysis_id": "retired", "method_id": "retired_method"}, _retire, "retired_method", "strategy_not_declared"),
        ({"result_schema_version": 99}, _age, "graham_number", "unsupported_version"),
    ],
    ids=["strategy-not-declared", "unsupported-version"],
)
def test_a_run_that_cannot_give_a_headline_still_reports_what_it_asked_for(
    isolated_cli_settings: ProjectSettings,
    columns: dict[str, object],
    change: Callable[[dict[str, Any]], None],
    method_id: str,
    unavailable: str,
) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM), ("SYNTH", GrahamNumberSelection())])
    context = ApplicationContext(settings=isolated_cli_settings)
    run_id = run_ids(isolated_cli_settings, refresh_id)[("SYNTH", "graham_number")]
    alter_row(isolated_cli_settings, run_id, columns, change)

    compared = _compared(context, refresh_id, method_id)

    assert compared.headline_unavailable == unavailable
    assert compared.requested_as_of is not None
    assert compared.requested_as_of.isoformat().startswith("2025-12-31T00:00:00")
    if unavailable == "strategy_not_declared":
        overview = get_run_overview(context, UUID(run_id))
        assert overview.headline_unavailable == unavailable
        assert overview.requested_as_of == compared.requested_as_of
    else:
        with pytest.raises(UnsupportedRunVersionError):
            get_run_overview(context, UUID(run_id))


def test_a_run_that_asked_for_now_has_a_null_requested_point_in_time_in_both(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM), ("SYNTH", GrahamNumberSelection())])
    context = ApplicationContext(settings=isolated_cli_settings)
    ids = run_ids(isolated_cli_settings, refresh_id)
    retired = ids[("SYNTH", "graham_number")]
    alter_row(
        isolated_cli_settings,
        retired,
        {"analysis_id": "retired", "method_id": "retired_method"},
        lambda document: document.update(analysis_id="retired", method_id="retired_method"),
    )

    assert _compared(context, refresh_id, "sma_crossover").requested_as_of is None
    assert _compared(context, refresh_id, "retired_method").requested_as_of is None
    assert get_run_overview(context, UUID(ids[("SYNTH", "sma_crossover")])).requested_as_of is None
    assert get_run_overview(context, UUID(retired)).requested_as_of is None


def test_a_run_of_a_strategy_no_longer_declared_with_an_unreadable_envelope_is_refused(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM)])
    context = ApplicationContext(settings=isolated_cli_settings)
    run_id = run_ids(isolated_cli_settings, refresh_id)[("SYNTH", "sma_crossover")]
    alter_row(
        isolated_cli_settings,
        run_id,
        {"analysis_id": "retired", "method_id": "retired_method"},
        lambda document: document.update(analysis_id="retired", method_id="retired_method", requested_as_of="soon"),
    )

    with pytest.raises(InvalidStoredRunError):
        get_run_overview(context, UUID(run_id))
