"""The run overview endpoint, and the outcome name every run list uses, in process."""

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.runs import get_run_overview
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.reporting.headline import CellKind, CellUnit
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from tests._cli_helpers import normalize_cli_output
from tests._runs_compare_refresh import alter_row
from tests.api._support import AUTH, client_for, runs_by_alias, store

runner = CliRunner()

_UNKNOWN = "00000000-0000-4000-8000-0000000000ee"


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_the_overview_of_a_saved_run_of_each_strategy_is_its_headline(
    descriptor: StrategyDescriptor, isolated_cli_settings: ProjectSettings
) -> None:
    run = runs_by_alias()[descriptor.alias]
    store(isolated_cli_settings, run)

    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/runs/{run.analysis_run_id}/overview", headers=AUTH)

    assert response.status_code == 200
    document = response.json()
    expected = get_run_overview(ApplicationContext(settings=isolated_cli_settings), run.analysis_run_id)
    assert document == expected.model_dump(mode="json")
    assert list(document) == [
        "schema_version",
        "analysis_run_id",
        "ticker",
        "outcome",
        "completed_at",
        "refresh_id",
        "requested_as_of",
        "strategy",
        "headline",
        "headline_unavailable",
    ]
    assert document["schema_version"] == 1
    assert (document["analysis_run_id"], document["ticker"], document["outcome"]) == (
        str(run.analysis_run_id),
        run.ticker,
        run.status.value,
    )
    assert document["strategy"] == {
        "analysis_id": descriptor.analysis_id,
        "method_id": descriptor.method_id,
        "alias": descriptor.alias,
        "label": descriptor.label,
        "term": descriptor.term,
        "declared": True,
    }
    assert (document["headline"] is None) != (document["headline_unavailable"] is None)
    assert document["headline"] is not None, "A stored run of a declared strategy has a headline."
    cells = document["headline"]["cells"]
    assert cells
    for cell in cells:
        if cell["kind"] == CellKind.TEXT.value:
            assert (cell["unit"], cell["currency"]) == (None, None)
        else:
            assert cell["unit"] in {unit.value for unit in CellUnit}
            assert (cell["currency"] is None) or cell["unit"] == CellUnit.PER_SHARE.value


def test_a_missing_run_is_not_found_as_the_run_document_is(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        overview = client.get(f"/v1/runs/{_UNKNOWN}/overview", headers=AUTH)
        run = client.get(f"/v1/runs/{_UNKNOWN}", headers=AUTH)

    assert overview.status_code == run.status_code == 404
    assert overview.json()["reason_code"] == run.json()["reason_code"] == "analysis_run_not_found"
    assert overview.json()["reason"] == run.json()["reason"]


def test_a_malformed_id_is_an_invalid_parameter(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/runs/not-an-id/overview", headers=AUTH)

    assert response.status_code == 400
    assert response.json()["reason_code"] == "invalid_parameter"


def test_a_run_stored_under_another_version_fails_as_the_run_document_does(
    isolated_cli_settings: ProjectSettings,
) -> None:
    run = runs_by_alias()[STRATEGIES[0].alias]
    store(isolated_cli_settings, run)
    alter_row(
        isolated_cli_settings,
        str(run.analysis_run_id),
        {"result_schema_version": 99},
        lambda document: document.update(result_schema_version=99),
    )

    with client_for(isolated_cli_settings) as client:
        overview = client.get(f"/v1/runs/{run.analysis_run_id}/overview", headers=AUTH)
        shown = client.get(f"/v1/runs/{run.analysis_run_id}", headers=AUTH)

    assert overview.status_code == shown.status_code
    assert overview.status_code >= 400
    assert overview.json()["reason_code"] == shown.json()["reason_code"]
    assert overview.json()["reason"] == shown.json()["reason"]


def test_a_malformed_stored_record_fails_as_the_run_document_does(isolated_cli_settings: ProjectSettings) -> None:
    run = runs_by_alias()[STRATEGIES[0].alias]
    store(isolated_cli_settings, run)
    alter_row(isolated_cli_settings, str(run.analysis_run_id), {}, lambda document: document.clear())

    with client_for(isolated_cli_settings) as client:
        overview = client.get(f"/v1/runs/{run.analysis_run_id}/overview", headers=AUTH)
        shown = client.get(f"/v1/runs/{run.analysis_run_id}", headers=AUTH)

    assert (overview.status_code, overview.json()["reason_code"]) == (shown.status_code, "invalid_stored_run")
    assert overview.json()["reason"] == shown.json()["reason"]


def test_a_run_of_a_strategy_no_longer_declared_shows_its_stored_label(isolated_cli_settings: ProjectSettings) -> None:
    run = runs_by_alias()[STRATEGIES[0].alias]
    store(isolated_cli_settings, run)
    alter_row(
        isolated_cli_settings,
        str(run.analysis_run_id),
        {"analysis_id": "retired", "method_id": "retired_method"},
        lambda document: document.update(analysis_id="retired", method_id="retired_method"),
    )

    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/runs/{run.analysis_run_id}/overview", headers=AUTH)

    assert response.status_code == 200
    document = response.json()
    assert document["strategy"] == {
        "analysis_id": "retired",
        "method_id": "retired_method",
        "alias": None,
        "label": "retired_method",
        "term": None,
        "declared": False,
    }
    assert (document["headline"], document["headline_unavailable"]) == (None, "strategy_not_declared")
    assert (document["ticker"], document["outcome"]) == (run.ticker, run.status.value)


def test_the_runs_list_names_a_runs_outcome_outcome(isolated_cli_settings: ProjectSettings) -> None:
    runs = list(runs_by_alias().values())
    store(isolated_cli_settings, *runs)
    outcome = runs[0].status

    with client_for(isolated_cli_settings) as client:
        everything = client.get("/v1/runs", headers=AUTH).json()
        filtered = client.get("/v1/runs", params={"outcome": outcome.value}, headers=AUTH)
        old_name = client.get("/v1/runs", params={"status": outcome.value}, headers=AUTH)
        bad = client.get("/v1/runs", params={"outcome": "great"}, headers=AUTH)

    assert everything["schema_version"] == 2
    assert all(
        "status" not in item and item["outcome"] in {o.value for o in RunOutcome} for item in everything["items"]
    )
    assert filtered.status_code == 200
    assert {item["outcome"] for item in filtered.json()["items"]} == {outcome.value}
    assert old_name.status_code == 400
    assert old_name.json()["reason_code"] == "invalid_parameter"
    assert old_name.json()["parameters"] == ["status"]
    assert bad.status_code == 400
    assert bad.json()["parameters"] == ["outcome"]
    assert bad.json()["reason"].startswith("outcome must be one of: ")


def test_the_command_lists_and_filters_by_outcome(isolated_cli_settings: ProjectSettings) -> None:
    runs = list(runs_by_alias().values())
    store(isolated_cli_settings, *runs)
    outcome = runs[0].status

    listed = runner.invoke(app, ["runs", "list", "--outcome", outcome.value, "--json"])
    help_text = runner.invoke(app, ["runs", "list", "--help"])
    old_option = runner.invoke(app, ["runs", "list", "--status", outcome.value])

    assert listed.exit_code == 0, listed.output
    assert "outcome" in listed.stdout
    assert '"status"' not in listed.stdout
    help_words = normalize_cli_output(help_text.output)
    assert "--outcome" in help_words
    assert "--status" not in help_words
    assert old_option.exit_code == 2
