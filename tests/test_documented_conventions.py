"""The contributor guide, the lasting authorization of the strategy descriptor and Momentum's one profile composition.

Three conventions are written down in prose or confined to one function. Each test fails with a sentence that
names what moved, so a rename or a second copy cannot go unnoticed.
"""

import ast
import importlib
import re
from pathlib import Path
from typing import Final

from scripts.repository_root import REPOSITORY_ROOT

GUIDE: Final = REPOSITORY_ROOT / "docs" / "TOOL_DEVELOPMENT.md"
OLD_GUIDE: Final = REPOSITORY_ROOT / "docs" / "project" / "ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md"
AGENTS: Final = REPOSITORY_ROOT / "AGENTS.md"
MOMENTUM_PACKAGE: Final = REPOSITORY_ROOT / "investment_analysis_engine" / "strategies" / "momentum"
GUIDE_SECTIONS: Final = (
    "At a glance",
    "Add a strategy: the workflow",
    "Edit sites of a strategy",
    "Strategy settings",
    "Background: how a strategy fits into the code",
)
CLOSED_TUPLES: Final = {
    "STRATEGIES": "investment_analysis_engine.strategy_wiring",
    "CLI_STRATEGIES": "investment_analysis_engine.cli_strategy_wiring",
    "EVALUATION_STRATEGIES": "investment_analysis_engine.evaluation.strategy_fixtures",
}
PROHIBITED_IN_AGENTS: Final = ("dynamic discovery", "plugin loading", "self-registration", "factory hierarchies")


def _section(text: str, heading_prefix: str) -> str:
    """Return the body of the ``## <heading_prefix>`` section of a Markdown document, up to the next ``## `` heading."""
    pattern = rf"^## {re.escape(heading_prefix)}[^\n]*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    assert match is not None, f"AGENTS.md has no section whose heading starts with {heading_prefix!r}."
    return match.group(1)


def test_the_contributor_guide_is_the_only_one_and_has_its_sections_in_order() -> None:
    assert GUIDE.is_file(), "docs/TOOL_DEVELOPMENT.md is the contributor guide and must exist."
    assert not OLD_GUIDE.exists(), "A second contributor guide was left at the old path."
    others = [path for path in (REPOSITORY_ROOT / "docs").rglob("*CONTRIBUTOR_GUIDE*") if path != GUIDE]
    assert others == [], f"Only one contributor guide may exist: {others}"
    headings = re.findall(r"^## (.+)$", GUIDE.read_text(encoding="utf-8"), flags=re.MULTILINE)
    positions = [headings.index(section) for section in GUIDE_SECTIONS if section in headings]
    assert len(positions) == len(GUIDE_SECTIONS), f"The guide lacks a required section; it has {headings}."
    assert positions == sorted(positions), f"The guide's sections are out of order; they are {headings}."


def test_agents_permits_the_closed_descriptor_tuples_in_section_3_without_section_0() -> None:
    text = AGENTS.read_text(encoding="utf-8")
    forbidden = _section(text, "3. Absolute forbidden actions")
    for name, module in CLOSED_TUPLES.items():
        assert name in forbidden, f"AGENTS.md section 3 does not name the permitted tuple {name}."
        assert isinstance(getattr(importlib.import_module(module), name), tuple), f"{module}.{name} is not a tuple."
    lowered = forbidden.lower()
    missing = [phrase for phrase in PROHIBITED_IN_AGENTS if phrase not in lowered]
    assert missing == [], f"AGENTS.md section 3 no longer prohibits {missing}."
    temporary = _section(text, "0. ")
    assert not any(name in temporary for name in CLOSED_TUPLES), (
        "The permission must stand outside the temporary section, which is removed later."
    )


def _calls(path: Path) -> list[tuple[str, str]]:
    """Return ``(function name, callee)`` for each call to the profile primitives in a module, by enclosing function."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, str]] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"InstrumentProfileCandidate", "compose_instrument_profile"}
            ):
                found.append((function.name, node.func.id))
    return found


def test_momentum_composes_its_instrument_profile_in_one_function() -> None:
    composing = {path.name: sorted(set(_calls(path))) for path in MOMENTUM_PACKAGE.glob("*.py") if _calls(path)}
    assert set(composing) == {"execution.py"}, f"Only execution.py may build the profile; found {sorted(composing)}."
    functions = {name for name, _ in composing["execution.py"]}
    assert functions == {"compose_momentum_profile"}, f"Only compose_momentum_profile may build it; found {functions}."
    cli = (MOMENTUM_PACKAGE / "cli.py").read_text(encoding="utf-8")
    assert cli.count("compose_momentum_profile(") == 3, "The direct, save-run and refresh paths must each call it."
