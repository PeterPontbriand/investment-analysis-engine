"""The status command reports each edit site done or missing from the conformance suite's own checks."""

import importlib
import subprocess
import sys
from types import ModuleType

import pytest

from investment_analysis_engine.orchestrator.tool_names import ToolName
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts import strategy_status
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import load_sites, strategy_names

FCF_GROWTH_PACKAGE = "investment_analysis_engine/strategies/fcf_growth"


def _module_of(alias: str) -> str:
    return alias.replace("-", "_")


@pytest.mark.parametrize("alias", [item.alias for item in STRATEGIES])
def test_every_declared_strategy_is_done(alias: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert strategy_status.main([_module_of(alias)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(load_sites())
    assert all(line.startswith("done     ") for line in lines)


def test_an_undeclared_name_reports_its_missing_sites_and_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert strategy_status.main(["piotroski"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "missing  vocabulary  investment_analysis_engine/strategies/piotroski/vocabulary.py" in lines
    assert any(
        "has no descriptor; declare it in investment_analysis_engine/strategy_wiring.py" in line for line in lines
    )
    assert "missing  guide  docs/user/strategies/PIOTROSKI.md" in lines


def test_an_alias_is_used_for_the_command_and_the_guide(capsys: pytest.CaptureFixture[str]) -> None:
    assert strategy_status.main(["piotroski", "--alias", "f-score"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "missing  guide  docs/user/strategies/F_SCORE.md" in lines
    assert "missing  schema  schemas/f-score.schema.json" in lines


def test_an_import_failure_is_the_first_gap_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_import = importlib.import_module

    def fail_for_conformance(name: str, package: str | None = None) -> ModuleType:
        if name == strategy_status.CONFORMANCE_MODULE:
            raise ImportError("cannot import name 'x'")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_for_conformance)
    assert strategy_status.main(["momentum"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "missing  import  scripts/strategy_conformance.py"
    assert "ImportError: cannot import name 'x'" in lines[1]
    assert len(lines) == 2


def _raised_in(relative_path: str, statement: str) -> BaseException:
    """Return the exception ``statement`` raises when it runs as if it were in the repository file ``relative_path``."""
    try:
        exec(compile(statement, str(REPOSITORY_ROOT / relative_path), "exec"), {})  # noqa: S102 - fixed test statement
    except Exception as error:  # noqa: BLE001 - the exception is the result
        return error
    raise AssertionError("the statement did not raise")


def _import_fails_with(
    error: BaseException, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> list[str]:
    """Run the status command for fcf_growth with the conformance import failing with ``error``."""
    real_import = importlib.import_module

    def fail_for_conformance(name: str, package: str | None = None) -> ModuleType:
        if name == strategy_status.CONFORMANCE_MODULE:
            raise error
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_for_conformance)
    assert strategy_status.main(["fcf_growth", "--alias", "fcf-growth"]) == 1
    return capsys.readouterr().out.splitlines()


def test_a_deleted_strategy_file_is_attributed_to_its_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A module that does not exist is matched with the site whose file it is, not with the file that imports it."""
    error = _raised_in(
        "investment_analysis_engine/strategy_wiring.py",
        "from investment_analysis_engine.strategies.fcf_growth import replay_that_is_gone",
    )
    missing = ModuleNotFoundError("No module named 'x'", name="investment_analysis_engine.strategies.fcf_growth.replay")
    missing.__traceback__ = error.__traceback__
    lines = _import_fails_with(missing, monkeypatch, capsys)
    assert lines[0] == f"missing  replay  {FCF_GROWTH_PACKAGE}/replay.py"
    assert "Original error: ModuleNotFoundError: No module named 'x'" in lines[1]
    assert len(lines) == 2


def test_an_emptied_strategy_file_is_attributed_to_its_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A name that a module no longer defines is matched with that module's site."""
    path = REPOSITORY_ROOT / FCF_GROWTH_PACKAGE / "presenter.py"
    error = ImportError("cannot import name 'render_x'", name=f"{FCF_GROWTH_PACKAGE.replace('/', '.')}.presenter")
    error.path = str(path)
    lines = _import_fails_with(error, monkeypatch, capsys)
    assert lines[0] == f"missing  presenter  {FCF_GROWTH_PACKAGE}/presenter.py"
    assert "Original error: ImportError: cannot import name 'render_x'" in lines[1]


def test_a_removed_tool_name_member_is_attributed_to_the_tool_name_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An attribute the ``ToolName`` enumeration lacks is matched with its file, not with the file that reads it."""
    try:
        _ = ToolName.A_MEMBER_THAT_WAS_REMOVED  # type: ignore[attr-defined]
    except AttributeError as caught:
        error = caught
    lines = _import_fails_with(error, monkeypatch, capsys)
    assert lines[0] == "missing  tool-name  investment_analysis_engine/orchestrator/tool_names.py"
    assert "AttributeError" in lines[1]
    assert "A_MEMBER_THAT_WAS_REMOVED" in lines[1]


def test_a_removed_tier_entry_is_attributed_to_the_tier_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An error raised in the tier file is matched with the tier's site, by the traceback."""
    error = _raised_in(
        "investment_analysis_engine/cli_strategy_wiring.py",
        "from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError\n"
        "raise UndeclaredStrategyError('The CLI tier has no entry for strategy x; it has entries for: y.')",
    )
    lines = _import_fails_with(error, monkeypatch, capsys)
    assert lines[0] == "missing  cli-tier  investment_analysis_engine/cli_strategy_wiring.py"
    assert "Original error: UndeclaredStrategyError: The CLI tier has no entry for strategy x" in lines[1]


def test_the_evaluation_tier_is_attributed_by_its_file(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = _raised_in("investment_analysis_engine/evaluation/strategy_fixtures.py", "raise LookupError('x')")
    lines = _import_fails_with(error, monkeypatch, capsys)
    assert lines[0] == "missing  evaluation-tier  investment_analysis_engine/evaluation/strategy_fixtures.py"


def test_a_removed_evaluation_tier_entry_is_attributed_to_the_tier_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A check that fails in the evaluation tier's file reports that site first, not the check that needed it."""
    from scripts import strategy_conformance  # noqa: PLC0415 - patched only here

    error = _raised_in(
        "investment_analysis_engine/evaluation/strategy_fixtures.py",
        "from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError\n"
        "raise UndeclaredStrategyError('The evaluation tier has no entry for tool x; it has entries for: y.')",
    )

    def explode(_names: object) -> list[object]:
        raise error

    monkeypatch.setattr(strategy_conformance, "site_codec", explode)
    assert strategy_status.main(["fcf_growth", "--alias", "fcf-growth"]) == 1
    lines = capsys.readouterr().out.splitlines()
    first = next(index for index, line in enumerate(lines) if line.startswith("missing"))
    assert lines[first] == "missing  evaluation-tier  investment_analysis_engine/evaluation/strategy_fixtures.py"
    assert "the check of codec could not run" in lines[first + 1]
    assert "Original error: UndeclaredStrategyError: The evaluation tier has no entry for tool x" in lines[first + 1]


def test_an_error_that_matches_no_site_keeps_the_import_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = _raised_in("scripts/strategy_conformance.py", "raise RuntimeError('unrelated')")
    lines = _import_fails_with(error, monkeypatch, capsys)
    assert lines[0] == "missing  import  scripts/strategy_conformance.py"
    assert "RuntimeError: unrelated" in lines[1]


def test_the_first_file_an_error_points_at_wins_over_the_traceback() -> None:
    """The module an ``ImportError`` names is the site, although the importing file is also a site's file."""
    error = _raised_in(
        "investment_analysis_engine/strategy_wiring.py",
        "raise ImportError('x', name='investment_analysis_engine.strategies.fcf_growth.tool')",
    )
    site = strategy_status.attributed_site(error, strategy_names("fcf_growth", "fcf-growth"), load_sites())
    assert site is not None
    assert site.id == "tool"


def test_a_check_that_raises_is_a_missing_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import strategy_conformance  # noqa: PLC0415 - patched only here

    def explode(_names: object) -> list[object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(strategy_conformance, "site_descriptor", explode)
    assert strategy_status.main(["momentum"]) == 1
    out = capsys.readouterr().out
    assert "missing  descriptor  investment_analysis_engine/strategy_wiring.py" in out
    assert "the check site_descriptor raised RuntimeError: boom" in out


@pytest.mark.parametrize("arguments", [[], ["Not-A-Module"], ["momentum", "--alias", "Bad_Alias"]])
def test_a_usage_error_exits_2(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        strategy_status.main(arguments)
    assert raised.value.code == 2
    assert capsys.readouterr().err


def test_the_script_runs_as_a_file_from_the_repository_root() -> None:
    result = subprocess.run(  # noqa: S603 - fixed arguments, the current interpreter
        [sys.executable, "scripts/strategy_status.py", "momentum"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith("done     vocabulary  ")
