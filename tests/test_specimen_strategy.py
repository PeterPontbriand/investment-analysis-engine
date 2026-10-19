"""The specimen strategy: a complete trivial strategy wired through every layer that is open to injection.

The specimen lives in ``tests/specimen`` and the production tuples, tiers, enumeration and unions never name it.
These tests build the closed tuples with it themselves, run the production conformance checks over them (T7, T8,
T11, T22 and the site checks of T27), and use it as the incomplete strategy of the T12 negative control. The layers
closed to it (``ToolName`` registration, the ``AnalysisSelection`` union and the ``StrategyBehavior`` bounds) are
covered by the generator's end-to-end test, which adds a strategy to a temporary copy of the repository.

The case ids the catalog check reads from this file: "SPC-01".
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Generator, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import pytest
import typer
from typer.testing import CliRunner

from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, CliStrategy, add_strategy_commands
from investment_analysis_engine.config.strategy_settings import clear_strategy_settings_cache
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.settings_error import StrategySettingsError
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.evaluation.strategy_fixtures import EVALUATION_STRATEGIES, EvaluationStrategy
from investment_analysis_engine.orchestrator.tool_names import ToolName
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import ReplayOptions
from investment_analysis_engine.strategy_wiring import (
    GRAHAM_GROWTH,
    GRAHAM_NUMBER,
    MOMENTUM,
    STRATEGIES,
    StrategyBehavior,
    evidence_by_key,
    replays_by_key,
)
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from scripts import strategy_conformance as conformance
from scripts import strategy_status
from scripts.generate_schemas import SCHEMA_DIRECTORY
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import load_sites, strategy_names
from tests._wiring_gaps import Surface, assert_wired, find_wiring_gaps, wiring_surfaces
from tests.specimen import cli as specimen_cli
from tests.specimen.analyzer import SpecimenAnalyzer, SpecimenConfig, SpecimenResult
from tests.specimen.catalog import CATALOG_CASE_IDS
from tests.specimen.cli_tier import SPECIMEN_CLI, SPECIMEN_CLI_STRATEGIES
from tests.specimen.evaluation import SAMPLE_SELECTION
from tests.specimen.evaluation_tier import SPECIMEN_EVALUATION, SPECIMEN_EVALUATION_STRATEGIES
from tests.specimen.runs import SPECIMEN_RUN_STORE, SpecimenRun, decode_specimen_run, project_specimen_run
from tests.specimen.selection import SpecimenSelection
from tests.specimen.settings import SpecimenSettings
from tests.specimen.site_context import (
    COVERED_BY_GENERATOR,
    COVERED_SITES,
    SPECIMEN_CONTEXT,
    SPECIMEN_FOLDER,
    SPECIMEN_NAMES,
    specimen_app,
    specimen_stored_run,
)
from tests.specimen.tool import SpecimenTool
from tests.specimen.wiring import SPECIMEN, SPECIMEN_STRATEGIES

_KEY = "('specimen', 'specimen_method')"
_COVERED_SITES = set(COVERED_SITES)
_PINNED_CASE_IDS = ("SPC-01",)
_CLOCK = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
_SITES = load_sites()


def _production_surfaces() -> dict[str, Surface]:
    return wiring_surfaces()


def _specimen_surfaces(
    cli_tier: tuple[CliStrategy, ...] = SPECIMEN_CLI_STRATEGIES,
    evaluation_tier: tuple[EvaluationStrategy, ...] = SPECIMEN_EVALUATION_STRATEGIES,
) -> dict[str, Surface]:
    """The surfaces over the specimen tiers, with the specimen's own document in its own schema folder."""
    return wiring_surfaces(
        cli_tier, evaluation_tier, lambda item: SPECIMEN_FOLDER if item is SPECIMEN else SCHEMA_DIRECTORY
    )


# ---------------------------------------------------------------------------
# The specimen stays out of production
# ---------------------------------------------------------------------------


