"""Graham Number's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from src.analysis.base_analyzer import AnalysisContext
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments, FiniteFloat
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from src.strategies.graham_number.config import GrahamNumberConfig, GrahamNumberEPSBasis
from src.strategies.graham_number.service import GrahamNumberAnalysis


class GrahamNumberToolArguments(AnalysisToolArguments):
    """Validated arguments for Graham Number analysis."""

    eps_basis: GrahamNumberEPSBasis = "three_year_average"
    eps_override: FiniteFloat | None = None
    bvps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None
    use_cache: bool = True


@dataclass(frozen=True)
class GrahamNumberToolDependencies:
    """Injected Graham Number analyzer and provider selections."""

    analyzer: GrahamNumberAnalyzer
    security_provider_id: str
    quote_provider_id: str

    def __post_init__(self) -> None:
        """Reject missing provider selections before any tool is registered."""
        if any(not provider_id.strip() for provider_id in (self.security_provider_id, self.quote_provider_id)):
            raise ValueError("Analysis tool provider IDs must be non-empty.")


class GrahamNumberToolHandler:
    """Bind Graham Number's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: GrahamNumberToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer, provider selections and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> GrahamNumberAnalysis:
        """Validate, resolve, and calculate one Graham Number run."""
        arguments = GrahamNumberToolArguments.model_validate(raw_arguments)
        profile = self._runtime.resolve_profile(arguments.ticker)
        config = GrahamNumberConfig(
            security_provider_id=self._dependencies.security_provider_id,
            quote_provider_id=self._dependencies.quote_provider_id,
            eps_basis=arguments.eps_basis,
            eps_override=arguments.eps_override,
            bvps_override=arguments.bvps_override,
            quote_override=arguments.current_price_override,
        )
        executed_at = self._runtime.validated_clock_value()
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.analyzer.run_analysis(ticker=arguments.ticker, config=config, context=context)
