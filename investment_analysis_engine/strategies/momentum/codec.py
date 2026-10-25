"""Strict JSON evidence for the retained Momentum result and input context.

The fixed typed schema reconstructs only Momentum's declared dataclasses and
enums. No class names, providers, calculators or presentation properties are
dispatched from stored data. Optional values and ordered evidence are retained.
"""

import json

from pydantic import BaseModel, ConfigDict, model_validator

from investment_analysis_engine.analysis.run_models import StrictJsonMapping, _validate_json_value
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.constants import TrendStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.strategies.momentum.analyzer import MomentumRun


class _MomentumEvidence(BaseModel):
    """The wire shape, independent of the public presenter JSON."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    run: MomentumRun

    @model_validator(mode="after")
    def _validate_context(self) -> "_MomentumEvidence":
        run = self.run
        ticker = run.ticker
        if not ticker or ticker != ticker.strip().upper():
            raise ValueError("Momentum evidence requires a normalized ticker.")
        if run.effective_as_of.utcoffset() is None:
            raise ValueError("Momentum timestamp must be timezone-aware.")
        _validate_status(run)
        profile = run.instrument_profile
        if profile is not None:
            if profile.ticker != ticker:
                raise ValueError("Momentum profile ticker does not match metrics.")
            resolution = profile.security_unit_resolution
            if resolution is not None and resolution.provenance is not None:
                for document in resolution.provenance.documents:
                    if document.available_at.utcoffset() is None or document.retrieved_at.utcoffset() is None:
                        raise ValueError("Document timestamps must be timezone-aware.")
        return self


def _validate_status(run: MomentumRun) -> None:
    """Require the status, the reasons, the metrics and the provider failure to agree.

    ``ok`` has metrics with a bullish or bearish trend and no reason. ``input_unavailable`` has a reason and either
    metrics with an unknown trend (``insufficient_history``) or none (``not_available_as_of`` or no code).
    ``provider_error`` has no metrics, a reason and ``provider_error``. No other status is produced.
    """
    metrics = run.metrics
    if metrics is not None and (metrics.ticker != run.ticker or metrics.timestamp != run.effective_as_of):
        raise ValueError("Momentum metrics do not match the run's ticker and time.")
    status = run.execution_status
    if run.provider_failure is not None and status is not CalculationStatus.PROVIDER_ERROR:
        raise ValueError("A Momentum provider failure requires the provider_error status.")
    if status is CalculationStatus.OK:
        _validate_ok(run)
    elif status is CalculationStatus.INPUT_UNAVAILABLE:
        _validate_unavailable(run)
    elif status is CalculationStatus.PROVIDER_ERROR:
        if metrics is not None or not run.reason or run.reason_code is not ReasonCode.PROVIDER_ERROR:
            raise ValueError("A Momentum provider error requires a reason and provider_error, and has no metrics.")
    else:
        raise ValueError(f"Momentum does not produce the {status.value} status.")


def _validate_ok(run: MomentumRun) -> None:
    """Require metrics with a known trend and no reason."""
    if run.metrics is None or run.metrics.status is TrendStatus.UNKNOWN:
        raise ValueError("An ok Momentum run requires metrics with a known trend.")
    if run.reason is not None or run.reason_code is not None:
        raise ValueError("An ok Momentum run carries no reason.")


def _validate_unavailable(run: MomentumRun) -> None:
    """Require a reason, and the code that goes with metrics or with their absence."""
    if not run.reason:
        raise ValueError("An unavailable Momentum run requires a reason.")
    if run.metrics is not None:
        if run.metrics.status is not TrendStatus.UNKNOWN or run.reason_code is not ReasonCode.INSUFFICIENT_HISTORY:
            raise ValueError("An unavailable Momentum run with metrics requires an unknown trend and its code.")
    elif run.reason_code not in (None, ReasonCode.NOT_AVAILABLE_AS_OF):
        raise ValueError("An unavailable Momentum run without metrics carries no code or not_available_as_of.")


def encode_momentum(evidence: MomentumRun) -> StrictJsonMapping:
    """Encode and revalidate a detached finite JSON snapshot of Momentum evidence.

    Validation runs through JSON even for already-constructed dataclasses so
    invalid native instances cannot bypass field and nested invariant checks.
    """
    payload = _MomentumEvidence(run=evidence).model_dump(mode="json")
    decode_momentum(payload)
    return payload


def decode_momentum(payload: StrictJsonMapping) -> MomentumRun:
    """Restore typed evidence, rejecting corrupt fields without recalculation.

    JSON-mode strict validation admits ISO dates, enum values and JSON arrays
    for their declared types while rejecting coercion of numeric strings/bools,
    unknown fields, invalid enums and non-finite numbers at every depth.
    """
    _validate_json_value(payload)
    return _MomentumEvidence.model_validate_json(json.dumps(payload, allow_nan=False, ensure_ascii=False)).run


def momentum_native_status(result: MomentumRun, /) -> CalculationStatus:
    """Return the result-level status the run reports."""
    return result.execution_status


def momentum_ticker(result: MomentumRun, /) -> str:
    """Return the ticker the evidence is about, which must equal its run envelope's ticker."""
    return result.ticker
