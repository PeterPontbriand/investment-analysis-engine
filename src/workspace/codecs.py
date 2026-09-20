"""Explicit version dispatch and safe errors for stored workspace evidence."""

from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthResult
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.analysis.strategy.momentum.momentum_analyzer import MomentumRun
from src.workspace.fcf_growth import decode_fcf_growth, encode_fcf_growth
from src.workspace.graham_growth import decode_graham_growth, encode_graham_growth
from src.workspace.graham_number import decode_graham_number, encode_graham_number
from src.workspace.models import StrictJsonMapping
from src.workspace.momentum import decode_momentum, encode_momentum
from src.workspace.runs import AnalysisRun


class UnsupportedRunVersionError(ValueError):
    """The stored method or version has no supported evidence decoder."""

    reason_code = "unsupported_run_version"


class InvalidStoredRunError(ValueError):
    """Stored evidence violates its declared schema or envelope identity."""

    reason_code = "invalid_stored_run"


def encode_evidence(
    evidence: MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult,
) -> StrictJsonMapping:
    """Encode the supported native evidence into an envelope-ready mapping."""
    try:
        if isinstance(evidence, FCFEarningsGrowthResult):
            return encode_fcf_growth(evidence)
        if isinstance(evidence, GrahamGrowthAnalysis):
            return encode_graham_growth(evidence)
        if isinstance(evidence, GrahamNumberAnalysis):
            return encode_graham_number(evidence)
        return encode_momentum(evidence)
    except (ValueError, TypeError) as exc:
        label = (
            "FCF Growth"
            if isinstance(evidence, FCFEarningsGrowthResult)
            else "Graham Growth"
            if isinstance(evidence, GrahamGrowthAnalysis)
            else "Graham Number"
            if isinstance(evidence, GrahamNumberAnalysis)
            else "Momentum"
        )
        raise InvalidStoredRunError(f"Invalid {label} evidence.") from exc


def decode_evidence(
    run: AnalysisRun,
) -> MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult | None:
    """Decode supported evidence using the envelope's explicit version tuple.

    Attempts that ended before resolution may have no result. Version checks
    still apply; unsupported records must never trigger recomputation.
    """
    fcf_pair = (run.analysis_id, run.method_id) == ("fcf_earnings_growth", "reported_fcf_eps_cagr")
    if (
        (run.analysis_id, run.method_id)
        not in (
            ("momentum", "sma_crossover"),
            ("graham", "graham_number"),
            ("graham", "graham_growth_value"),
            ("fcf_earnings_growth", "reported_fcf_eps_cagr"),
        )
        or any(
            type(version) is not int or version != 1
            for version in (
                run.run_schema_version,
                run.config_schema_version,
                run.evidence_codec_version,
                run.projection_version,
            )
        )
        or (
            type(run.method_version) is not int
            or run.method_version != (2 if fcf_pair else 1)
            or type(run.result_schema_version) is not int
            or run.result_schema_version != (3 if fcf_pair else 1)
        )
    ):
        raise UnsupportedRunVersionError("Unsupported Analysis Run method or version.")
    if run.result_evidence is None:
        return None
    try:
        if fcf_pair:
            fcf = decode_fcf_growth(run.result_evidence)
            if fcf.ticker != run.ticker:
                raise ValueError("Ticker mismatch.")
            return fcf
        if run.method_id == "graham_growth_value":
            growth = decode_graham_growth(run.result_evidence)
            if growth.ticker != run.ticker:
                raise ValueError("Ticker mismatch.")
            return growth
        if run.method_id == "graham_number":
            number = decode_graham_number(run.result_evidence)
            if number.ticker != run.ticker:
                raise ValueError("Ticker mismatch.")
            return number
        evidence = decode_momentum(run.result_evidence)
        if evidence.metrics.ticker != run.ticker:
            raise ValueError("Ticker mismatch.")
        return evidence
    except (ValueError, TypeError) as exc:
        label = (
            "FCF Growth"
            if fcf_pair
            else "Graham Growth"
            if run.method_id == "graham_growth_value"
            else "Graham Number"
            if run.method_id == "graham_number"
            else "Momentum"
        )
        raise InvalidStoredRunError(f"Invalid stored {label} evidence.") from exc
