"""Strict version-one codec for complete Graham Growth execution evidence."""

import json

from pydantic import BaseModel, ConfigDict, model_validator

from src.analysis.shared.graham_contracts import GrahamMethod
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.core.analysis_status import CalculationStatus
from src.workspace.models import StrictJsonMapping, _validate_json_value


class _GrowthEvidence(BaseModel):
    """Fixed native schema with explicit handling of constructor-excluded methods."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    analysis: GrahamGrowthAnalysis

    @model_validator(mode="after")
    def _validate_evidence(self) -> "_GrowthEvidence":
        analysis = self.analysis
        if not analysis.ticker or analysis.ticker != analysis.ticker.strip().upper():
            raise ValueError("Graham Growth requires a normalized ticker.")
        if analysis.as_of is not None and analysis.as_of.utcoffset() is None:
            raise ValueError("Analysis as_of must be timezone-aware.")
        assembly, result = analysis.assembly, analysis.result
        if assembly.method is not GrahamMethod.GROWTH_VALUE or result.method is not GrahamMethod.GROWTH_VALUE:
            raise ValueError("Graham Growth assembly/result method mismatch.")
        if assembly.status is CalculationStatus.OK:
            if (
                assembly.eps is None
                or assembly.expected_growth is None
                or assembly.current_aaa_yield is None
                or assembly.reason is not None
            ):
                raise ValueError("Successful assembly requires EPS, growth and AAA yield and no failure reason.")
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
    def _validate_timestamps(self) -> "_GrowthEvidence":
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


def encode_graham_growth(evidence: GrahamGrowthAnalysis) -> StrictJsonMapping:
    """Capture a detached finite JSON snapshot, revalidating native instances."""
    payload = _GrowthEvidence(analysis=evidence).model_dump(mode="json")
    decode_graham_growth(payload)
    return payload


def decode_graham_growth(payload: StrictJsonMapping) -> GrahamGrowthAnalysis:
    """Reconstruct Growth evidence without invoking financial or provider work."""
    _validate_json_value(payload)
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("Graham Growth analysis must be an object.")
    analysis = dict(analysis)
    for name in ("assembly", "result"):
        section = analysis.get(name)
        if not isinstance(section, dict) or section.get("method") != "graham_growth_value":
            raise ValueError("Graham Growth assembly/result method mismatch.")
        # Native init=False identifiers are checked, then restored by the native
        # constructor. Copy before removal to leave caller-owned data intact.
        analysis[name] = {key: item for key, item in section.items() if key != "method"}
    wire = {**payload, "analysis": analysis}
    return _GrowthEvidence.model_validate_json(json.dumps(wire, allow_nan=False)).analysis
