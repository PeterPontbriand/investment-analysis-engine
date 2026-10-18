"""The only place the specimen's types cross the closed production types.

The specimen deliberately stays outside three closed production declarations: ``ToolName``, the selection union
(``SelectionMember`` and the ``AnalysisSelection`` built from it) and the ``NativeEvidence`` union with the
``StrategyBehavior`` bounds that name them (SWC plan Appendix B.19). Naming the specimen in any of them would put a
test fixture into production, so the descriptor, the tier entries and the behavior reach those types through the
functions below, one per crossing, and no other specimen file calls ``cast``. A test enforces that.

The layers behind these crossings are not exercised by the specimen. The generator's end-to-end test (T28) adds a
strategy to a temporary copy of the repository through the real declarations, with no ``cast``, and covers them.
"""

from typing import cast

from investment_analysis_engine.orchestrator.tool_names import ToolName
from investment_analysis_engine.orchestrator.tool_runtime import AnalysisToolHandler
from investment_analysis_engine.workspace.strategy_types import NativeEvidence, SelectionMember
from tests.specimen.analyzer import SpecimenResult
from tests.specimen.selection import SpecimenSelection
from tests.specimen.tool import SpecimenTool, SpecimenToolHandler


def as_tool_name(tool: SpecimenTool) -> ToolName:
    """Return the specimen's tool where the descriptor's ``tool`` field wants a ``ToolName``.

    ``ToolName`` is a closed enumeration that ``register_analysis_tools`` checks handlers against in both
    directions, so the specimen cannot be a member and names its tool with an enumeration of its own. Option B
    requires the crossing because the descriptor's field is typed with ``ToolName``.
    """
    return cast("ToolName", tool)


def as_selection_member(selection: SpecimenSelection) -> SelectionMember:
    """Return the specimen's selection where a tier entry wants a ``SelectionMember``.

    The union is the type an ``AnalysisRun`` validates a selection against; the specimen is not in it, and the
    tier entries (``CliStrategy.build``, ``EvaluationStrategy.sample_selection``) are typed with it. Option B
    requires the crossing because the specimen stores runs of its own and never widens the union.
    """
    return cast("SelectionMember", selection)


def as_native_evidence(result: SpecimenResult) -> NativeEvidence:
    """Return the specimen's result where a generic consumer wants a ``NativeEvidence``.

    ``NativeEvidence`` is the closed union of the production results, which ``BehaviorView.decode_for`` and
    ``ExecutionCapture`` are typed with. Option B requires the crossing because the specimen implements
    ``BehaviorView`` itself instead of the bound-checked ``StrategyBehavior``.
    """
    return cast("NativeEvidence", result)


def native_evidence_type() -> type[NativeEvidence]:
    """Return the specimen's result type where ``BehaviorView.result_type`` wants a ``NativeEvidence`` type.

    The same union as :func:`as_native_evidence`, crossed for the class rather than an instance.
    """
    return cast("type[NativeEvidence]", SpecimenResult)


def as_native_handler(handler: SpecimenToolHandler) -> AnalysisToolHandler[NativeEvidence]:
    """Return the specimen's bound handler where ``BehaviorView.bind_handler`` wants a ``NativeEvidence`` handler.

    The handler returns the specimen's result, which is not a ``NativeEvidence``. Option B requires the crossing
    for the same reason as :func:`as_native_evidence`.
    """
    return cast("AnalysisToolHandler[NativeEvidence]", handler)
