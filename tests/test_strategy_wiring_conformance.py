"""Conformance of the closed strategy declaration to the surfaces that are declared independently of it.

Each test asserts that one check body in ``scripts/strategy_conformance.py`` reports no gap over the
production descriptors. Every check body takes its tuple as a parameter, so a second test challenges it with
a deliberately incomplete copy and requires a gap that names the missing wiring. The tests make no network,
provider or LLM call.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import strategy_conformance as conformance
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.strategy_wiring import (
    BY_ARGUMENTS,
    BY_KEY,
    BY_METHOD_ID,
    BY_RESULT_TYPE,
    BY_TOOL,
    FCF_GROWTH,
    GRAHAM_GROWTH,
    GRAHAM_NUMBER,
    MOMENTUM,
    STRATEGIES,
)

_WIRING = Path(__file__).resolve().parents[1] / "src" / "strategy_wiring.py"


def test_t1_selection_union_ids_match_the_descriptors() -> None:
    """Every selection class has a descriptor with the same identifiers, and every descriptor a selection class."""
    assert conformance.selection_union_gaps(STRATEGIES) == []


def test_t1_names_a_selection_class_with_no_descriptor() -> None:
    """A strategy added to the selection union only is reported by name."""
    gaps = conformance.selection_union_gaps(STRATEGIES[:-1])
    assert gaps == [
        "selection class FCFGrowthSelection with ids ('fcf_earnings_growth', 'reported_fcf_eps_cagr') has no descriptor"
    ]


def test_t1_names_a_descriptor_with_no_selection_class() -> None:
    """A descriptor with identifiers no selection class carries is reported by identity."""
    stray = replace(MOMENTUM, analysis_id="stray", method_id="stray")
    gaps = conformance.selection_union_gaps((*STRATEGIES, stray))
    assert gaps == ["descriptor ('stray', 'stray') has no selection class in SelectionMember"]


def test_t2_native_evidence_union_matches_the_descriptors() -> None:
    """The result types the descriptors declare are exactly the ``NativeEvidence`` union."""
    assert conformance.native_evidence_union_gaps(STRATEGIES) == []
    gaps = conformance.native_evidence_union_gaps(STRATEGIES[1:])
    assert gaps == ["MomentumRun is in NativeEvidence but no descriptor declares it"]


def test_t3_result_types_match_the_analyzers_found_by_package_walk() -> None:
    """Each descriptor's result type is the ``ResultT`` of exactly one analyzer, and every analyzer has a descriptor."""
    assert conformance.analyzer_generics_gaps(STRATEGIES) == []
    gaps = conformance.analyzer_generics_gaps(STRATEGIES[:1])
    assert len(gaps) == 3
    assert all("which no descriptor declares" in gap for gap in gaps)


def test_t4_tool_surfaces_agree() -> None:
    """``ToolName``, the descriptors and the src-defined argument models name the same four tools."""
    assert conformance.tool_surface_gaps(STRATEGIES) == []
    gaps = conformance.tool_surface_gaps(STRATEGIES[:-1])
    assert any("ANALYZE_FCF_EARNINGS_GROWTH is in ToolName but no descriptor binds it" in gap for gap in gaps)
    assert any("FCFEarningsGrowthToolArguments subclasses AnalysisToolArguments" in gap for gap in gaps)


def test_t4_ignores_argument_subclasses_defined_outside_src() -> None:
    """A test-defined arguments subclass must not make the comparison depend on test order."""

    class _TestOnlyArguments(AnalysisToolArguments):
        pass

    assert _TestOnlyArguments in AnalysisToolArguments.__subclasses__()
    assert conformance.tool_surface_gaps(STRATEGIES) == []


def test_t5_every_catalog_case_routes_to_the_tool_its_constraints_require() -> None:
    """Reviewed case constraints name tools by hand; the descriptors' argument routing must agree."""
    assert conformance.case_routing_gaps(STRATEGIES) == []
    gaps = conformance.case_routing_gaps(STRATEGIES[1:])
    assert gaps
    assert all(gap.startswith("case MOM-") and "Momentum" in gap for gap in gaps)


