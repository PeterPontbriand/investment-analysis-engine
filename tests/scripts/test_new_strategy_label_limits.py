"""The generator's limits on the label and the module name, and the proof that its output holds at both limits.

At the longest label and the longest module name together, and for the longest candidates in the Step 3.5
specifications, the generator's output passes the Ruff lint and format checks and the strict type check in a copy of
the package. One character over either limit is a usage error that writes nothing.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from scripts.new_strategy import MAX_LABEL_LENGTH, MAX_MODULE_NAME_LENGTH, PACKAGE, main
from scripts.repository_root import REPOSITORY_ROOT
from tests.scripts.test_new_strategy_end_to_end import EXCLUDED, TIMEOUT_SECONDS, _environment

LONGEST_LABEL: Final = "Cash-Flow Valuation Multiples"
LONGEST_MODULE: Final = "cash_flow_valuation_multiples"
MAXIMUM_LABEL: Final = ("Maximum " * 6)[:MAX_LABEL_LENGTH].rstrip() + "x" * (MAX_LABEL_LENGTH - 39)
MAXIMUM_MODULE: Final = "m" + "o" * (MAX_MODULE_NAME_LENGTH - 1)


def _copy(destination: Path) -> None:
    for folder in (PACKAGE, "scripts"):
        shutil.copytree(REPOSITORY_ROOT / folder, destination / folder, ignore=shutil.ignore_patterns(*EXCLUDED))
    shutil.copyfile(REPOSITORY_ROOT / "pyproject.toml", destination / "pyproject.toml")


def _python(copy: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - the interpreter running this test, with arguments built here
        [sys.executable, *arguments],
        cwd=copy,
        env=_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def _generate_and_check(tmp_path: Path, module: str, label: str) -> None:
    copy = tmp_path / "repository"
    _copy(copy)
    generated = _python(copy, "-m", "scripts.new_strategy", module, "--label", label)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    for arguments in (("check", "--no-cache", PACKAGE), ("format", "--check", PACKAGE)):
        ruff = _python(copy, "-m", "ruff", *arguments)
        assert ruff.returncode == 0, f"ruff {' '.join(arguments)}\n{ruff.stdout}{ruff.stderr}"
    mypy = _python(copy, "-m", "mypy", "--strict", f"{PACKAGE}/strategies/{module}")
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    for path in (copy / PACKAGE / "strategies" / module).glob("*.py"):
        too_long = [n for n, line in enumerate(path.read_text("utf-8").splitlines(), 1) if len(line) > 120]
        assert not too_long, f"{path.name}: lines {too_long}"


def test_the_limits_are_proven_at_both_maxima_together(tmp_path: Path) -> None:
    """The longest label with the longest module name generates a lint-, format- and type-clean package."""
    assert len(MAXIMUM_LABEL) == MAX_LABEL_LENGTH
    assert len(MAXIMUM_MODULE) == MAX_MODULE_NAME_LENGTH
    _generate_and_check(tmp_path, MAXIMUM_MODULE, MAXIMUM_LABEL)


def test_the_longest_candidates_of_the_specifications_generate_cleanly(tmp_path: Path) -> None:
    """Cash-Flow Valuation Multiples, the longest name of Step 3.5, fits with margin and generates cleanly."""
    assert len(LONGEST_LABEL) < MAX_LABEL_LENGTH
    assert len(LONGEST_MODULE) < MAX_MODULE_NAME_LENGTH
    _generate_and_check(tmp_path, LONGEST_MODULE, LONGEST_LABEL)


@pytest.mark.parametrize(
    ("module", "label", "limit"),
    [
        ("probe", "x" * (MAX_LABEL_LENGTH + 1), str(MAX_LABEL_LENGTH)),
        ("m" * (MAX_MODULE_NAME_LENGTH + 1), "Probe", str(MAX_MODULE_NAME_LENGTH)),
    ],
)
def test_one_character_over_a_limit_is_a_usage_error_that_writes_nothing(
    module: str, label: str, limit: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A label or a module name one character over its limit exits with 2, names the limit and writes nothing."""
    with pytest.raises(SystemExit) as raised:
        main([module, "--label", label], root=tmp_path)

    assert raised.value.code == 2
    assert f"the limit is {limit}" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
