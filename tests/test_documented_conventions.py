"""The contributor guide, the lasting authorization of the strategy descriptor and Momentum's one profile composition.

Three conventions are written down in prose or confined to one function. Each test fails with a message that
names what moved, so a rename or a second copy cannot go unnoticed. The single-valued provider option and field
are kept out of every strategy by two tests, the run outcome is kept out of every strategy and template by a scan and
a totality test of the shared rule, and the last test keeps one word out of failure text.
"""

import ast
import dataclasses
import importlib
import re
from pathlib import Path
from typing import Final, get_args, get_origin, get_type_hints

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from investment_analysis_engine.analysis.base_analyzer import BaseAnalyzer
from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyBehavior
from scripts.repository_root import REPOSITORY_ROOT
from tests._cli_helpers import normalize_cli_output

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


_REMOVED_OPTION_COMMANDS: Final = (
    *(
        ([descriptor.alias], descriptor.alias)
        for entry in CLI_STRATEGIES
        for descriptor in STRATEGIES
        if descriptor.behavior is entry.behavior
    ),
    (["watchlist", "create", "Core"], "watchlist create"),
    (["watchlist", "add-selection", "Core"], "watchlist add-selection"),
)


def _field_names(model: type) -> list[str]:
    """Return the field names of a Pydantic model or a dataclass."""
    if issubclass(model, BaseModel):
        return list(model.model_fields)
    assert dataclasses.is_dataclass(model), f"{model.__name__} is neither a Pydantic model nor a dataclass."
    return [field.name for field in dataclasses.fields(model)]


@pytest.mark.parametrize(
    ("prefix", "label"), _REMOVED_OPTION_COMMANDS, ids=[label for _, label in _REMOVED_OPTION_COMMANDS]
)
def test_data_provider_option_is_rejected_with_exit_2(prefix: list[str], label: str) -> None:
    arguments = [*prefix, "AAPL", "--data-provider", "sec_edgar"]
    if prefix[0] == "watchlist":
        arguments += ["-a", "momentum"]
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 2, (
        f"{label} must reject --data-provider as an unknown option (exit 2); it exited {result.exit_code}. "
        "A strategy has one provider for each kind of fact, so the option can hold only one value."
    )
    output = normalize_cli_output(result.output)
    assert "No such option" in output, f"{label} exited 2 but not for an unknown option; the output was {output!r}."
    assert "--data-provider" in output, f"{label} does not name --data-provider as the unknown option: {output!r}."


def _config_type_of(deps_type: type) -> type:
    """Return the config type ``C`` of the ``BaseAnalyzer[C, R]`` that a strategy's tool dependencies hold."""
    analyzer = get_type_hints(deps_type)["analyzer"]
    for base in getattr(analyzer, "__orig_bases__", ()):
        if get_origin(base) is BaseAnalyzer:
            config_type = get_args(base)[0]
            assert isinstance(config_type, type), f"{analyzer.__name__} declares no concrete config type."
            return config_type
    raise AssertionError(f"{analyzer.__name__} does not subclass BaseAnalyzer[ConfigT, ResultT].")


def test_no_strategy_model_has_a_provider_id_field() -> None:
    models: list[type] = []
    for descriptor in STRATEGIES:
        behavior = descriptor.behavior
        assert isinstance(behavior, StrategyBehavior), f"{descriptor.alias} declares no strategy behavior."
        models += [_config_type_of(behavior.deps_type), behavior.selection_type, behavior.deps_type]
    offenders = [
        f"{model.__name__}.{name}" for model in models for name in _field_names(model) if name.endswith("provider_id")
    ]
    assert offenders == [], (
        f"{offenders} hold a provider identifier a strategy owns as a named constant: a field that can hold only "
        "one value is not added."
    )


STRATEGIES_PACKAGE: Final = REPOSITORY_ROOT / "investment_analysis_engine" / "strategies"