def test_t6_every_tool_has_a_golden_case_and_every_case_is_served() -> None:
    """The fixture composition serves each catalog case with the result type its descriptor declares."""
    assert conformance.evaluation_coverage_gaps(STRATEGIES) == []
    gaps = conformance.evaluation_coverage_gaps(STRATEGIES[:-1])
    assert any("tool analyze_fcf_earnings_growth" not in gap and "FCF-" in gap for gap in gaps)


def test_t11_undeclared_inputs_fail_closed() -> None:
    """Every dispatcher rejects an input that matches no declared strategy and names it."""
    assert conformance.undeclared_input_gaps(STRATEGIES) == []


def test_t11_reports_a_dispatcher_that_accepts_an_undeclared_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check can fail: a lookup that routes everything to one strategy is reported."""

    def route_everything_to_momentum(*_: object) -> object:
        return MOMENTUM.tool

    monkeypatch.setattr(conformance, "tool_for_arguments", route_everything_to_momentum)
    gaps = conformance.undeclared_input_gaps(STRATEGIES)
    assert gaps == ["tool_for_arguments(undeclared model): accepted an undeclared input"]


def test_t14_wiring_files_declare_no_discovery_or_registration() -> None:
    """The root and every strategy-owned file have no discovery, self-registration or registry-like name."""
    files = conformance.wiring_files()
    assert _WIRING in files
    assert len(files) > 30
    assert conformance.discovery_gaps(files) == []
    assert conformance.closed_tuple_gaps(_WIRING, ["STRATEGIES"]) == []
    assert (
        conformance.read_only_index_gaps(
            {
                "BY_KEY": BY_KEY,
                "BY_METHOD_ID": BY_METHOD_ID,
                "BY_TOOL": BY_TOOL,
                "BY_ARGUMENTS": BY_ARGUMENTS,
                "BY_RESULT_TYPE": BY_RESULT_TYPE,
            }
        )
        == []
    )


def test_t14_reports_each_kind_of_drift(tmp_path: Path) -> None:
    """Every discovery, registration and self-registration pattern is reported with its file and line."""
    source = tmp_path / "drift.py"
    source.write_text(
        "import importlib\n"
        "from pkgutil import walk_packages\n"
        "from src.cli import app\n"
        "import typer\n"
        "\n"
        "\n"
        "def register_strategy(dispatcher, name):\n"
        "    dispatcher.register_tool(name, None)\n"
        "    app.command()(None)\n"
        "    typer.Typer()\n"
        "    return globals(), locals(), getattr(dispatcher, name), Base.__subclasses__()\n"
        "\n"
        "\n"
        "class StrategyRegistry:\n"
        "    pass\n"
        "\n"
        "\n"
        "def load_all():\n"
        "    return getattr(dispatcher, 'fixed')\n",
        encoding="utf-8",
    )
    gaps = conformance.discovery_gaps([source], root=tmp_path)
    reported = " | ".join(gaps)
    for expected in (
        "imports importlib",
        "imports from pkgutil",
        "imports the Typer app",
        "defines register_strategy",
        "registers a tool",
        "registers a command on the Typer app",
        "constructs a Typer app",
        "calls globals",
        "calls locals",
        "calls getattr with a computed name",
        "uses __subclasses__",
        "defines StrategyRegistry",
        "defines load_all",
    ):
        assert expected in reported, expected
    assert "drift.py:19" not in reported, "getattr with a literal name is permitted"


def test_t14_reports_a_closed_tuple_that_is_not_a_literal_of_constants(tmp_path: Path) -> None:
    """A closed tuple must be a literal of module constants, and a read-only index must be a read-only mapping."""
    source = tmp_path / "wiring.py"
    source.write_text("ONE = 1\nSTRATEGIES = (ONE, make())\nOTHER = [ONE]\n", encoding="utf-8")
    assert conformance.closed_tuple_gaps(source, ["STRATEGIES", "OTHER", "MISSING"]) == [
        "wiring.py: STRATEGIES holds an element that is not a module constant or pair_* call",
        "wiring.py: OTHER is not a tuple literal",
        "wiring.py: MISSING is not declared",
    ]
    assert conformance.read_only_index_gaps({"BY_X": {}}) == ["BY_X is not a read-only mapping"]


def test_t15_the_descriptor_and_its_behavior_are_closed() -> None:
    """The descriptor has the documented fields and is frozen and non-generic; its behavior has its members."""
    assert conformance.descriptor_is_closed_gaps() == []


def test_t15_reports_an_undocumented_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a field or a behavior member without a reviewed edit to the documented set fails."""
    monkeypatch.setattr(conformance, "DESCRIPTOR_FIELDS", {"analysis_id": str})
    monkeypatch.setattr(conformance, "BEHAVIOR_MEMBERS", frozenset({"result_type"}))
    gaps = conformance.descriptor_is_closed_gaps()
    assert len(gaps) == 2
    assert gaps[0].startswith("descriptor fields differ from the documented set")
    assert gaps[1].startswith("behavior members differ from the documented set")


