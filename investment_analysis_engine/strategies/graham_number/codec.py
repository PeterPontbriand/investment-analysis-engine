"""Strict version-one codec for complete Graham Number execution evidence."""

from pydantic import BaseModel, ConfigDict, model_validator

from investment_analysis_engine.analysis.run_models import (
    StrictJsonMapping,
    decode_with_method_sections,
    snapshot_by_revalidation,
)
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.strategies.graham_number.vocabulary import METHOD_ID


class _NumberEvidence(BaseModel):
    """Fixed native schema with explicit handling of constructor-excluded methods."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    analysis: GrahamNumberAnalysis

    @model_validator(mode="after")
    def _validate_evidence(self) -> "_NumberEvidence":
        analysis = self.analysis
        if not analysis.ticker or analysis.ticker != analysis.ticker.strip().upper():
            raise ValueError("Graham Number requires a normalized ticker.")
        if analysis.as_of is not None and analysis.as_of.utcoffset() is None:
            raise ValueError("Analysis as_of must be timezone-aware.")
        if analysis.effective_as_of.utcoffset() is None:
            raise ValueError("Analysis effective_as_of must be timezone-aware.")
        if analysis.as_of is not None and analysis.effective_as_of != analysis.as_of:
            raise ValueError("Analysis effective_as_of must equal the requested as_of when one was given.")
        assembly, result = analysis.assembly, analysis.result
        if assembly.method != METHOD_ID or result.method != METHOD_ID:
            raise ValueError("Graham Number assembly/result method mismatch.")
        if assembly.status is CalculationStatus.OK:
            if assembly.eps is None or assembly.bvps is None or assembly.reason is not None:
                raise ValueError("Successful assembly requires EPS/BVPS and no failure reason.")
        elif not assembly.reason or not assembly.reason.strip() or result.status is not assembly.status:
            raise ValueError("Failed assembly requires a reason and matching result status.")
        comparison = analysis.price_comparison
        if comparison is not None and comparison.percent != analysis.margin_of_safety_percent:
            raise ValueError("Retained comparison percentage contradicts the analysis.")
        profile = analysis.instrument_profile
        if profile is not None and profile.ticker != analysis.ticker:
            raise ValueError("Instrument profile ticker mismatch.")
        return self

    @model_validator(mode="after")
    def _validate_timestamps(self) -> "_NumberEvidence":
        analysis = self.analysis
        assembly, comparison, profile = analysis.assembly, analysis.price_comparison, analysis.instrument_profile
        for freshness in (
            assembly.quote_freshness,
            comparison.quote_freshness if comparison is not None else None,
        ):
            if freshness is not None:
                for stamp in (freshness.evaluated_at, freshness.retrieved_at, freshness.market_observed_at):
                    if stamp is not None and stamp.utcoffset() is None:
                        raise ValueError("Quote freshness timestamps must be timezone-aware.")
        for resolution in (
            profile.security_unit_resolution if profile is not None else None,
            comparison.security_unit_resolution if comparison is not None else None,
        ):
            if resolution is not None and resolution.provenance is not None:
                for document in resolution.provenance.documents:
                    if document.available_at.utcoffset() is None or document.retrieved_at.utcoffset() is None:
                        raise ValueError("Security-unit document timestamps must be timezone-aware.")
        return self


def encode_graham_number(evidence: GrahamNumberAnalysis) -> StrictJsonMapping:
    """Capture a detached finite JSON snapshot, revalidating native instances."""
    return snapshot_by_revalidation(_NumberEvidence(analysis=evidence), decode_graham_number)


def decode_graham_number(payload: StrictJsonMapping) -> GrahamNumberAnalysis:
    """Reconstruct Number evidence without invoking financial or provider work."""
    return decode_with_method_sections(
        _NumberEvidence,
        payload,
        key="analysis",
        sections=("assembly", "result"),
        label="Graham Number",
        method_id=METHOD_ID,
    ).analysis


def graham_number_native_status(result: GrahamNumberAnalysis, /) -> CalculationStatus:
    """Return the native status: the assembly's, or the calculation's when the assembly succeeded."""
    return result.native_status


def graham_number_ticker(result: GrahamNumberAnalysis, /) -> str:
    """Return the ticker the evidence is about, which must equal its run envelope's ticker."""
    return result.ticker