def test_no_strategy_function_has_a_provider_id_parameter() -> None:
    offenders: list[str] = []
    for path in sorted(STRATEGIES_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            arguments = node.args
            names = [arg.arg for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
            names += [arg.arg for arg in (arguments.vararg, arguments.kwarg) if arg is not None]
            offenders += [
                f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{node.lineno}: {node.name}({name})"
                for name in names
                if name.endswith("provider_id")
            ]
    assert offenders == [], (
        f"{offenders} take a provider identifier a strategy owns as a named constant: a parameter that holds one "
        "value in production is not added. Provenance fields are class fields, not parameters."
    )


def test_no_strategy_class_has_a_provider_id_field() -> None:
    offenders: list[str] = []
    for path in sorted(STRATEGIES_PACKAGE.rglob("*.py")):
        if path.name == "envelope.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            offenders += [
                f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{item.lineno}: {node.name}.{item.target.id}"
                for item in node.body
                if isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id.endswith("provider_id")
            ]
    assert offenders == [], (
        f"{offenders} hold a provider identifier a strategy owns as a named constant. Only the evidence document of "
        "a strategy (envelope.py) records the source of a fact."
    )


_WORD: Final = "sen" + "tence"
"""The scanned word, written in two pieces so that this file does not contain it."""
_MESSAGE_RULE: Final = (
    'User-facing failure text is a "message", optionally prefixed by its field, as in "reason message". '
    f'"{_WORD.capitalize()}" is correct only where actual {_WORD}s are counted: add the phrase to '
    "_ALLOWED_PHRASES only then."
)
_SCAN_ROOTS: Final = ("investment_analysis_engine", "scripts", "tests", "schemas", "docs", "AGENTS.md", "README.md")
_SCAN_EXCLUDED: Final = REPOSITORY_ROOT / "docs" / "project" / "milestones"
_SCAN_SUFFIXES: Final = frozenset({".py", ".md", ".json", ".toml", ".txt", ".tmpl", ".yml", ".yaml"})
_ALLOWED_PHRASES: Final = tuple(
    phrase.format(w=_WORD)
    for phrase in (
        "one {w}",
        "one-{w}",
        "every {w}",
        "each {w}",
        "each written {w}",
        "a written {w}",
        "a fluent {w}",
        "a {w} that fails",
        "a {w} as if",
        "one friendly {w}",
        "write {w}s",
        "writes {w}s",
        "writes the {w}s",
        "check {w}s",
        "checks {w}s",
        "{w} checking",
        "{w}s in an answer",
        "{w}s that name",
        "{w}s shown",
        "correct {w}s",
        "draft {w}s",
        "failed {w}s",
        "too many {w}s",
    )
)
"""The phrases that count units of text, or describe the text of a plain-English answer."""


def _scanned_files() -> list[Path]:
    """Return the text files the word scan covers, in a stable order."""
    found: list[Path] = []
    for root in _SCAN_ROOTS:
        base = REPOSITORY_ROOT / root
        candidates = [base] if base.is_file() else sorted(base.rglob("*"))
        found += [
            path
            for path in candidates
            if path.is_file()
            and path.suffix in _SCAN_SUFFIXES
            and _SCAN_EXCLUDED not in path.parents
            and "__pycache__" not in path.parts
        ]
    return found


def test_the_scanned_word_appears_only_in_allowlisted_phrases() -> None:
    offenders: list[str] = []
    for path in _scanned_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.lower()
            if _WORD in lowered and not any(phrase in lowered for phrase in _ALLOWED_PHRASES):
                offenders.append(f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{number}: {_MESSAGE_RULE}")
    assert offenders == [], "\n".join(offenders)


_STRATEGIES_ROOT: Final = REPOSITORY_ROOT / "investment_analysis_engine" / "strategies"
_TEMPLATES_ROOT: Final = REPOSITORY_ROOT / "scripts" / "strategy_templates"
_OUTCOME_MEMBERS: Final = frozenset(member.name for member in RunOutcome)
_PLACEHOLDER: Final = re.compile(r"\$\{?\w+\}?")
_EXPECTED_OUTCOMES: Final = {
    CalculationStatus.OK: RunOutcome.COMPLETED,
    CalculationStatus.NOT_APPLICABLE: RunOutcome.NOT_APPLICABLE,
    CalculationStatus.INPUT_UNAVAILABLE: RunOutcome.UNAVAILABLE,
    CalculationStatus.INVALID_INPUT: RunOutcome.FAILED,
    CalculationStatus.PROVIDER_ERROR: RunOutcome.FAILED,
    None: RunOutcome.COMPLETED,
}


def _run_outcome_members_named(source: str) -> list[tuple[int, str]]:
    """Return ``(line, member)`` for each ``RunOutcome.<member>`` access in Python source."""
    return [
        (node.lineno, node.attr)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "RunOutcome"
        and node.attr in _OUTCOME_MEMBERS
    ]


def _outcome_scan_targets() -> list[Path]:
    """Return every strategy module and every generator template, in a stable order."""
    modules = sorted(path for path in _STRATEGIES_ROOT.rglob("*.py") if "__pycache__" not in path.parts)
    return [*modules, *sorted(_TEMPLATES_ROOT.glob("*.tmpl"))]


def test_no_strategy_module_or_template_names_a_run_outcome_member() -> None:
    offenders: list[str] = []
    for path in _outcome_scan_targets():
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".tmpl":
            source = _PLACEHOLDER.sub("x", source)
        offenders += [
            f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{line}: RunOutcome.{member} is decided by the shared "
            "rule RunOutcome.from_status, not by a strategy"
            for line, member in _run_outcome_members_named(source)
        ]
    assert offenders == [], "\n".join(offenders)


def test_the_outcome_scan_reports_a_member_and_accepts_the_rest() -> None:
    found = _run_outcome_members_named("x = RunOutcome.FAILED\n\ny = RunOutcome.COMPLETED")
    assert found == [(1, "FAILED"), (3, "COMPLETED")]
    accepted = "x = RunOutcome.from_status(None)\ny = Other.FAILED\nz = RunOutcome('failed')"
    assert _run_outcome_members_named(accepted) == []
    assert _outcome_scan_targets(), "The scan found no strategy module or template."


def test_run_outcome_from_status_is_total_and_matches_the_table() -> None:
    assert set(_EXPECTED_OUTCOMES) == {*CalculationStatus, None}, "The table lacks a status, or names one that is gone."
    for status, outcome in _EXPECTED_OUTCOMES.items():
        assert RunOutcome.from_status(status) is outcome, f"{status!r} must map to {outcome!r}."
