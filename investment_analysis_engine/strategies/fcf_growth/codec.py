"""Strict version-one codec for native FCF and earnings-growth evidence."""

from pydantic import BaseModel, ConfigDict, model_validator

from investment_analysis_engine.analysis.run_models import (
    StrictJsonMapping,
    decode_with_native_identifiers,
    snapshot_by_revalidation,
)
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.strategies.fcf_growth.models import (
    METHOD_VERSION,
    SCHEMA_VERSION,
    FCFEarningsGrowthResult,
)
from investment_analysis_engine.strategies.fcf_growth.vocabulary import ANALYSIS_ID, METHOD_ID


class _FCFEvidence(BaseModel):
    """Fixed native result schema, independent of presentation and codec versions."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    result: FCFEarningsGrowthResult

    @model_validator(mode="after")
    def _validate_context(self) -> "_FCFEvidence":
        result = self.result
        if not result.ticker or result.ticker != result.ticker.strip().upper():
            raise ValueError("FCF evidence requires a normalized ticker.")
        for stamp in (result.requested_as_of, result.effective_as_of, result.period_start, result.period_end):
            if stamp is not None and stamp.utcoffset() is None:
                raise ValueError("FCF result timestamps must be timezone-aware.")
        for observation in result.annual_observations:
            if observation.period_start.utcoffset() is None or observation.period_end.utcoffset() is None:
                raise ValueError("Annual observation timestamps must be timezone-aware.")
        profile = result.instrument_profile
        if profile is not None:
            resolution = profile.security_unit_resolution
            if resolution is not None and resolution.provenance is not None:
                for document in resolution.provenance.documents:
                    if document.available_at.utcoffset() is None or document.retrieved_at.utcoffset() is None:
                        raise ValueError("Security-unit document timestamps must be timezone-aware.")
        return self


def encode_fcf_growth(evidence: FCFEarningsGrowthResult) -> StrictJsonMapping:
    """Capture a detached finite snapshot, revalidating native instances via JSON."""
    return snapshot_by_revalidation(_FCFEvidence(result=evidence), decode_fcf_growth)


def decode_fcf_growth(payload: StrictJsonMapping) -> FCFEarningsGrowthResult:
    """Restore declared native evidence without resolving inputs or computing metrics."""
    return decode_with_native_identifiers(
        _FCFEvidence,
        payload,
        label="FCF",
        identifiers={"strategy_id": ANALYSIS_ID, "method_id": METHOD_ID},
        versions={"method_version": METHOD_VERSION, "schema_version": SCHEMA_VERSION},
    ).result


def fcf_growth_native_status(result: FCFEarningsGrowthResult, /) -> CalculationStatus:
    """Return the native execution status."""
    return result.execution_status


def fcf_growth_ticker(result: FCFEarningsGrowthResult, /) -> str:
    """Return the ticker the evidence is about, which must equal its run envelope's ticker."""
    return result.ticker
