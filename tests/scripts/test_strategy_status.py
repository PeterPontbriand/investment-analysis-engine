"""The status command reports each edit site done or missing from the conformance suite's own checks."""

import importlib
import subprocess
import sys
from types import ModuleType

import pytest

from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts import strategy_status
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import load_sites


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
