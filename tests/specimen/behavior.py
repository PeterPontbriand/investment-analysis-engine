"""The specimen's behavior bundle.

The production ``StrategyBehavior`` bounds its selection and result types by the closed production unions, which
the specimen must never be added to. The specimen therefore implements the erased view that generic consumers use,
``BehaviorView``, directly. Each method guards with an exact-type check exactly as ``StrategyBehavior`` does, and
its types cross the bound only through :mod:`tests.specimen.closed_types`.
"""

from investment_analysis_engine.analysis.run_models import StrictJsonMapping
from investment_analysis_engine.core.strategy_errors import undeclared
from investment_analysis_engine.orchestrator.tool_runtime import AnalysisToolHandler, ToolRuntime
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from investment_analysis_engine.workspace.strategy_types import NativeEvidence
from tests.specimen.analyzer import SpecimenResult
from tests.specimen.closed_types import as_native_evidence, as_native_handler, native_evidence_type
from tests.specimen.codec import decode_specimen, encode_specimen, specimen_native_status, specimen_ticker
from tests.specimen.replay import project_specimen
from tests.specimen.selection import SpecimenSelection
from tests.specimen.tool import SpecimenToolDependencies, SpecimenToolHandler


class SpecimenBehavior:
    """The specimen's functions behind the erased ``BehaviorView``, each guarded by an exact-type check."""

    @property
    def result_type(self) -> type[NativeEvidence]:
        """Return the specimen's native result type."""
        return native_evidence_type()

    def encode_object(self, evidence: object, /) -> StrictJsonMapping:
        """Encode ``evidence``, which must be exactly the specimen's result type."""
        if type(evidence) is not SpecimenResult:
            raise undeclared("result type", type(evidence))
        return encode_specimen(evidence)

    def decode_for(self, payload: StrictJsonMapping, ticker: str, /) -> NativeEvidence:
        """Decode a stored payload and require its evidence to be about ``ticker``."""
        result = decode_specimen(payload)
        if specimen_ticker(result) != ticker:
            raise ValueError("Ticker mismatch.")
        return as_native_evidence(result)

    def native_status_of(self, result: object, /) -> str | None:
        """Return the status of ``result``, which must be exactly the specimen's result type."""
        if type(result) is not SpecimenResult:
            raise undeclared("result type", type(result))
        return specimen_native_status(result)

    def bind_handler(self, dependencies: object, runtime: ToolRuntime, /) -> AnalysisToolHandler[NativeEvidence]:
        """Bind the specimen's handler to its own dependency class and the shared runtime."""
        if type(dependencies) is not SpecimenToolDependencies:
            raise undeclared("handler dependencies", type(dependencies))
        return as_native_handler(SpecimenToolHandler(dependencies, runtime))

    def project_for(self, inputs: ReplayInputs, evidence: object, selection: object, options: ReplayOptions, /) -> str:
        """Project ``evidence`` and ``selection``, which must be exactly the specimen's types."""
        if type(evidence) is not SpecimenResult:
            raise undeclared("result type", type(evidence))
        if type(selection) is not SpecimenSelection:
            raise undeclared("selection type", type(selection))
        return project_specimen(inputs, evidence, selection, options)