def test_the_production_declarations_never_name_the_specimen() -> None:
    """The closed tuples, tiers, enumeration, unions and published schemas are the four production strategies."""
    assert SPECIMEN not in STRATEGIES
    assert all(entry is not SPECIMEN_CLI for entry in CLI_STRATEGIES)
    assert all(entry is not SPECIMEN_EVALUATION for entry in EVALUATION_STRATEGIES)
    assert SpecimenTool.ANALYZE_SPECIMEN.value not in {tool.value for tool in ToolName}
    assert SpecimenSelection not in get_args(SelectionMember)
    assert not list(SCHEMA_DIRECTORY.glob("specimen*"))
    for path in PACKAGE_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "tests.specimen" not in text, path
        assert SpecimenTool.ANALYZE_SPECIMEN.value not in text, path


def test_only_the_closed_types_module_of_the_specimen_calls_cast() -> None:
    """The specimen crosses the closed production types in one module, so a crossing cannot appear unnoticed."""
    for path in sorted(SPECIMEN_FOLDER.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name == "closed_types.py":
            assert text.count("cast(") == 5
        else:
            assert "cast(" not in text, path.name
            assert "import cast" not in text, path.name
            assert "type: ignore" not in text, path.name


def test_the_specimen_tuples_append_the_specimen_after_the_production_entries() -> None:
    """The tests build the closed tuples themselves: production first, the specimen last."""
    assert (*STRATEGIES, SPECIMEN) == SPECIMEN_STRATEGIES
    assert (*CLI_STRATEGIES, SPECIMEN_CLI) == SPECIMEN_CLI_STRATEGIES
    assert (*EVALUATION_STRATEGIES, SPECIMEN_EVALUATION) == SPECIMEN_EVALUATION_STRATEGIES


# ---------------------------------------------------------------------------
# T27: the status command on the specimen
# ---------------------------------------------------------------------------


def test_t27_every_site_is_done_for_the_specimen_except_those_covered_by_the_generator_test() -> None:
    """The status report has a line for each site in the site data file, and only the covered ones are not run."""
    lines, complete = strategy_status.report(SPECIMEN_NAMES, SPECIMEN_CONTEXT)
    assert complete
    headlines = [line for line in lines if not line.startswith(" ")]
    assert len(headlines) == len(_SITES)
    assert {line.split()[1] for line in headlines if line.startswith("covered")} == _COVERED_SITES
    assert all(line.startswith(("done     ", "covered  ")) for line in headlines)
    assert not any(line.startswith("missing") for line in lines)


def test_t27_the_covered_sites_are_reported_by_name_with_where_they_are_checked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The status command prints each covered site and does not skip any silently."""
    assert strategy_status.main(["--specimen"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "covered  tool-name  investment_analysis_engine/orchestrator/tool_names.py" in lines
    assert "covered  unions  investment_analysis_engine/workspace/strategy_types.py" in lines
    for site in _SITES:
        if site.id in _COVERED_SITES:
            assert f"covered  {site.id}  {site.resolved_path(SPECIMEN_NAMES)}" in lines
    assert lines.count(f"    {COVERED_BY_GENERATOR}") == len(_COVERED_SITES)
    assert "done     settings  tests/specimen/settings.toml" in lines


def test_t27_the_specimen_options_exclude_a_module_name_and_an_alias() -> None:
    """``--specimen`` names its own strategy."""
    with pytest.raises(SystemExit) as raised:
        strategy_status.main(["--specimen", "momentum"])
    assert raised.value.code == 2


@pytest.mark.parametrize("site", [site for site in _SITES if site.id not in _COVERED_SITES], ids=lambda site: site.id)
def test_t27_each_check_run_on_the_specimen_returns_no_gap(site: Any) -> None:
    """Every checked site is done: the same check functions the production strategies pass."""
    assert getattr(conformance, site.check)(SPECIMEN_NAMES, SPECIMEN_CONTEXT) == []


@pytest.mark.parametrize("site", [site for site in _SITES if site.id in _COVERED_SITES], ids=lambda site: site.id)
def test_t27_the_covered_sites_really_are_not_done_for_the_specimen(site: Any) -> None:
    """Their checks, run on the specimen, do report it: the covered note is not hiding a passing check."""
    assert getattr(conformance, site.check)(SPECIMEN_NAMES, SPECIMEN_CONTEXT) != []


@pytest.mark.parametrize("site", [site for site in _SITES if site.id not in _COVERED_SITES], ids=lambda site: site.id)
def test_t27_an_incomplete_specimen_is_reported_at_each_site(site: Any, tmp_path: Path) -> None:
    """Pointing each site at a file that does not exist, or removing the strategy from its tuples, is reported."""
    nothing = replace(SPECIMEN_CONTEXT, descriptors=STRATEGIES, cli_tier=CLI_STRATEGIES, evaluation_tier=())
    paths = {site_id: f"{tmp_path.name}/missing/{site_id}" for site_id in SPECIMEN_CONTEXT.paths}
    gone = replace(nothing, paths=paths, root=tmp_path.parent, evaluation_tier=EVALUATION_STRATEGIES)
    gaps = getattr(conformance, site.check)(SPECIMEN_NAMES, gone)
    if site.id == "settings":
        assert gaps == []
        return
    assert gaps
    assert {gap.site_id for gap in gaps} == {site.id}


# ---------------------------------------------------------------------------
# The settings site
# ---------------------------------------------------------------------------


def test_the_settings_site_is_done_for_a_package_with_no_settings_file() -> None:
    """A strategy with no ``settings.py`` has no settings and nothing to add."""
    assert not (PACKAGE_ROOT / "strategies" / "graham_number" / "settings.py").exists()
    names = strategy_names("graham_number", "graham-number")
    assert conformance.site_settings(names) == []


def test_the_settings_site_reports_a_missing_shipped_file_and_a_descriptor_that_names_another_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A package with a ``settings.py`` needs the ``settings.toml`` beside it and the descriptor's model."""
    package = tmp_path / "investment_analysis_engine" / "strategies" / "zed"
    package.mkdir(parents=True)
    (package / "settings.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(conformance, "REPOSITORY_ROOT", tmp_path)
    messages = [gap.message for gap in conformance.site_settings(strategy_names("zed"))]
    assert messages[0].endswith(
        "defines a settings model but investment_analysis_engine/strategies/zed/settings.toml does not exist"
    )
    assert "has no descriptor" in messages[1]
    assert len(messages) == 2


def test_the_settings_site_reports_a_descriptor_without_the_model_and_one_with_another_package_s_model() -> None:
    """The descriptor's ``settings_type`` must be the model the strategy's own ``settings.py`` defines."""
    names = strategy_names("graham_growth", "graham-growth")
    other = tuple(item for item in STRATEGIES if item is not GRAHAM_GROWTH)
    without = dataclasses.replace(
        conformance.PRODUCTION, descriptors=(replace(GRAHAM_GROWTH, settings_type=None), *other)
    )
    assert [gap.message for gap in conformance.site_settings(names, without)] == [
        "investment_analysis_engine/strategies/graham_growth/settings.py exists "
        "but the descriptor's settings_type is None"
    ]
    borrowed = dataclasses.replace(
        conformance.PRODUCTION, descriptors=(replace(GRAHAM_GROWTH, settings_type=MOMENTUM.settings_type), *other)
    )
    (gap,) = conformance.site_settings(names, borrowed)
    assert (
        "MomentumSettings is not defined in investment_analysis_engine/strategies/graham_growth/settings.py"
        in gap.message
    )
    assert conformance.site_settings(names) == []


# ---------------------------------------------------------------------------
# The settings path at the composition root
# ---------------------------------------------------------------------------


@pytest.fixture
def specimen_config_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """A user settings folder the specimen command reads, with the settings cache and run store emptied around it."""
    clear_strategy_settings_cache()
    SPECIMEN_RUN_STORE.clear()
    monkeypatch.setattr(specimen_cli, "settings", SimpleNamespace(config_dir=tmp_path))
    yield tmp_path
    clear_strategy_settings_cache()
    SPECIMEN_RUN_STORE.clear()


def _invoke(*arguments: str) -> tuple[int, str]:
    result = CliRunner().invoke(specimen_app(), ["specimen-test", *arguments])
    return result.exit_code, result.output


def test_the_calculation_uses_the_shipped_multiplier_through_the_composition_root(specimen_config_folder: Path) -> None:
    """The multiplier the command scales by is the shipped ``settings.toml``'s key, not a constant in the code."""
    del specimen_config_folder
    assert SpecimenSettings.model_fields.keys() == {"multiplier"}
    assert specimen_cli.specimen_settings().multiplier == 2.0
    assert _invoke("SPEC", "--value", "3") == (0, "SPEC specimen value: 6.0\n")


def test_a_user_settings_file_overrides_the_key_and_changes_the_result(specimen_config_folder: Path) -> None:
    """The key is not a one-value setting: the user's per-key override reaches the calculation."""
    folder = specimen_config_folder / "strategies"
    folder.mkdir()
    (folder / "specimen-test.toml").write_text("multiplier = 5.0\n", encoding="utf-8")
    assert _invoke("SPEC", "--value", "3") == (0, "SPEC specimen value: 15.0\n")


def test_an_invalid_user_setting_is_rejected_naming_the_file_and_the_key(specimen_config_folder: Path) -> None:
    """The generic loader validates the specimen's model like any strategy's."""
    folder = specimen_config_folder / "strategies"
    folder.mkdir()
    (folder / "specimen-test.toml").write_text("multiplier = -1.0\n", encoding="utf-8")
    with pytest.raises(StrategySettingsError, match=r"specimen-test\.toml is invalid: multiplier"):
        specimen_cli.specimen_settings()


# ---------------------------------------------------------------------------
# T7: the specimen's command in its own Typer app
# ---------------------------------------------------------------------------


def test_t7_the_specimen_app_holds_one_command_per_alias_and_each_offers_both_flags() -> None:
    """The production command check, over an app built from the specimen tuples with ``add_strategy_commands``."""
    application = specimen_app()
    assert conformance.command_table_gaps(SPECIMEN_STRATEGIES, application) == []
    standalone = typer.Typer()
    add_strategy_commands(standalone, SPECIMEN_STRATEGIES, SPECIMEN_CLI_STRATEGIES)
    assert [info.name for info in standalone.registered_commands] == [item.alias for item in SPECIMEN_STRATEGIES]
    assert standalone.registered_commands[-1].callback is SPECIMEN_CLI.command


def test_t7_a_specimen_app_missing_the_specimen_command_is_reported_by_the_cli_tier_site() -> None:
    """Without the specimen's tier entry the app has no command for it, and the site names the alias."""
    application = typer.Typer()

    @application.callback()
    def root() -> None:
        """Hold the commands."""

    add_strategy_commands(application, STRATEGIES, CLI_STRATEGIES)
    context = replace(SPECIMEN_CONTEXT, app=application, cli_tier=CLI_STRATEGIES)
    messages = [gap.message for gap in conformance.site_cli_tier(SPECIMEN_NAMES, context)]
    assert f"strategy {_KEY} is not wired in: CLI tier" in messages
    assert "alias 'specimen-test' is not a top-level command" in messages


def test_the_production_app_has_no_specimen_command() -> None:
    """The user's command line is built from the production CLI tier only."""
    from investment_analysis_engine.cli import app  # noqa: PLC0415 - compared only here

    assert "specimen-test" not in {info.name for info in app.registered_commands}


# ---------------------------------------------------------------------------
# T8: the specimen's result stored and replayed
# ---------------------------------------------------------------------------


def test_t8_the_specimen_result_is_stored_under_the_sample_selection_its_tier_entry_declares() -> None:
    """The run carries the descriptor's versions, decodes to the result stored and replays in every mode."""
    stored = specimen_stored_run()
    assert stored.selection is SPECIMEN_EVALUATION.sample_selection
    assert isinstance(stored.run, SpecimenRun)
    assert stored.run.requested_config is SAMPLE_SELECTION
    local = (stored,)
    assert conformance.versions_and_round_trip_gaps(SPECIMEN_STRATEGIES, SPECIMEN_EVALUATION_STRATEGIES, local) == []
    assert conformance.replay_gaps(SPECIMEN_STRATEGIES, SPECIMEN_EVALUATION_STRATEGIES, local) == []
    assert [
        entry.descriptor
        for entry in conformance.stored_runs(SPECIMEN_STRATEGIES, SPECIMEN_EVALUATION_STRATEGIES, local)
    ] == list(SPECIMEN_STRATEGIES)


def test_t8_the_specimen_has_no_stored_run_unless_one_is_supplied() -> None:
    """Without a local run the specimen has no golden case to store, and the check names it."""
    gaps = conformance.versions_and_round_trip_gaps(SPECIMEN_STRATEGIES, SPECIMEN_EVALUATION_STRATEGIES)
    assert gaps == [f"strategy {_KEY} has no golden fixture result or evaluation-tier sample selection to store"]


def test_t8_the_specimen_run_replays_the_concise_text_and_a_valid_document() -> None:
    """Replay reads only the stored evidence: the same text the live presenter writes, and the typed document."""
    stored = specimen_stored_run()
    run = stored.run
    assert isinstance(run, SpecimenRun)
    codecs, replays = evidence_by_key(SPECIMEN_STRATEGIES), replays_by_key(SPECIMEN_STRATEGIES)
    assert project_specimen_run(run, codecs=codecs, replays=replays) == "SPEC specimen value: 6.0"
    document = project_specimen_run(run, ReplayOptions(mode=PresentationMode.JSON), codecs=codecs, replays=replays)
    assert SPECIMEN.json_envelope.model_validate_json(document).model_dump()["result"]["scaled"] == 6.0
    assert decode_specimen_run(run, codecs) == stored.result


def test_t8_a_corrupted_specimen_run_is_rejected_not_decoded() -> None:
    """An unknown key, another version tuple and an evidence mismatch each raise the production errors."""
    run = specimen_stored_run().run
    assert isinstance(run, SpecimenRun)
    codecs = evidence_by_key(SPECIMEN_STRATEGIES)
    assert run.result_evidence is not None
    for bad in (
        replace_run(run, evidence_codec_version=9),
        replace_run(run, method_version=2),
    ):
        with pytest.raises(ValueError, match="Unsupported Analysis Run method or version"):
            decode_specimen_run(bad, codecs)
    with pytest.raises(ValueError, match="Invalid stored Specimen evidence"):
        decode_specimen_run(replace_run(run, result_evidence={**run.result_evidence, "extra": 1}), codecs)
    with pytest.raises(ValueError, match="Invalid stored Specimen evidence"):
        decode_specimen_run(replace_run(run, ticker="OTHER"), codecs)


def replace_run(run: SpecimenRun, **changes: Any) -> SpecimenRun:
    """Return a copy of ``run`` with fields changed, validated like any other."""
    return SpecimenRun.model_validate({**run.model_dump(), **changes})


# ---------------------------------------------------------------------------
# T11: undeclared inputs fail closed, over the specimen tuples
# ---------------------------------------------------------------------------


def test_t11_every_dispatcher_over_the_specimen_tuples_rejects_an_undeclared_input() -> None:
    """The production dispatchers are given a fifth strategy and still fail closed for every probe."""
    gaps = conformance.undeclared_input_gaps(
        SPECIMEN_STRATEGIES,
        SPECIMEN_EVALUATION_STRATEGIES,
        SPECIMEN_CLI_STRATEGIES,
        local_runs=(specimen_stored_run(),),
        outside_tool_names=(SPECIMEN,),
    )
    assert gaps == []


def test_t11_a_specimen_bundle_rejects_another_strategy_s_objects_and_they_reject_its_own() -> None:
    """Every guard is an exact-type check in both directions, so no object is routed to the wrong strategy."""
    result = specimen_stored_run().result
    behavior = SPECIMEN.behavior
    assert isinstance(result, SpecimenResult)
    subclassed: object = object.__new__(type("_Subclassed", (SpecimenResult,), {}))
    for foreign in (object(), subclassed):
        with pytest.raises(UndeclaredStrategyError):
            behavior.encode_object(foreign)
    with pytest.raises(UndeclaredStrategyError):
        MOMENTUM.behavior.encode_object(result)
    with pytest.raises(UndeclaredStrategyError):
        behavior.native_status_of(GRAHAM_NUMBER)
    with pytest.raises(UndeclaredStrategyError):
        behavior.bind_handler(object(), ToolRuntime(clock=lambda: _CLOCK))


# ---------------------------------------------------------------------------
# T22: the specimen's command run with --save-run
# ---------------------------------------------------------------------------


def _saved_runs(*arguments: str) -> Callable[[], tuple[SpecimenRun, ...]]:
    def run() -> tuple[SpecimenRun, ...]:
        SPECIMEN_RUN_STORE.clear()
        exit_code, output = _invoke(*arguments)
        assert exit_code == 0, output
        return tuple(SPECIMEN_RUN_STORE.runs)

    return run


def test_t22_the_specimen_command_saves_one_run_under_its_descriptors_key(specimen_config_folder: Path) -> None:
    """The real command, through the specimen's Typer app, stores exactly one run its codec accepts."""
    del specimen_config_folder
    stored = {SPECIMEN.alias: _saved_runs("SPEC", "--value", "3", "--save-run")}
    assert conformance.run_record_gaps((SPECIMEN,), stored, decode_specimen_run) == []
    (run,) = SPECIMEN_RUN_STORE.runs
    assert (run.analysis_id, run.method_id) == (SPECIMEN.analysis_id, SPECIMEN.method_id)
    assert run.result_evidence is not None
    assert run.result_evidence["scaled"] == 6.0


def test_t22_without_save_run_the_specimen_command_stores_nothing(specimen_config_folder: Path) -> None:
    """The flag decides whether a run is stored."""
    del specimen_config_folder
    SPECIMEN_RUN_STORE.clear()
    assert _invoke("SPEC", "--value", "3")[0] == 0
    assert SPECIMEN_RUN_STORE.runs == []


def test_t22_names_a_specimen_alias_with_no_fixture_and_a_command_that_stores_nothing() -> None:
    """The production run check can fail for the specimen, as it does for the four production aliases."""
    assert conformance.run_record_gaps((SPECIMEN,), {}, decode_specimen_run) == [
        "no save-run fixture for alias 'specimen-test'"
    ]
    nothing: dict[str, Callable[[], Sequence[SpecimenRun]]] = {SPECIMEN.alias: lambda: ()}
    assert conformance.run_record_gaps((SPECIMEN,), nothing, decode_specimen_run) == [
        "alias 'specimen-test' stored no run"
    ]


# ---------------------------------------------------------------------------
# T12: the negative control, on the specimen
# ---------------------------------------------------------------------------


def test_t12_part_1_a_specimen_added_to_the_production_tuple_with_no_tier_entries_is_reported_on_every_surface() -> (
    None
):
    """A declaration with no entries anywhere is reported on each surface that is still a table or a file."""
    assert find_wiring_gaps((*STRATEGIES, SPECIMEN), _production_surfaces()) == [
        f"strategy {_KEY} is not wired in: CLI tier; evaluation tier; published schemas"
    ]


def test_t12_part_2_a_removed_evaluation_tier_entry_yields_exactly_one_gap_naming_the_specimen() -> None:
    """With the specimen's evaluation-tier entry removed, one gap names that tier and the specimen, and no other."""
    incomplete = tuple(entry for entry in SPECIMEN_EVALUATION_STRATEGIES if entry is not SPECIMEN_EVALUATION)
    assert len(incomplete) == len(STRATEGIES)
    gaps = find_wiring_gaps(SPECIMEN_STRATEGIES, _specimen_surfaces(evaluation_tier=incomplete))
    assert gaps == [f"strategy {_KEY} is not wired in: evaluation tier"]
    assert find_wiring_gaps(SPECIMEN_STRATEGIES, _specimen_surfaces()) == []


def test_t12_part_3_the_production_tier_check_body_fails_for_the_specimen_tuples_with_one_entry_missing() -> None:
    """The very function the production T10 tests call raises ``AssertionError`` for a forgotten specimen entry.

    No production table is patched: the specimen tuples are passed in, as the check bodies take them.
    """
    assert_wired(STRATEGIES, _production_surfaces())
    assert_wired(SPECIMEN_STRATEGIES, _specimen_surfaces())
    incomplete_cli = tuple(entry for entry in SPECIMEN_CLI_STRATEGIES if entry is not SPECIMEN_CLI)
    with pytest.raises(AssertionError, match=re.escape(f"strategy {_KEY} is not wired in: CLI tier")):
        assert_wired(SPECIMEN_STRATEGIES, _specimen_surfaces(cli_tier=incomplete_cli))
    incomplete_eval = tuple(entry for entry in SPECIMEN_EVALUATION_STRATEGIES if entry is not SPECIMEN_EVALUATION)
    with pytest.raises(AssertionError, match=re.escape(f"strategy {_KEY} is not wired in: evaluation tier")):
        assert_wired(SPECIMEN_STRATEGIES, _specimen_surfaces(evaluation_tier=incomplete_eval))
    everywhere = f"strategy {_KEY} is not wired in: CLI tier; evaluation tier; published schemas"
    with pytest.raises(AssertionError, match=re.escape(everywhere)):
        assert_wired((*STRATEGIES, SPECIMEN), _production_surfaces())


def test_t12_part_4_an_incomplete_bundle_is_a_type_error_and_a_foreign_object_is_an_undeclared_strategy() -> None:
    """A bundle built without one member raises ``TypeError``; a dispatcher given another strategy's type raises."""
    members: dict[str, Any] = {
        field.name: getattr(MOMENTUM.behavior, field.name) for field in dataclasses.fields(StrategyBehavior)
    }
    for name in members:
        with pytest.raises(TypeError, match=name):
            StrategyBehavior(**{key: value for key, value in members.items() if key != name})
    with pytest.raises(UndeclaredStrategyError):
        SPECIMEN.behavior.encode_object(object.__new__(MOMENTUM.behavior.result_type))
    with pytest.raises(UndeclaredStrategyError):
        MOMENTUM.behavior.encode_object(
            SpecimenAnalyzer(multiplier=2.0).run_analysis(
                "X", SpecimenConfig(1.0), SpecimenSelection(value=1.0).to_analysis_context(_CLOCK)
            )
        )


# ---------------------------------------------------------------------------
# The catalog test pins the specimen's case ids
# ---------------------------------------------------------------------------


def test_the_catalog_pins_the_specimen_case_ids() -> None:
    """The ids the catalog check reads from this file are the ids of the specimen's cases."""
    assert CATALOG_CASE_IDS == _PINNED_CASE_IDS
    assert Path(__file__).resolve() == (REPOSITORY_ROOT / "tests" / "test_specimen_strategy.py")
