"""A collection error in a conformance test module ends with the line that names the status command."""

from typing import Any

import pytest

from tests._collection_hint import CONFORMANCE_MODULES, HINT, SECTION, add_hint


def _failed_report(nodeid: str) -> pytest.CollectReport:
    try:
        raise ModuleNotFoundError("No module named 'investment_analysis_engine.strategies.fcf_growth.replay'")
    except ModuleNotFoundError:
        info = pytest.ExceptionInfo.from_current()
    return pytest.CollectReport(nodeid, "failed", info.getrepr(), [])


def _text(report: pytest.CollectReport) -> str:
    return str(report.longrepr)


def test_a_failed_collection_of_a_conformance_module_gains_the_hint() -> None:
    report = _failed_report("tests/test_strategy_wiring_conformance.py")
    add_hint(report)
    text = _text(report)
    assert "ModuleNotFoundError" in text
    assert SECTION in text
    assert HINT in text
    assert text.rstrip().endswith(HINT)


class _ImportErrorRepr:
    """Stands in for the representation pytest gives an import error of a test module: it holds the message text."""

    def __init__(self, longrepr: str) -> None:
        self.longrepr = longrepr


def test_an_import_error_of_the_module_itself_gains_the_hint() -> None:
    representation = _ImportErrorRepr("ImportError while importing test module")
    stand_in: Any = representation
    report = pytest.CollectReport("tests/test_strategy_wiring_conformance.py", "failed", stand_in, [])
    add_hint(report)
    assert representation.longrepr == "ImportError while importing test module\n" + HINT


def test_a_text_report_gains_the_hint() -> None:
    report = pytest.CollectReport("tests/test_strategy_wiring_conformance.py", "failed", "boom", [])
    add_hint(report)
    assert report.longrepr == "boom\n" + HINT


def test_the_hint_names_the_status_command_in_its_module_form() -> None:
    assert "uv run python -m scripts.strategy_status" in HINT
    assert "which site" in HINT


@pytest.mark.parametrize("nodeid", ["tests/test_config.py", "tests/scripts/test_strategy_sites.py"])
def test_another_module_is_left_alone(nodeid: str) -> None:
    report = _failed_report(nodeid)
    before = _text(report)
    add_hint(report)
    assert _text(report) == before


def test_a_collection_that_passed_is_left_alone() -> None:
    report = pytest.CollectReport("tests/test_strategy_wiring_conformance.py", "passed", None, [])
    add_hint(report)
    assert report.longrepr is None


def test_every_listed_module_exists() -> None:
    from scripts.repository_root import REPOSITORY_ROOT  # noqa: PLC0415 - only this test needs the root

    assert all((REPOSITORY_ROOT / name).is_file() for name in CONFORMANCE_MODULES)