def test_t16_every_field_and_view_accessor_is_read_outside_the_root() -> None:
    """No descriptor field and no consumer-visible behavior accessor is dead."""
    assert conformance.unused_field_gaps(conformance.source_files(), _WIRING) == []


def test_t16_counts_only_reads_on_descriptor_typed_expressions() -> None:
    """``descriptor.tool`` counts; the same attribute on a selection or a plain variable does not."""
    snippet = (
        "from src.strategy_wiring import STRATEGIES, BY_TOOL, StrategyDescriptor\n"
        "def f(selection, one: StrategyDescriptor, many: tuple[StrategyDescriptor, ...]):\n"
        "    selection.analysis_id\n"
        "    one.tool\n"
        "    [m.method_id for m in many]\n"
        "    for d in STRATEGIES:\n"
        "        d.behavior.result_type\n"
        "    BY_TOOL[x].tool_arguments\n"
        "    require(BY_TOOL, x).behavior.native_status_of\n"
        "    unrelated.tool_description\n"
    )
    assert conformance.descriptor_reads(snippet) == {
        "tool",
        "method_id",
        "behavior",
        "result_type",
        "tool_arguments",
        "native_status_of",
    }
    assert conformance.descriptor_reads("def g(m):\n    m.analysis_id\n", frozenset({"MOMENTUM"})) == set()
    assert conformance.descriptor_reads("MOMENTUM.analysis_id\n", frozenset({"MOMENTUM"})) == {"analysis_id"}


def test_t16_reports_a_field_nothing_reads(tmp_path: Path) -> None:
    """A field or accessor with no read outside the defining module is reported by name."""
    reader = tmp_path / "reader.py"
    reader.write_text(
        "from src.strategy_wiring import STRATEGIES\nfor d in STRATEGIES:\n    d.tool\n", encoding="utf-8"
    )
    gaps = conformance.unused_field_gaps([reader], _WIRING)
    assert "tool is never read outside strategy_wiring.py" not in gaps
    assert "analysis_id is never read outside strategy_wiring.py" in gaps
    assert "bind_handler is never read outside strategy_wiring.py" in gaps


def test_t17_the_analyzer_invocation_envelope_is_unchanged() -> None:
    """``run_analysis(ticker, config, context)`` and the four ``AnalysisContext`` fields are as documented."""
    assert conformance.analyzer_envelope_gaps() == []


def test_t17_reports_a_changed_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """A change to the documented parameters or context fields fails."""
    monkeypatch.setattr(conformance, "ANALYZER_ENVELOPE_PARAMETERS", ("self", "ticker"))
    monkeypatch.setattr(conformance, "ANALYZER_CONTEXT_FIELDS", ("as_of",))
    assert len(conformance.analyzer_envelope_gaps()) == 2


def test_t24_each_uniqueness_rule_rejects_a_duplicate_and_names_both_descriptors() -> None:
    """Duplicating each key in a copy of the tuple raises, naming the rule and both descriptors."""
    assert conformance.uniqueness_gaps(STRATEGIES) == []
    assert conformance.uniqueness_gaps(STRATEGIES[:1]) == [
        "uniqueness rules cannot be challenged with fewer than two descriptors"
    ]


@pytest.mark.parametrize("descriptor", [MOMENTUM, GRAHAM_NUMBER, GRAHAM_GROWTH, FCF_GROWTH])
def test_the_four_strategies_are_declared_in_order_with_their_existing_identifiers(descriptor: object) -> None:
    """The declaration order is the order tools are registered and advertised to the model."""
    assert descriptor in STRATEGIES
    assert [item.tool.value for item in STRATEGIES] == [
        "analyze_momentum",
        "analyze_graham_number",
        "analyze_graham_growth_value",
        "analyze_fcf_earnings_growth",
    ]
